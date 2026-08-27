"""Orquestracao dos cinco estagios e o registro da rodada.

Cada estagio commita a propria transacao. Falha no estagio 3 nao desfaz o que o
estagio 1 gravou - a rodada termina com `status = 'parcial'` e os avisos dizem
onde doeu.
"""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
from dataclasses import dataclass, field
from typing import Optional, Sequence

from . import db, guardrails
from .config import Config, config
from .estagios import classificacao, coleta, enriquecimento, export, refresh
from .fontes.hf_client import ClienteHF
from .llm import estagio_a as ea
from .llm.cliente import ClienteLLM, Estimativa, Uso
from .log import logger

log = logger("run")

ESTAGIOS = ("coleta", "enriquecimento", "classificacao", "refresh", "export")


@dataclass
class ResultadoRun:
    run_id: str
    status: str = "parcial"
    dias: list[str] = field(default_factory=list)
    coletados: int = 0
    novos: int = 0
    ja_vistos: int = 0
    fora: int = 0
    amplo: int = 0
    estrito: int = 0
    fichas: int = 0
    refresh_papers: int = 0
    avisos: list[str] = field(default_factory=list)
    uso: Uso = field(default_factory=Uso)
    arquivos: dict[str, int] = field(default_factory=dict)

    @property
    def aprovados(self) -> int:
        return self.amplo + self.estrito

    @property
    def taxa_fora(self) -> Optional[float]:
        total = self.fora + self.aprovados
        return self.fora / total if total else None


def novo_run_id(hoje: Optional[dt.datetime] = None) -> str:
    return (hoje or dt.datetime.now()).strftime("run-%Y%m%d-%H%M%S")


def _abrir_execucao(conn: sqlite3.Connection, run_id: str) -> None:
    db.upsert_execucao(
        conn,
        {
            "run_id": run_id,
            "iniciado_em": db.agora(),
            "status": "parcial",
        },
    )


def _fechar_execucao(conn: sqlite3.Connection, res: ResultadoRun) -> None:
    db.upsert_execucao(
        conn,
        {
            "run_id": res.run_id,
            "iniciado_em": db.agora(),
            "finalizado_em": db.agora(),
            "status": res.status,
            "dias_cobertos": json.dumps(res.dias),
            "qtd_coletados": res.coletados,
            "qtd_novos": res.novos,
            "qtd_ja_vistos": res.ja_vistos,
            "qtd_fora": res.fora,
            "qtd_amplo": res.amplo,
            "qtd_estrito": res.estrito,
            "taxa_fora": res.taxa_fora,
            "qtd_refresh": res.refresh_papers,
            "tokens_entrada": res.uso.tokens_entrada,
            "tokens_saida": res.uso.tokens_saida,
            "custo_usd": res.uso.custo_usd,
            "avisos": json.dumps(res.avisos, ensure_ascii=False),
        },
    )


