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
from .llm import schemas
from .llm.cliente import ClienteLLM, Estimativa, Uso
from .log import logger

log = logger("run")

ESTAGIOS = ("coleta", "enriquecimento", "classificacao", "refresh", "datas_arxiv", "export")


@dataclass
class ResultadoRun:
    run_id: str
    status: str = "parcial"
    dias: list[str] = field(default_factory=list)
    coletados: int = 0
    novos: int = 0
    ja_vistos: int = 0
    fora: int = 0
    aprovados: int = 0
    por_prerequisito: dict[str, int] = field(default_factory=dict)
    nao_classificados: int = 0
    selecionados: int = 0
    fichas: int = 0
    refresh_papers: int = 0
    avisos: list[str] = field(default_factory=list)
    uso: Uso = field(default_factory=Uso)
    arquivos: dict[str, int] = field(default_factory=dict)

    @property
    def taxa_fora(self) -> Optional[float]:
        total = self.fora + self.aprovados
        return self.fora / total if total else None

    @property
    def falhas_estagio_b(self) -> list[str]:
        """Papers cujo Estagio B caiu nas duas passadas, na ordem em que caiu.

        Sai dos avisos porque e la que `classificacao.rodar` os deixa; quem
        chama nao precisa conhecer o formato `estagio_b_falhou:<paper_id>`.
        """
        marca = "estagio_b_falhou:"
        return [a[len(marca):] for a in self.avisos if a.startswith(marca)]


