"""Estagio 4 - REFRESH escalonado das metricas vivas.

A descoberta que define a estrategia (secao 2.3): re-consultar
`daily_papers?date=` de uma data antiga devolve as metricas ATUAIS. Entao
atualizar ~35 papers custa 1 requisicao, nao 35. Janela quente de 30 dias
custa ~22 requisicoes/dia em vez de ~1.000.

`papers/{id}` fica so para os `numTotal*`, que mudam devagar - semanalmente.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from dataclasses import dataclass, field
from typing import Optional

from .. import db
from ..config import Refresh as ConfigRefresh
from ..fontes.hf_client import ClienteHF, ErroHF
from ..log import logger
from . import coleta, enriquecimento

log = logger("refresh")


@dataclass
class ResultadoRefresh:
    datas_quentes: list[dt.date] = field(default_factory=list)
    datas_mornas: list[dt.date] = field(default_factory=list)
    papers_atualizados: int = 0
    papers_enriquecidos: int = 0
    requisicoes: int = 0
    avisos: list[str] = field(default_factory=list)


def datas_na_janela(
    conn: sqlite3.Connection, *, de: dt.date, ate: dt.date
) -> list[dt.date]:
    """Datas `data_hf_daily` distintas com paper na base, no intervalo fechado."""
    cur = conn.execute(
        "SELECT DISTINCT data_hf_daily AS d FROM dim_paper "
        "WHERE data_hf_daily IS NOT NULL AND data_hf_daily BETWEEN ? AND ? "
        "ORDER BY d",
        (de.isoformat(), ate.isoformat()),
    )
    return [dt.date.fromisoformat(str(r["d"])[:10]) for r in cur]


def ids_na_janela(conn: sqlite3.Connection, *, de: dt.date, ate: dt.date) -> list[str]:
    cur = conn.execute(
        "SELECT paper_id FROM dim_paper "
        "WHERE data_hf_daily IS NOT NULL AND data_hf_daily BETWEEN ? AND ? "
        "ORDER BY data_hf_daily DESC",
        (de.isoformat(), ate.isoformat()),
    )
    return [r["paper_id"] for r in cur]


def _atualizar_datas(
    conn: sqlite3.Connection,
    cliente: ClienteHF,
    datas: list[dt.date],
    *,
    hoje: dt.date,
    res: ResultadoRefresh,
) -> None:
    for data in datas:
        try:
            itens = cliente.daily_papers(data)
        except ErroHF as e:
            log.warning("refresh falhou em %s: %s", data, e)
            res.avisos.append(f"refresh_falhou:{data.isoformat()}")
            continue
        res.requisicoes += 1
        if not itens:
            continue
        with db.transacao(conn):
            coleta.gravar_itens(conn, itens, data_snapshot=hoje, origem="daily")
        res.papers_atualizados += len(itens)


def rodar(
    conn: sqlite3.Connection,
    cliente: ClienteHF,
    cfg: ConfigRefresh,
    *,
    hoje: Optional[dt.date] = None,
    forcar_semanal: bool = False,
) -> ResultadoRefresh:
    hoje = hoje or db.hoje()
    res = ResultadoRefresh()
    eh_segunda = hoje.isoweekday() == 1 or forcar_semanal

    inicio_quente = hoje - dt.timedelta(days=cfg.janela_quente_dias)
    res.datas_quentes = datas_na_janela(conn, de=inicio_quente, ate=hoje)
    _atualizar_datas(conn, cliente, res.datas_quentes, hoje=hoje, res=res)

    if eh_segunda:
        inicio_morno = hoje - dt.timedelta(days=cfg.janela_morna_dias)
        res.datas_mornas = datas_na_janela(
            conn, de=inicio_morno, ate=inicio_quente - dt.timedelta(days=1)
        )
        _atualizar_datas(conn, cliente, res.datas_mornas, hoje=hoje, res=res)

        if cfg.enriquecimento_semanal:
            ids = ids_na_janela(conn, de=inicio_quente, ate=hoje)
            r = enriquecimento.rodar(conn, cliente, ids, data_snapshot=hoje)
            res.papers_enriquecidos = r.enriquecidos
            res.avisos.extend(r.avisos)

    log.info(
        "refresh: %s datas quentes, %s mornas, %s papers, %s enriquecidos",
        len(res.datas_quentes), len(res.datas_mornas),
        res.papers_atualizados, res.papers_enriquecidos,
    )
    return res
