"""Estagio 2 - ENRIQUECIMENTO: campos que so o endpoint por-paper tem.

Sao dois: os contadores de artefatos vinculados (`numTotal*`) e o
`authors[].status == 'claimed_verified'`. Como mudam devagar, isto roda so em
paper inedito (e, semanalmente, na janela quente pelo estagio de refresh).
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from dataclasses import dataclass, field
from typing import Optional, Sequence

from .. import db
from ..fontes.hf_client import ClienteHF, ErroHF
from ..fontes.modelos import paper_para_dim, paper_para_metrica
from ..log import logger

log = logger("enriquecimento")


@dataclass
class ResultadoEnriquecimento:
    enriquecidos: int = 0
    falhas: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)


def _atualizar_autores(conn: sqlite3.Connection, paper) -> None:
    """So o endpoint por-paper traz `status`/`user` do autor."""
    for ordem, autor in enumerate(paper.authors, start=1):
        if not autor.name:
            continue
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
            manter_se_nulo=["hf_user"],
        )


def rodar(
    conn: sqlite3.Connection,
    cliente: ClienteHF,
    ids: Sequence[str],
    *,
    data_snapshot: Optional[dt.date] = None,
) -> ResultadoEnriquecimento:
    data_snapshot = data_snapshot or db.hoje()
    res = ResultadoEnriquecimento()
    agora = db.agora()

    for pid in ids:
        try:
            paper = cliente.paper(pid)
        except ErroHF as e:
            log.warning("enriquecimento falhou em %s: %s", pid, e)
            res.falhas.append(pid)
            continue

        with db.transacao(conn):
            db.upsert_paper(
                conn,
                paper_para_dim(paper, primeiro_visto_em=agora, enriquecido_em=agora),
            )
            db.upsert_metrica(
                conn,
                paper_para_metrica(paper, data_snapshot=data_snapshot, origem="por_paper"),
            )
            _atualizar_autores(conn, paper)
            for kw in paper.ai_keywords:
                if kw:
                    db.inserir_ignorando(
                        conn, "ponte_paper_keyword", {"paper_id": paper.paper_id, "keyword": kw}
                    )
        res.enriquecidos += 1

    if res.falhas:
        res.avisos.append(f"enriquecimento_falhou:{len(res.falhas)}")
    log.info("enriquecidos %s papers (%s falhas)", res.enriquecidos, len(res.falhas))
    return res
