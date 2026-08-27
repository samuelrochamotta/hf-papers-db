"""Estagio 1 - COLETA: busca dias novos no HF e insere papers ineditos.

O dia que organiza a operacao e `paper.submittedOnDailyAt`, nao `publishedAt`:
no lote de 25/08 as duas datas divergiram em 35 de 35 papers.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from dataclasses import dataclass, field
from typing import Iterable, Optional, Sequence

from .. import db
from ..fontes.hf_client import ClienteHF, ErroHF
from ..fontes.modelos import ItemDiario, paper_para_dim, paper_para_metrica
from ..log import logger

log = logger("coleta")


@dataclass
class ResultadoColeta:
    dias: list[dt.date] = field(default_factory=list)
    coletados: int = 0
    novos: list[str] = field(default_factory=list)
    ja_vistos: int = 0
    avisos: list[str] = field(default_factory=list)
    por_dia: dict[str, int] = field(default_factory=dict)


# ── quais dias buscar ───────────────────────────────────────────────────────


def dias_faltantes(
    conn: sqlite3.Connection, *, hoje: Optional[dt.date] = None, limite: int = 30
) -> list[dt.date]:
    """Do ultimo dia coberto ate hoje. Fim de semana entra na lista mesmo assim:
    o feed simplesmente devolve vazio e isso nao e erro (secao 2.4)."""
    hoje = hoje or db.hoje()
    ultimo = db.max_data_hf(conn)
    if ultimo is None:
        return [hoje]
    dias = []
    d = ultimo + dt.timedelta(days=1)
    while d <= hoje and len(dias) < limite:
        dias.append(d)
        d += dt.timedelta(days=1)
    return dias or [hoje]


# ── gravacao ────────────────────────────────────────────────────────────────


def _gravar_pontes(conn: sqlite3.Connection, item_paper) -> None:
    pid = item_paper.paper_id
    conn.execute("DELETE FROM ponte_paper_autor WHERE paper_id = ?", (pid,))
    for ordem, autor in enumerate(item_paper.authors, start=1):
        if not autor.name:
            continue
        db.inserir_ignorando(
            conn,
            "ponte_paper_autor",
            {
                "paper_id": pid,
                "ordem": ordem,
                "autor": autor.name,
                "hf_user": autor.hf_user,
                "verificado": int(autor.verificado),
            },
        )
    for kw in item_paper.ai_keywords:
        if kw:
            db.inserir_ignorando(
                conn, "ponte_paper_keyword", {"paper_id": pid, "keyword": kw}
            )


def gravar_itens(
    conn: sqlite3.Connection,
    itens: Sequence[ItemDiario],
    *,
    data_snapshot: Optional[dt.date] = None,
    origem: str = "daily",
) -> tuple[list[str], int]:
    """Upsert de dim_paper + metrica do dia + pontes. Devolve (ids novos, ja vistos)."""
    data_snapshot = data_snapshot or db.hoje()
    agora = db.agora()
    ids = [i.paper.paper_id for i in itens]
    existentes = db.ids_existentes(conn, ids)
    novos: list[str] = []

    for item in itens:
        p = item.paper
        if p.paper_id not in existentes:
            novos.append(p.paper_id)
        db.upsert_paper(
            conn, paper_para_dim(p, item=item, primeiro_visto_em=agora)
        )
        db.upsert_metrica(
            conn,
            paper_para_metrica(
                p, data_snapshot=data_snapshot, origem=origem, comentarios=item.numComments
            ),
        )
        _gravar_pontes(conn, p)

    return novos, len(itens) - len(novos)


# ── estagio ─────────────────────────────────────────────────────────────────


def rodar(
    conn: sqlite3.Connection,
    cliente: ClienteHF,
    *,
    datas: Optional[Iterable[dt.date]] = None,
    hoje: Optional[dt.date] = None,
    coletados_min_dia_util: int = 15,
) -> ResultadoColeta:
    hoje = hoje or db.hoje()
    lista = list(datas) if datas is not None else dias_faltantes(conn, hoje=hoje)
    res = ResultadoColeta(dias=lista)

    if datas is None and len(lista) > 1:
        res.avisos.append(
            "lacuna_recuperada: " + ", ".join(d.isoformat() for d in lista)
        )

    for data in lista:
        try:
            itens = cliente.daily_papers(data)
        except ErroHF as e:
            log.error("coleta falhou em %s: %s", data, e)
            res.avisos.append(f"coleta_falhou:{data.isoformat()}")
            continue

        res.por_dia[data.isoformat()] = len(itens)
        res.coletados += len(itens)
        dia_util = data.isoweekday() <= 5
        if dia_util and 0 < len(itens) < coletados_min_dia_util:
            res.avisos.append(f"coleta_suspeita:{data.isoformat()}:{len(itens)}")
        if not itens:
            log.info("%s sem papers%s", data, "" if dia_util else " (fim de semana, normal)")
            continue

        with db.transacao(conn):
            novos, ja_vistos = gravar_itens(conn, itens, data_snapshot=hoje)
            db.popular_calendario(conn, min(lista), hoje)
        res.novos.extend(novos)
        res.ja_vistos += ja_vistos
        log.info("%s: %s coletados, %s novos", data, len(itens), len(novos))

    return res