def _absorver(res: ResultadoRun, parcial: classificacao.ResultadoClassificacao) -> None:
    """Passa para o `ResultadoRun` o que a classificacao acumulou ate agora.

    Chamada no `finally` da classificacao, e nao depois do `return` dela, para
    que valha tambem quando a varredura estoura no meio: as triagens ja gravadas
    sao fato no banco, e `log_execucao` tem de refletir isso. Fechar a execucao
    com `qtd_fora = qtd_aprovados = 0` depois de horas de varredura
    perde a contagem e ainda faz `doutor.checar_pendencias` descartar a rodada
    como corte - ele so considera execucao que classificou alguem.
    """
    res.fora, res.aprovados = parcial.fora, parcial.aprovados
    res.por_prerequisito = dict(parcial.por_prerequisito)
    res.nao_classificados = parcial.nao_classificados
    res.fichas = parcial.fichas
    res.avisos.extend(parcial.avisos)
    res.uso.somar(parcial.uso)


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
            "qtd_aprovados": res.aprovados,
            **{
                f"qtd_pr_{degrau}": res.por_prerequisito.get(degrau, 0)
                for degrau in schemas.PREREQUISITOS
            },
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
            res.selecionados = len(pendentes)
            if pendentes:
                llm = llm or ClienteLLM(cfg, conn=conn, run_id=run_id)
                parcial = classificacao.ResultadoClassificacao()
                try:
                    # A rodada diaria fica com a concorrencia do config (padrao
                    # 1, sequencial): sao ~30 papers, nao ha rodada a encurtar,
                    # e o que ela quer e nao dar rajada no provedor. Quem pede
                    # concorrencia na linha de comando e `reclassificar`.
                    classificacao.rodar(
                        conn, llm, pendentes, run_id=run_id, cfg=cfg,
                        concorrencia=cfg.llm.concorrencia, res=parcial,
                    )
                finally:
                    _absorver(res, parcial)
                falhou = falhou or any(a.startswith("estagio_a_falhou") for a in res.avisos)
            else:
                log.info("nada a classificar (tudo ja tem triagem)")

        # ── 4. refresh ──────────────────────────────────────────────────────
        if "refresh" in etapas:
            r = refresh.rodar(conn, hf, cfg.refresh, hoje=hoje)
            res.refresh_papers = r.papers_atualizados
            res.avisos.extend(r.avisos)

        if "datas_arxiv" in etapas:
            from .auditoria_arxiv import auditar
            auditoria = auditar(conn, cache=cfg.caminho_banco.parent / 'cache_arxiv_v1',
                               aplicar=True, apenas_pendentes=True)
            res.avisos.extend('arxiv_' + p['resultado'] + ':' + p['paper_id']
                             for p in auditoria['papers'] if p['resultado'] != 'verificado')
            cfg.dir_relatorios.mkdir(parents=True, exist_ok=True)
            (cfg.dir_relatorios / 'auditoria-arxiv-pendentes.json').write_text(
                json.dumps(auditoria, ensure_ascii=False, indent=2))

        # ── guardrails (validacao, nao decisao) ─────────────────────────────
        dia_util = (data or hoje).isoweekday() <= 5
        res.avisos.extend(
            guardrails.avaliar(
                guardrails.Contagens(
                    coletados=res.coletados,
                    fora=res.fora,
                    aprovados=res.aprovados,
                    por_prerequisito=res.por_prerequisito,
                    nao_classificados=res.nao_classificados,
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


# ── reclassificacao ─────────────────────────────────────────────────────────


def reclassificar(
    *,
    cfg: Optional[Config] = None,
    conn: Optional[sqlite3.Connection] = None,
    ids: Optional[Sequence[str]] = None,
    data: Optional[str] = None,
    tudo: bool = False,
    concorrencia: Optional[int] = None,
    so_estagio_a: bool = False,
    retomar: Optional[str] = None,
    cliente_llm: Optional[ClienteLLM] = None,
) -> ResultadoRun:
    """Roda so o estagio 3, sobre papers ja vistos, e registra a rodada.

    `retomar=<run_id>` continua uma rodada total que caiu no meio: reaproveita
    o `run_id` e leva so quem ainda nao tem triagem dele, de modo que `conferir`
    fecha em 0/0 e a trava de `run_id` do painel continua valendo. As contagens
    de `log_execucao` sao refeitas de `fato_triagem` no fim, porque as do
    segmento retomado sozinhas contariam so a metade.

    A selecao e `force=True`: leva quem ja tem triagem (o caso comum) e tambem
    o pendente que ficou sem linha, que e o que faz o criterio de conclusao da
    rodada total fechar em "zero papers sem triagem".


    Por que passa por aqui e nao chama `classificacao.rodar` direto: a rodada
    precisa existir em `log_execucao`. Sem a linha, ela e invisivel para o
    `doutor` (que corta as pendencias pela ultima execucao que classificou
    alguem) e para a trava de `run_id` do painel. Vale para a rodada dirigida
    (`--data`, `--paper`) tanto quanto para a total.

    Os campos de coleta e refresh do `ResultadoRun` ficam zerados de proposito:
    nenhum dos dois estagios roda aqui, e zero e a verdade, nao um buraco. Os
    guardrails tambem nao rodam - eles calibram o volume de um dia coletado, e
    dizer "volume atipico" de uma varredura de 482 papers seria ruido.

    `concorrencia=None` usa a do `config.yaml` (padrao 1). E aqui que ela
    importa: a rodada total sao ~482 papers de chamada sequencial, e este e o
    unico chamador que pede a base inteira de uma vez.

    `so_estagio_a` para a varredura no Estagio A: e a rodada que mede a massa
    da grade antes de gastar com ficha (spec, secao Operacao, passo 4). O
    candidato sai dela sem triagem nova - a faceta ele recebe, o veredito nao -,
    e por isso ela nao fecha o criterio de `conferir`.
    """
    cfg = cfg or config()
    fechar_conn = conn is None
    conn = conn or db.abrir(cfg)
    run_id = retomar or novo_run_id()
    res = ResultadoRun(run_id=run_id)
    if data:
        res.dias = [data]
    aberta = False

    try:
        papers = classificacao.selecionar(
            conn,
            ids=None if tudo else ids,
            data=None if tudo else data,
            force=True,
            exceto_run_id=retomar,
        )
        res.selecionados = len(papers)
        if not papers:
            # Nenhuma linha em `log_execucao`: rodada que nao classificou
            # ninguem nao serve de corte para o `doutor` e so poluiria o log.
            res.status = "ok"
            return res

        llm = cliente_llm or ClienteLLM(cfg, conn=conn, run_id=run_id)
        _abrir_execucao(conn, run_id)
        aberta = True
        parcial = classificacao.ResultadoClassificacao()
        try:
            classificacao.rodar(
                conn, llm, papers, run_id=run_id, cfg=cfg,
                concorrencia=cfg.llm.concorrencia if concorrencia is None else concorrencia,
                so_estagio_a=so_estagio_a,
                res=parcial,
            )
        finally:
            _absorver(res, parcial)
        # Mesmo criterio de `rodar`: falha do Estagio A e do que a rodada nao
        # deu conta; falha do Estagio B deixa o paper pendente, que e caminho
        # previsto (e sai impresso para o operador repetir um a um).
        res.status = (
            "parcial" if any(a.startswith("estagio_a_falhou") for a in res.avisos) else "ok"
        )
        if retomar:
            _recontar(conn, res)
        _fechar_execucao(conn, res)
    except Exception:
        res.status = "erro"
        if aberta:
            _fechar_execucao(conn, res)
        raise
    finally:
        if fechar_conn:
            conn.close()

    return res


def _recontar(conn: sqlite3.Connection, res: ResultadoRun) -> None:
    """As contagens da rodada inteira, lidas de `fato_triagem` pelo `run_id`."""
    res.fora = db.contar(conn, "fato_triagem", "run_id = ? AND veredito = 'fora'", (res.run_id,))
    res.por_prerequisito = {
        r["prerequisito"]: r["n"]
        for r in conn.execute(
            "SELECT prerequisito, COUNT(*) AS n FROM fato_triagem "
            "WHERE run_id = ? AND veredito = 'aprovado' GROUP BY prerequisito",
            (res.run_id,),
        )
    }
    res.aprovados = sum(res.por_prerequisito.values())


def conferir(conn: sqlite3.Connection, run_id: str) -> dict[str, int]:
    """Criterio de conclusao da reclassificacao total (spec, secao 2).

    A rodada acabou quando nenhuma triagem sobrou com `run_id` de outra rodada
    e nenhum paper esta sem triagem. Ler as duas contagens e mais barato do que
    conferir a mao depois de oito horas de varredura.
    """
    return {
        "outro_run_id": conn.execute(
            "SELECT COUNT(*) AS n FROM fato_triagem WHERE run_id <> ?", (run_id,)
        ).fetchone()["n"],
        "sem_triagem": conn.execute(
            "SELECT COUNT(*) AS n FROM dim_paper "
            "WHERE paper_id NOT IN (SELECT paper_id FROM fato_triagem)"
        ).fetchone()["n"],
    }


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