def rodar(
    *,
    cfg: Optional[Config] = None,
    conn: Optional[sqlite3.Connection] = None,
    data: Optional[dt.date] = None,
    apenas: Optional[Sequence[str]] = None,
    force: bool = False,
    hoje: Optional[dt.date] = None,
    cliente_hf: Optional[ClienteHF] = None,
    cliente_llm: Optional[ClienteLLM] = None,
) -> ResultadoRun:
    cfg = cfg or config()
    hoje = hoje or db.hoje()
    etapas = set(apenas or ESTAGIOS)
    fechar_conn = conn is None
    conn = conn or db.abrir(cfg)
    run_id = novo_run_id()
    res = ResultadoRun(run_id=run_id)
    hf = cliente_hf or ClienteHF(cfg)
    llm: Optional[ClienteLLM] = cliente_llm
    falhou = False

    try:
        _abrir_execucao(conn, run_id)

        # ── 1. coleta ───────────────────────────────────────────────────────
        novos: list[str] = []
        if "coleta" in etapas:
            r = coleta.rodar(
                conn,
                hf,
                datas=[data] if data else None,
                hoje=hoje,
                coletados_min_dia_util=cfg.guardrails.coletados_min_dia_util,
            )
            res.dias = [d.isoformat() for d in r.dias]
            res.coletados, res.ja_vistos = r.coletados, r.ja_vistos
            res.novos = len(r.novos)
            res.avisos.extend(r.avisos)
            novos = r.novos
            falhou = falhou or any(a.startswith("coleta_falhou") for a in r.avisos)

        # ── 2. enriquecimento ───────────────────────────────────────────────
        if "enriquecimento" in etapas and novos:
            r = enriquecimento.rodar(conn, hf, novos, data_snapshot=hoje)
            res.avisos.extend(r.avisos)

        # ── 3. classificacao ────────────────────────────────────────────────
        if "classificacao" in etapas:
            pendentes = classificacao.selecionar(
                conn,
                data=data.isoformat() if data else None,
                force=force,
            )
            if pendentes:
                llm = llm or ClienteLLM(cfg, conn=conn, run_id=run_id)
                r = classificacao.rodar(conn, llm, pendentes, run_id=run_id, cfg=cfg)
                res.fora, res.amplo, res.estrito = r.fora, r.amplo, r.estrito
                res.fichas = r.fichas
                res.avisos.extend(r.avisos)
                res.uso.somar(r.uso)
                falhou = falhou or any(a.startswith("estagio_a_falhou") for a in r.avisos)
            else:
                log.info("nada a classificar (tudo ja tem triagem)")

        # ── 4. refresh ──────────────────────────────────────────────────────
        if "refresh" in etapas:
            r = refresh.rodar(conn, hf, cfg.refresh, hoje=hoje)
            res.refresh_papers = r.papers_atualizados
            res.avisos.extend(r.avisos)

        # ── guardrails (validacao, nao decisao) ─────────────────────────────
        dia_util = (data or hoje).isoweekday() <= 5
        res.avisos.extend(
            guardrails.avaliar(
                guardrails.Contagens(
                    coletados=res.coletados,
                    fora=res.fora,
                    amplo=res.amplo,
                    estrito=res.estrito,
                    dia_util=dia_util,
                ),
                cfg.guardrails,
            )
        )

        # avisos de guardrail nao tornam a rodada parcial: eles validam, nao decidem
        res.status = "parcial" if falhou else "ok"
        _fechar_execucao(conn, res)

        # ── 5. export ───────────────────────────────────────────────────────
        if "export" in etapas:
            r = export.rodar(conn, cfg, run_id=run_id, hoje=hoje)
            res.arquivos = r.arquivos

    except Exception:
        res.status = "erro"
        _fechar_execucao(conn, res)
        raise
    finally:
        if cliente_hf is None:
            hf.fechar()
        if fechar_conn:
            conn.close()

    return res


# ── dry-run ─────────────────────────────────────────────────────────────────


@dataclass
class ResultadoDryRun:
    dias: list[str] = field(default_factory=list)
    coletados: int = 0
    ja_na_base: int = 0
    a_classificar: int = 0
    estimativa: Estimativa = field(default_factory=Estimativa)


def dry_run(
    *,
    cfg: Optional[Config] = None,
    conn: Optional[sqlite3.Connection] = None,
    data: Optional[dt.date] = None,
    hoje: Optional[dt.date] = None,
    cliente_hf: Optional[ClienteHF] = None,
) -> ResultadoDryRun:
    """Estima o custo da rodada sem gravar nada e sem chamar modelo."""
    cfg = cfg or config()
    hoje = hoje or db.hoje()
    fechar_conn = conn is None
    conn = conn or db.abrir(cfg)
    hf = cliente_hf or ClienteHF(cfg)
    res = ResultadoDryRun()

    try:
        datas = [data] if data else coleta.dias_faltantes(conn, hoje=hoje)
        res.dias = [d.isoformat() for d in datas]
        entradas: list[ea.PaperEntrada] = []
        ja_triados = {
            r["paper_id"] for r in conn.execute("SELECT paper_id FROM fato_triagem")
        }
        for d in datas:
            for item in hf.daily_papers(d):
                p = item.paper
                res.coletados += 1
                if p.paper_id in ja_triados:
                    res.ja_na_base += 1
                    continue
                entradas.append(
                    ea.PaperEntrada(
                        paper_id=p.paper_id,
                        titulo=p.title,
                        abstract=p.summary or "",
                        keywords=p.ai_keywords,
                        ai_summary=p.ai_summary,
                    )
                )
        res.a_classificar = len(entradas)
        res.estimativa = classificacao.estimar(
            conn, ClienteLLM.somente_precos(cfg), entradas, cfg=cfg
        )
    finally:
        if cliente_hf is None:
            hf.fechar()
        if fechar_conn:
            conn.close()

    return res
