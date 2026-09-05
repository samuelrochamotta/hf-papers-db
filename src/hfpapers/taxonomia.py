"""Governanca do vocabulario controlado - agora em codigo, nao por convencao.

Tetos (config `taxonomia`): 10 areas, 24 topicos, 5 topicos por paper, e 2
papers distintos para promover um candidato.

Promocao e automatica. **Fusao de rotulos e manual** e exige comando explicito:
vocabulario grande demais deixa de separar qualquer coisa, e escolher qual par
fundir e julgamento humano.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional, Sequence

from . import db
from .config import Taxonomia as ConfigTaxonomia
from .log import logger

log = logger("taxonomia")


@dataclass
class ResultadoCandidato:
    rotulo: str
    tipo: str
    papers: list[str]
    promovido: bool = False
    aviso: Optional[str] = None


# ── leitura ─────────────────────────────────────────────────────────────────


def areas(conn: sqlite3.Connection) -> list[str]:
    return [r["area"] for r in conn.execute("SELECT area FROM dim_area ORDER BY area")]


def topicos(conn: sqlite3.Connection) -> list[str]:
    return [r["topico"] for r in conn.execute("SELECT topico FROM dim_topico ORDER BY topico")]


def _tabela(tipo: str) -> tuple[str, str]:
    return ("dim_area", "area") if tipo == "area" else ("dim_topico", "topico")


def _teto(tipo: str, cfg: ConfigTaxonomia) -> int:
    return cfg.max_areas if tipo == "area" else cfg.max_topicos


def _quantidade(conn: sqlite3.Connection, tipo: str) -> int:
    tabela, _ = _tabela(tipo)
    return db.contar(conn, tabela)


# ── classificacao de um paper ───────────────────────────────────────────────


def aplicar_classificacao(
    conn: sqlite3.Connection,
    paper_id: str,
    *,
    area_primaria: str,
    areas_secundarias: Sequence[str] = (),
    topicos_paper: Sequence[str] = (),
    cfg: Optional[ConfigTaxonomia] = None,
) -> None:
    """Reescreve as pontes de um paper. Rotulo desconhecido e ignorado com aviso
    - a LLM nao cria vocabulario, e o enum ja deveria ter impedido isso."""
    cfg = cfg or ConfigTaxonomia()
    validos_area = set(areas(conn))
    validos_topico = set(topicos(conn))

    conn.execute("DELETE FROM ponte_paper_area WHERE paper_id = ?", (paper_id,))
    conn.execute("DELETE FROM ponte_paper_topico WHERE paper_id = ?", (paper_id,))

    if area_primaria in validos_area:
        db.inserir_ignorando(
            conn,
            "ponte_paper_area",
            {"paper_id": paper_id, "area": area_primaria, "is_primaria": 1},
        )
    elif area_primaria:
        log.warning("area desconhecida ignorada em %s: %s", paper_id, area_primaria)

    for a in areas_secundarias:
        if a in validos_area and a != area_primaria:
            db.inserir_ignorando(
                conn, "ponte_paper_area", {"paper_id": paper_id, "area": a, "is_primaria": 0}
            )

    for t in list(dict.fromkeys(topicos_paper))[: cfg.max_topicos_por_paper]:
        if t in validos_topico:
            db.inserir_ignorando(conn, "ponte_paper_topico", {"paper_id": paper_id, "topico": t})
        elif t:
            log.warning("topico desconhecido ignorado em %s: %s", paper_id, t)


# ── candidatos ──────────────────────────────────────────────────────────────


def registrar_candidato(
    conn: sqlite3.Connection,
    *,
    rotulo: str,
    tipo: str,
    definicao: str,
    paper_id: str,
    cfg: Optional[ConfigTaxonomia] = None,
) -> ResultadoCandidato:
    """Acrescenta o paper ao candidato e promove quando houver quorum e folga."""
    cfg = cfg or ConfigTaxonomia()
    rotulo = (rotulo or "").strip()
    if not rotulo or tipo not in ("area", "topico"):
        return ResultadoCandidato(rotulo, tipo, [], aviso="candidato_invalido")

    tabela, coluna = _tabela(tipo)
    ja_existe = conn.execute(
        f"SELECT 1 FROM {tabela} WHERE {coluna} = ?", (rotulo,)
    ).fetchone()
    if ja_existe:
        return ResultadoCandidato(rotulo, tipo, [], aviso=None)

    row = conn.execute(
        "SELECT papers, promovido FROM tax_candidato WHERE rotulo = ? AND tipo = ?",
        (rotulo, tipo),
    ).fetchone()
    papers = json.loads(row["papers"]) if row else []
    if paper_id not in papers:
        papers.append(paper_id)

    db.upsert_candidato(
        conn,
        {
            "rotulo": rotulo,
            "tipo": tipo,
            "definicao": definicao,
            "papers": json.dumps(papers, ensure_ascii=False),
            "promovido": int(bool(row["promovido"])) if row else 0,
            "criado_em": db.agora(),
        },
    )

    res = ResultadoCandidato(rotulo, tipo, papers)
    if len(papers) < cfg.min_papers_novo_rotulo:
        return res

    if _quantidade(conn, tipo) >= _teto(tipo, cfg):
        res.aviso = f"teto_vocabulario:{tipo}:{rotulo}"
        log.warning(
            "candidato '%s' com quorum mas teto de %s atingido - fusao manual necessaria",
            rotulo, tipo,
        )
        return res

    promover(conn, rotulo=rotulo, tipo=tipo, definicao=definicao)
    res.promovido = True
    log.info("candidato promovido a %s: %s", tipo, rotulo)
    return res


def promover(
    conn: sqlite3.Connection, *, rotulo: str, tipo: str, definicao: str
) -> None:
    tabela, coluna = _tabela(tipo)
    db.upsert(
        conn,
        tabela,
        {coluna: rotulo, "definicao": definicao, "desde": db.hoje().isoformat()},
        chave=[coluna],
    )
    conn.execute(
        "UPDATE tax_candidato SET promovido = 1 WHERE rotulo = ? AND tipo = ?",
        (rotulo, tipo),
    )


# ── fusao (manual) ──────────────────────────────────────────────────────────


def fundir(conn: sqlite3.Connection, *, de: str, para: str, tipo: str) -> dict[str, int]:
    """Reescreve as pontes de `de` para `para` e apaga o rotulo `de`."""
    tabela, coluna = _tabela(tipo)
    ponte = "ponte_paper_area" if tipo == "area" else "ponte_paper_topico"

    for rotulo in (de, para):
        if not conn.execute(f"SELECT 1 FROM {tabela} WHERE {coluna} = ?", (rotulo,)).fetchone():
            raise ValueError(f"{tipo} inexistente: {rotulo}")

    with db.transacao(conn):
        if tipo == "area":
            # o paper pode ja ter a area de destino: nesse caso a primaria vence
            conn.execute(
                "UPDATE OR IGNORE ponte_paper_area SET area = ? WHERE area = ?", (para, de)
            )
            conn.execute("DELETE FROM ponte_paper_area WHERE area = ?", (de,))
        else:
            conn.execute(
                "UPDATE OR IGNORE ponte_paper_topico SET topico = ? WHERE topico = ?",
                (para, de),
            )
            conn.execute("DELETE FROM ponte_paper_topico WHERE topico = ?", (de,))
        movidos = conn.execute(
            f"SELECT COUNT(*) AS n FROM {ponte} WHERE {coluna} = ?", (para,)
        ).fetchone()["n"]
        conn.execute(f"DELETE FROM {tabela} WHERE {coluna} = ?", (de,))

    log.info("fusao %s: '%s' -> '%s' (%s papers no destino)", tipo, de, para, movidos)
    return {"papers_no_destino": int(movidos)}


# ── bootstrap do vocabulario ────────────────────────────────────────────────
#
# O vocabulario vivo mora no banco, e o banco nao esta versionado. `exportar` o
# retrata num JSON que entra no git (`config/taxonomia_inicial.json`) e
# `carregar` o repoe num banco novo - e so isso: nao e migracao nem sincronia.
# Candidato nao entra no arquivo porque candidato e fila de promocao, estado de
# uma base especifica, e nao vocabulario vigente.


def exportar(conn: sqlite3.Connection) -> dict[str, Any]:
    """dim_area / dim_topico -> dicionario serializavel (rotulo e definicao).

    `desde` fica de fora de proposito: num banco novo a data em que o rotulo
    passou a valer e a da carga, nao a do banco de origem.
    """
    return {
        "areas": [
            {"rotulo": r["area"], "definicao": r["definicao"] or ""}
            for r in conn.execute("SELECT area, definicao FROM dim_area ORDER BY area")
        ],
        "topicos": [
            {"rotulo": r["topico"], "definicao": r["definicao"] or ""}
            for r in conn.execute("SELECT topico, definicao FROM dim_topico ORDER BY topico")
        ],
    }


def carregar(conn: sqlite3.Connection, dados: dict[str, Any]) -> dict[str, int]:
    """Inverso de `exportar`, para banco sem vocabulario. Idempotente.

    Rotulo que ja existe nao e tocado: a definicao viva do banco ganha da do
    arquivo, que e um retrato de outro momento. Por isso `INSERT OR IGNORE` e
    nao upsert - rodar duas vezes nao muda nada e nao desfaz fusao nenhuma.
    """
    desde = db.hoje().isoformat()
    contagem = {"areas": 0, "topicos": 0, "ja_existiam": 0}
    for chave, tabela, coluna in (
        ("areas", "dim_area", "area"),
        ("topicos", "dim_topico", "topico"),
    ):
        for item in dados.get(chave) or []:
            rotulo = (item.get("rotulo") or "").strip()
            if not rotulo:
                log.warning("entrada sem rotulo ignorada em %s", chave)
                continue
            entrou = db.inserir_ignorando(
                conn,
                tabela,
                {coluna: rotulo, "definicao": item.get("definicao") or "", "desde": desde},
            )
            if entrou:
                contagem[chave] += 1
            else:
                contagem["ja_existiam"] += 1
    return contagem


def listar(conn: sqlite3.Connection, cfg: Optional[ConfigTaxonomia] = None) -> dict[str, Any]:
    cfg = cfg or ConfigTaxonomia()
    def _com_uso(tabela: str, coluna: str, ponte: str) -> list[dict]:
        return [
            dict(r)
            for r in conn.execute(
                f"SELECT d.{coluna} AS rotulo, d.definicao, d.desde, "
                f"       (SELECT COUNT(*) FROM {ponte} p WHERE p.{coluna} = d.{coluna}) AS papers "
                f"FROM {tabela} d ORDER BY papers DESC, rotulo"
            )
        ]

    return {
        "areas": _com_uso("dim_area", "area", "ponte_paper_area"),
        "topicos": _com_uso("dim_topico", "topico", "ponte_paper_topico"),
        "candidatos": [
            {**dict(r), "papers": json.loads(r["papers"])}
            for r in conn.execute(
                "SELECT rotulo, tipo, definicao, papers, promovido FROM tax_candidato "
                "ORDER BY promovido, rotulo"
            )
        ],
        "tetos": {"areas": cfg.max_areas, "topicos": cfg.max_topicos},
    }
