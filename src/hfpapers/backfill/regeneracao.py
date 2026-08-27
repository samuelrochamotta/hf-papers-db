"""Regeneracao pelo pipeline novo: Estagio A nos sem classificacao, Estagio B
nos aprovados sem ficha.

Unico gasto de LLM do backfill. Nenhuma das duas etapas reabre o veredito
historico - o Estagio B devolve um veredito proprio, que fica registrado a parte
para o relatorio de validacao poder compara-los.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Sequence

from .. import db, taxonomia
from ..config import Config
from ..estagios import classificacao
from ..llm import estagio_a as ea
from ..llm import estagio_b as eb
from ..llm.cliente import ClienteLLM, ErroLLM
from ..log import logger
from .tipos import RUN_ID, ResultadoBackfill

log = logger("backfill")


def _entradas(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[ea.PaperEntrada]:
    linhas = conn.execute(sql, params).fetchall()
    entradas = []
    for r in linhas:
        kws = [
            x["keyword"]
            for x in conn.execute(
                "SELECT keyword FROM ponte_paper_keyword WHERE paper_id = ?", (r["paper_id"],)
            )
        ]
        entradas.append(
            ea.PaperEntrada(
                paper_id=r["paper_id"],
                titulo=r["titulo"],
                abstract=r["abstract"] or r["ai_summary"] or "",
                keywords=kws,
                ai_summary=r["ai_summary"],
            )
        )
    return entradas


# ── Estagio A ───────────────────────────────────────────────────────────────


def classificar_sem_taxonomia(
    conn: sqlite3.Connection,
    cliente: ClienteLLM,
    res: ResultadoBackfill,
    cfg: Config,
    ids: Sequence[str],
) -> None:
    """Estagio A nos papers sem classificacao curada - em geral os FORA.

    So para ganhar area e topico. Estes nao passam pelo Estagio B: o veredito
    historico ja esta gravado e nao e reaberto aqui.

    Restrito aos ids da lista de trabalho: sem isso o backfill classificaria de
    quebra os papers do dia corrente, que sao trabalho do `run`.
    """
    if not ids:
        return
    marca = ", ".join("?" for _ in ids)
    pendentes = _entradas(
        conn,
        "SELECT paper_id, titulo, abstract, ai_summary FROM dim_paper "
        f"WHERE paper_id IN ({marca}) "
        "  AND paper_id NOT IN (SELECT paper_id FROM ponte_paper_area) "
        "ORDER BY paper_id",
        tuple(ids),
    )
    if not pendentes:
        return
    vocab = ea.carregar_vocabulario(conn)
    log.info("estagio A em %s papers sem classificacao", len(pendentes))

    for paper in pendentes:
        try:
            a = ea.classificar(cliente, paper, vocab, cfg=cfg)
        except ErroLLM as e:
            log.error("estagio A falhou em %s: %s", paper.paper_id, e)
            res.avisos.append(f"estagio_a_falhou:{paper.paper_id}")
            continue
        res.uso.somar(a.uso)
        with db.transacao(conn):
            taxonomia.aplicar_classificacao(
                conn,
                paper.paper_id,
                area_primaria=a.area_primaria,
                areas_secundarias=a.areas_secundarias,
                topicos_paper=a.topicos,
                cfg=cfg.taxonomia,
            )
            if a.candidato_novo_rotulo:
                c = taxonomia.registrar_candidato(
                    conn,
                    rotulo=a.candidato_novo_rotulo.get("rotulo", ""),
                    tipo=a.candidato_novo_rotulo.get("tipo", "topico"),
                    definicao=a.candidato_novo_rotulo.get("definicao", ""),
                    paper_id=paper.paper_id,
                    cfg=cfg.taxonomia,
                )
                if c.aviso:
                    res.avisos.append(c.aviso)
        res.estagio_a += 1


# ── vereditos regenerados ───────────────────────────────────────────────────


def _arquivo_vereditos(cfg: Config) -> Path:
    return cfg.dir_estado / "vereditos_estagio_b.json"


def registrar_veredito_regenerado(cfg: Config, paper_id: str, veredito: str) -> None:
    """Guarda o veredito que o Estagio B devolveu, sem tocar em `fato_triagem`.

    O veredito historico e autoritativo no backfill - ele nao e reaberto. Mas
    sem guardar o veredito novo em algum lugar, o relatorio de validacao
    compararia o historico contra ele mesmo e daria 100% de concordancia sempre.

    Por isso mora em `data/estado/` e nao em `relatorios/`: e entrada de uma
    etapa seguinte, nao artefato de leitura. Apagar por engano nao quebra o
    relatorio - faz ele mentir.
    """
    caminho = _arquivo_vereditos(cfg)
    cfg.dir_estado.mkdir(parents=True, exist_ok=True)
    dados = {}
    if caminho.exists():
        try:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            dados = {}
    dados[paper_id] = veredito
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def vereditos_regenerados(cfg: Config) -> dict[str, str]:
    caminho = _arquivo_vereditos(cfg)
    if not caminho.exists():
        return {}
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


# ── Estagio B ───────────────────────────────────────────────────────────────


def gerar_fichas(
    conn: sqlite3.Connection,
    cliente: ClienteLLM,
    res: ResultadoBackfill,
    cfg: Config,
    ids: Sequence[str],
) -> None:
    """Estagio B nos aprovados sem ficha. Unico gasto significativo do backfill.

    Restrito aos ids da lista de trabalho, pelo mesmo motivo do Estagio A: ficha
    de paper do dia corrente e trabalho do `run`, nao do backfill.
    """
    if not ids:
        return
    marca = ", ".join("?" for _ in ids)
    pendentes = _entradas(
        conn,
        "SELECT p.paper_id, p.titulo, p.abstract, p.ai_summary FROM dim_paper p "
        "JOIN fato_triagem t ON t.paper_id = p.paper_id "
        f"WHERE p.paper_id IN ({marca}) "
        "  AND t.veredito IN ('amplo','estrito') "
        "  AND p.paper_id NOT IN (SELECT paper_id FROM dim_ficha) "
        "ORDER BY p.paper_id",
        tuple(ids),
    )
    if not pendentes:
        return
    log.info("estagio B em %s aprovados sem ficha", len(pendentes))

    for paper in pendentes:
        area = conn.execute(
            "SELECT area FROM ponte_paper_area WHERE paper_id = ? AND is_primaria = 1",
            (paper.paper_id,),
        ).fetchone()
        topicos = [
            r["topico"]
            for r in conn.execute(
                "SELECT topico FROM ponte_paper_topico WHERE paper_id = ?", (paper.paper_id,)
            )
        ]
        paper.area_primaria = area["area"] if area else None
        paper.topicos = topicos
        try:
            b = eb.avaliar(cliente, paper, cfg=cfg)
        except ErroLLM as e:
            log.error("estagio B falhou em %s: %s", paper.paper_id, e)
            res.avisos.append(f"estagio_b_falhou:{paper.paper_id}")
            continue
        res.uso.somar(b.uso)
        registrar_veredito_regenerado(cfg, paper.paper_id, b.veredito)
        if not b.ficha:
            # o veredito historico manda no backfill; a ficha ausente vira aviso
            res.avisos.append(f"ficha_ausente:{paper.paper_id}:{b.veredito}")
            continue
        with db.transacao(conn):
            classificacao.gravar_ficha(
                conn, paper.paper_id, b.ficha, modelo=cfg.llm.estagio_b.modelo, run_id=RUN_ID
            )
        res.fichas_geradas += 1
