"""Hidratacao dos papers da lista de trabalho via API do HF."""

from __future__ import annotations

import datetime as dt
import sqlite3
from typing import Any, Optional

from .. import db
from ..fontes.hf_client import ClienteHF, ErroHF
from ..fontes.modelos import paper_para_dim, paper_para_metrica
from ..log import logger
from .tipos import ItemTrabalho, ResultadoBackfill

log = logger("backfill")


def _linha_minima(it: ItemTrabalho) -> dict[str, Any]:
    """Fallback quando o HF nao devolve o paper: a linha existe mesmo assim,
    senao as FKs de triagem e ponte impedem o resto do backfill."""
    return {
        "paper_id": it.paper_id,
        "titulo": it.titulo or f"(sem titulo) {it.paper_id}",
        "data_arxiv": it.data_publicado,
        "data_hf_daily": it.data_publicado,
        "url_arxiv": f"https://arxiv.org/abs/{it.paper_id}",
        "url_hf": f"https://huggingface.co/papers/{it.paper_id}",
        "primeiro_visto_em": db.agora(),
    }


def hidratar(
    conn: sqlite3.Connection,
    cliente: ClienteHF,
    itens: dict[str, ItemTrabalho],
    res: ResultadoBackfill,
    *,
    hoje: Optional[dt.date] = None,
    force: bool = False,
) -> None:
    hoje = hoje or db.hoje()
    ja = {
        r["paper_id"]
        for r in conn.execute("SELECT paper_id FROM dim_paper WHERE enriquecido_em IS NOT NULL")
    }
    agora = db.agora()

    for pid, it in itens.items():
        if pid in ja and not force:
            continue
        try:
            paper = cliente.paper(pid)
        except ErroHF as e:
            log.warning("hidratacao falhou em %s: %s", pid, e)
            res.falhas_hidratacao.append(pid)
            with db.transacao(conn):
                db.upsert_paper(conn, _linha_minima(it))
            continue

        with db.transacao(conn):
            db.upsert_paper(
                conn,
                paper_para_dim(paper, primeiro_visto_em=agora, enriquecido_em=agora),
            )
            # snapshot de hoje, com as metricas atuais
            db.upsert_metrica(
                conn, paper_para_metrica(paper, data_snapshot=hoje, origem="backfill")
            )
            # e um snapshot historico com o upvote do dia 1: a serie comeca com
            # dois pontos reais em vez de um
            data_dia1 = paper.submittedOnDailyAt or it.data_publicado
            if data_dia1 and it.upvotes_dia1 is not None:
                db.upsert_metrica(
                    conn,
                    {
                        "paper_id": paper.paper_id,
                        "data_snapshot": data_dia1,
                        "upvotes": it.upvotes_dia1,
                        "origem": "backfill",
                    },
                )
            for ordem, autor in enumerate(paper.authors, start=1):
                if autor.name:
                    db.upsert(
                        conn,
                        "ponte_paper_autor",
                        {
                            "paper_id": paper.paper_id,
                            "ordem": ordem,
                            "autor": autor.name,
                            "hf_user": autor.hf_user,
                            "verificado": int(autor.verificado),
                        },
                        chave=["paper_id", "ordem"],
                    )
            for kw in paper.ai_keywords:
                if kw:
                    db.inserir_ignorando(
                        conn,
                        "ponte_paper_keyword",
                        {"paper_id": paper.paper_id, "keyword": kw},
                    )
        res.hidratados += 1

    if res.falhas_hidratacao:
        res.avisos.append(f"hidratacao_falhou:{len(res.falhas_hidratacao)}")
