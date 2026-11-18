"""Leitura do texto completo dos papers (painel v2, ADR 007).

`texto` baixa e limpa o HTML do arXiv, `extrator` chama o Haiku 5.5 e confere
a copia, `derivar` faz as contas. `rodar` amarra os tres para o comando
`hfpapers ler`.
"""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from .. import db
from ..config import Config, config
from ..log import logger
from . import extrator, texto

log = logger("leitura")

# O arXiv pede no maximo uma requisicao a cada 3 s para clientes automaticos.
INTERVALO_ARXIV_S = 3.0


@dataclass
class ResultadoLeitura:
    run_id: str
    lidos: list[str] = field(default_factory=list)
    falhas: dict[str, str] = field(default_factory=dict)
    custo_usd: float = 0.0
    so_abstract: list[str] = field(default_factory=list)


def candidatos(
    conn: sqlite3.Connection,
    cfg: Config,
    *,
    dias: int,
    min_votos: int,
    ids: Sequence[str] | None = None,
    refazer: bool = False,
    hoje: dt.date | None = None,
) -> list[dict]:
    """Papers do HF Daily na janela, do mais votado para o menos votado."""
    hoje = hoje or dt.date.today()
    filtros, params = [], []
    if ids:
        filtros.append(f"p.paper_id IN ({','.join('?' * len(ids))})")
        params += list(ids)
    else:
        filtros.append("p.data_hf_daily >= ?")
        params.append((hoje - dt.timedelta(days=dias)).isoformat())
    if not refazer:
        filtros.append(
            "NOT EXISTS (SELECT 1 FROM leitura_texto l WHERE l.paper_id = p.paper_id "
            "AND l.versao_esquema = ?)"
        )
        params.append(cfg.leitura.versao_esquema)
    sql = f"""
        SELECT p.paper_id, p.titulo, p.abstract, p.data_hf_daily,
               (SELECT m.upvotes FROM fato_metrica m WHERE m.paper_id = p.paper_id
                ORDER BY m.data_snapshot DESC LIMIT 1) AS upvotes
        FROM dim_paper p
        WHERE {" AND ".join(filtros)}
    """
    linhas = [dict(r) for r in conn.execute(sql, params)]
    linhas = [l for l in linhas if (l["upvotes"] or 0) >= min_votos or ids]
    return sorted(linhas, key=lambda l: (-(l["upvotes"] or 0), l["paper_id"]))


def gravar(
    conn: sqlite3.Connection, cfg: Config, lt: extrator.Leitura, fonte: str
) -> None:
    c = lt.conferencia
    with db.transacao(conn):
        conn.execute(
            """INSERT OR REPLACE INTO leitura_texto
               (paper_id, versao_esquema, modelo, fonte, cobertura, caracteres, trechos,
                trechos_ok, numeros, numeros_ok, extracao, avisos, tokens_entrada,
                tokens_saida, custo_usd, lido_em)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                lt.arxiv_id,
                cfg.leitura.versao_esquema,
                lt.modelo,
                fonte,
                lt.dados.get("leitura", {}).get("cobertura", "parcial"),
                lt.caracteres,
                c["trechos"],
                c["trechos_ok"],
                c["numeros"],
                c["numeros_ok"],
                json.dumps(lt.dados, ensure_ascii=False),
                json.dumps(lt.avisos, ensure_ascii=False),
                lt.tokens_entrada,
                lt.tokens_saida,
                lt.custo_usd,
                db.agora(),
            ),
        )


def rodar(
    conn: sqlite3.Connection,
    cfg: Config | None = None,
    *,
    dias: int | None = None,
    limite: int | None = None,
    min_votos: int | None = None,
    ids: Sequence[str] | None = None,
    refazer: bool = False,
    cliente: Any = None,
    http: Any = None,
) -> ResultadoLeitura:
    cfg = cfg or config()
    lc = cfg.leitura
    run_id = f"leitura-{dt.datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
    res = ResultadoLeitura(run_id)
    fila = candidatos(
        conn,
        cfg,
        dias=dias if dias is not None else lc.dias,
        min_votos=min_votos if min_votos is not None else lc.min_votos,
        ids=ids,
        refazer=refazer,
    )
    if limite:
        fila = fila[:limite]
    if not fila:
        log.info("nada a ler")
        return res
    cliente = cliente or extrator.cliente_llm(cfg, conn=conn, run_id=run_id)
    esquema = extrator.carregar_esquema(cfg)
    ultimo_get = 0.0
    for i, p in enumerate(fila, 1):
        pid = p["paper_id"]
        espera = INTERVALO_ARXIV_S - (time.monotonic() - ultimo_get)
        if espera > 0 and http is None:
            time.sleep(espera)
        try:
            ultimo_get = time.monotonic()
            tp = texto.texto_do_paper(
                pid,
                abstract=p.get("abstract") or "",
                teto=lc.teto_caracteres,
                cliente=http,
            )
            lt = extrator.extrair(
                tp, {"titulo": p["titulo"]}, cliente=cliente, cfg=cfg, esquema=esquema
            )
            gravar(conn, cfg, lt, tp.fonte)
        except Exception as e:  # noqa: BLE001 - um paper ruim nao para a rodada
            res.falhas[pid] = f"{type(e).__name__}: {e}"
            log.warning("[%s/%s] %s falhou: %s", i, len(fila), pid, type(e).__name__)
            continue
        res.lidos.append(pid)
        res.custo_usd += lt.custo_usd
        if tp.fonte == "abstract":
            res.so_abstract.append(pid)
        c = lt.conferencia
        log.info(
            "[%s/%s] %s %s, %s mil caracteres, trechos %s/%s, numeros %s/%s, US$ %.4f",
            i,
            len(fila),
            pid,
            lt.dados["leitura"]["cobertura"],
            lt.caracteres // 1000,
            c["trechos_ok"],
            c["trechos"],
            c["numeros_ok"],
            c["numeros"],
            lt.custo_usd,
        )
    return res
