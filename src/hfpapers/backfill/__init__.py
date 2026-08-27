"""Backfill da base historica a partir de `seed/`.

Roda uma vez e e idempotente: a segunda execucao nao altera contagem nem gera
chamada de LLM.

A lista de trabalho e a **uniao de tres fontes** - `hf-digest-estado.json`,
`taxonomia.json > classificacoes` e os ids das fichas dos digests. Usar so o
estado produz 241 papers e 82 fichas, e esta errado: `2608.14577` tem ficha e
classificacao mas sumiu do estado quando a rodada de 18/08 gravou o digest. O
estado e registro historico e fica verbatim; a uniao o recupera.

Ordem real de execucao (difere da ordem narrativa do PROMPT por causa das FKs:
ponte e triagem exigem a linha de `dim_paper` ja existente):

    vocabulario -> lista de trabalho -> hidratacao -> triagem
    -> classificacoes curadas -> Estagio A nos sem classificacao
    -> Estagio B nos aprovados -> relatorio de validacao

Um modulo por etapa; `rodar()` abaixo e a unica coisa que conhece a ordem.
"""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
from pathlib import Path
from typing import Optional

from .. import db, taxonomia
from ..config import Config, config
from ..fontes.hf_client import ClienteHF
from ..llm.cliente import ClienteLLM
from ..log import logger
from .hidratacao import hidratar
from .importacao import importar_classificacoes, importar_triagem
from .lista import montar_lista
from .regeneracao import (
    classificar_sem_taxonomia,
    gerar_fichas,
    registrar_veredito_regenerado,
    vereditos_regenerados,
)
from .tipos import RUN_ID, ItemTrabalho, ResultadoBackfill
from .validacao import relatorio_validacao

__all__ = [
    "RUN_ID",
    "ItemTrabalho",
    "ResultadoBackfill",
    "classificar_sem_taxonomia",
    "gerar_fichas",
    "hidratar",
    "importar_classificacoes",
    "importar_triagem",
    "montar_lista",
    "registrar_veredito_regenerado",
    "relatorio_validacao",
    "rodar",
    "vereditos_regenerados",
]

log = logger("backfill")


def rodar(
    seed: Path,
    *,
    cfg: Optional[Config] = None,
    conn: Optional[sqlite3.Connection] = None,
    cliente_hf: Optional[ClienteHF] = None,
    cliente_llm: Optional[ClienteLLM] = None,
    pular_llm: bool = False,
    force: bool = False,
    hoje: Optional[dt.date] = None,
) -> ResultadoBackfill:
    cfg = cfg or config()
    hoje = hoje or db.hoje()
    fechar_conn = conn is None
    conn = conn or db.abrir(cfg)
    hf = cliente_hf or ClienteHF(cfg)
    res = ResultadoBackfill()

    try:
        # 1. vocabulario primeiro - os limites e definicoes vem do seed
        tax = json.loads((seed / "taxonomia.json").read_text(encoding="utf-8"))
        with db.transacao(conn):
            taxonomia.carregar_seed(conn, tax)

        # 2. lista de trabalho: uniao das tres fontes
        itens = montar_lista(seed)
        res.papers = len(itens)
        log.info("lista de trabalho: %s papers", len(itens))

        # 3. hidratacao
        hidratar(conn, hf, itens, res, hoje=hoje, force=force)

        # 4. triagem historica
        importar_triagem(conn, itens, res)

        # 5. classificacoes curadas (autoritativas)
        importar_classificacoes(conn, seed, res, cfg)

        with db.transacao(conn):
            db.garantir_calendario(conn)

        res.fichas_existentes = db.contar(conn, "dim_ficha")

        # 6/7. LLM
        if not pular_llm:
            llm = cliente_llm or ClienteLLM(cfg, conn=conn, run_id=RUN_ID)
            classificar_sem_taxonomia(conn, llm, res, cfg, list(itens))
            gerar_fichas(conn, llm, res, cfg, list(itens))

        # 8. validacao contra o historico
        relatorio_validacao(conn, seed, cfg, res)

        db.upsert_execucao(
            conn,
            {
                "run_id": RUN_ID,
                "iniciado_em": db.agora(),
                "finalizado_em": db.agora(),
                "status": "ok" if not res.avisos else "parcial",
                "dias_cobertos": json.dumps([]),
                "qtd_coletados": res.papers,
                "qtd_novos": res.hidratados,
                "qtd_fora": res.vereditos.get("fora", 0),
                "qtd_amplo": res.vereditos.get("amplo", 0),
                "qtd_estrito": res.vereditos.get("estrito", 0),
                "tokens_entrada": res.uso.tokens_entrada,
                "tokens_saida": res.uso.tokens_saida,
                "custo_usd": res.uso.custo_usd,
                "avisos": json.dumps(res.avisos, ensure_ascii=False),
            },
        )
    finally:
        if cliente_hf is None:
            hf.fechar()
        if fechar_conn:
            conn.close()

    return res
