"""Estagio 5 - EXPORT: materializa os Parquet que o painel le.

Os Parquet sao o contrato de `scripts/gerar_painel.py`, e de mais ninguem
(ADR 008): sai a tabela e a coluna que o painel le, e so. Dado que o painel nao
mostra fica no banco, que e a fonte. Coluna nova no painel comeca aqui.

Tres regras que valem para o arquivo inteiro:

* datas saem como `date32`, nunca string - o painel faz aritmetica de data
  (janela, trimestre do registro historico) sobre o que le;
* nada e pre-agregado: o grao fino vai inteiro e a agregacao e papel do painel;
* escrita atomica (`os.replace`), porque o painel pode estar lendo o arquivo
  na hora do export. O `_manifest.json` sai por ultimo: e ele que acorda o
  launchd do painel.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import os
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from ..config import Config, config
from ..log import logger

log = logger("export")


@dataclass
class ResultadoExport:
    dir_saida: Path = Path(".")
    arquivos: dict[str, int] = field(default_factory=dict)
    manifest: Path | None = None


# ── conversores ─────────────────────────────────────────────────────────────


def _d(v: Any) -> dt.date | None:
    if v in (None, ""):
        return None
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    try:
        return dt.date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def _b(v: Any) -> bool | None:
    return None if v is None else bool(v)


# ── escrita ─────────────────────────────────────────────────────────────────


def _escrever(
    dir_saida: Path, nome: str, linhas: list[dict], schema: pa.Schema, *, csv_tambem: bool
) -> int:
    colunas = {c: [linha.get(c) for linha in linhas] for c in schema.names}
    tabela = pa.Table.from_pydict(colunas, schema=schema)

    destino = dir_saida / f"{nome}.parquet"
    tmp = destino.with_suffix(".parquet.tmp")
    pq.write_table(tabela, tmp, compression="snappy")
    os.replace(tmp, destino)   # atomico no mesmo volume, inclusive no Windows

    if csv_tambem:
        destino_csv = dir_saida / f"{nome}.csv"
        tmp_csv = destino_csv.with_suffix(".csv.tmp")
        with open(tmp_csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=schema.names)
            w.writeheader()
            for linha in linhas:
                w.writerow({c: linha.get(c) for c in schema.names})
        os.replace(tmp_csv, destino_csv)

    log.info("%s: %s linhas", destino.name, len(linhas))
    return len(linhas)


def _rows(conn: sqlite3.Connection, sql: str, params: Sequence = ()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params)]


# ── tabelas ─────────────────────────────────────────────────────────────────
#
# `_escrever` monta as colunas a partir dos nomes do schema: coluna fora do
# schema nao sai, mesmo que a consulta a traga.


def _dim_paper(conn: sqlite3.Connection) -> tuple[list[dict], pa.Schema]:
    """O paper com o ultimo valor nao nulo de cada metrica, que e o que o card
    e a ordenacao por voto mostram."""
    brutas = _rows(
        conn,
        """
        SELECT p.*,
               (SELECT m.upvotes FROM fato_metrica m
                 WHERE m.paper_id = p.paper_id AND m.upvotes IS NOT NULL
                 ORDER BY m.data_snapshot DESC LIMIT 1)      AS upvotes_atual,
               (SELECT m.github_stars FROM fato_metrica m
                 WHERE m.paper_id = p.paper_id AND m.github_stars IS NOT NULL
                 ORDER BY m.data_snapshot DESC LIMIT 1)      AS github_stars_atual,
               (SELECT m.comentarios FROM fato_metrica m
                 WHERE m.paper_id = p.paper_id AND m.comentarios IS NOT NULL
                 ORDER BY m.data_snapshot DESC LIMIT 1)      AS comentarios_atual
          FROM dim_paper p
        """,
    )
    linhas = [
        {
            **r,
            "data_hf_daily": _d(r["data_hf_daily"]),
            "tem_project_page": bool(r["project_page"]),
        }
        for r in brutas
    ]
    schema = pa.schema(
        [
            ("paper_id", pa.string()),
            ("titulo", pa.string()),
            ("data_hf_daily", pa.date32()),
            ("url_hf", pa.string()),
            ("project_page", pa.string()),
            ("github_repo", pa.string()),
            ("tem_project_page", pa.bool_()),
            ("organizacao", pa.string()),
            ("qtd_autores", pa.int32()),
            ("qtd_autores_verificados", pa.int32()),
            ("upvotes_atual", pa.int32()),
            ("comentarios_atual", pa.int32()),
            ("github_stars_atual", pa.int32()),
        ]
    )
    return linhas, schema


def _fato_metrica(conn: sqlite3.Connection) -> tuple[list[dict], pa.Schema]:
    """Grao fino, um snapshot por linha: os votos de cada dia, que o painel
    agrega, e a data da ultima medicao do registro historico."""
    linhas = [
        {**r, "data_snapshot": _d(r["data_snapshot"])}
        for r in _rows(conn, "SELECT * FROM fato_metrica ORDER BY paper_id, data_snapshot")
    ]
    schema = pa.schema(
        [
            ("paper_id", pa.string()),
            ("data_snapshot", pa.date32()),
            ("upvotes", pa.int32()),
        ]
    )
    return linhas, schema


def _fato_triagem(conn: sqlite3.Connection) -> tuple[list[dict], pa.Schema]:
    """A triagem do regime do ADR 004. `artefato_aberto` vem de `vw_artefato`,
    a unica fonte da regra, para o painel nao reimplementa-la."""
    linhas = [
        {**r, "artefato_aberto": _b(r["artefato_aberto"])}
        for r in _rows(
            conn,
            "SELECT t.*, a.artefato_aberto FROM fato_triagem t "
            "LEFT JOIN vw_artefato a ON a.paper_id = t.paper_id",
        )
    ]
    schema = pa.schema(
        [
            ("paper_id", pa.string()),
            ("veredito", pa.string()),
            ("regra_fora", pa.string()),
            ("justificativa", pa.string()),
            ("natureza", pa.string()),
            ("pratica_contradita", pa.string()),
            ("falta_o_como", pa.string()),
            ("artefato_aberto", pa.bool_()),
        ]
    )
    return linhas, schema


def _simples(conn: sqlite3.Connection, tabela: str, schema: pa.Schema) -> tuple[list[dict], pa.Schema]:
    return _rows(conn, f"SELECT * FROM {tabela}"), schema


_SCHEMAS_SIMPLES = {
    "dim_ficha": pa.schema(
        [
            ("paper_id", pa.string()),
            ("achado", pa.string()),
            ("implicacao_pratica", pa.string()),
            ("exemplo_concreto", pa.string()),
            ("ressalva", pa.string()),
        ]
    ),
    # `area_pai` e o que faz a dimensao ser hierarquica: sem ela os dois niveis
    # chegam ao painel como uma lista plana de rotulos, sem dizer qual e area
    # raiz (pai nulo) nem de quem cada sub-area e filha.
    "dim_area": pa.schema(
        [("area", pa.string()), ("area_pai", pa.string()), ("definicao", pa.string())]
    ),
    "dim_vertente": pa.schema([("vertente", pa.string()), ("definicao", pa.string())]),
    "ponte_paper_area": pa.schema(
        [
            ("paper_id", pa.string()),
            ("area", pa.string()),
            ("subarea", pa.string()),
            ("is_primaria", pa.bool_()),
        ]
    ),
    # `ordem` separa a vertente dominante (1) da secundaria (2): e a dominante
    # que o card exibe primeiro.
    "ponte_paper_vertente": pa.schema(
        [("paper_id", pa.string()), ("vertente", pa.string()), ("ordem", pa.int32())]
    ),
    # `ordem` e a unica copia da ordenacao das naturezas (ADR 004).
    "dim_natureza": pa.schema(
        [
            ("natureza", pa.string()),
            ("rotulo", pa.string()),
            ("definicao", pa.string()),
            ("ordem", pa.int32()),
        ]
    ),
}


# Versao do contrato dos Parquet: 2 no ADR 004 (sai estrito/amplo e a ponte de
# criterios; entram natureza, pre-requisito e perfis); 3 no ADR 005 (saem as
# tabelas sem leitor); 4 no ADR 008 (o Parquet passa a ser so o que o painel le).
VERSAO_SCHEMA = 4

# Tabelas que deixaram de existir. O export so escreve, nao apaga: sem esta
# lista o Parquet antigo ficaria em `marts/` parecendo vigente. As tabelas
# seguem no banco; so o Parquet deixa de existir.
ARQUIVOS_MORTOS = {
    "ponte_paper_criterio": "ADR 004",
    "dim_calendario": "ADR 005",
    "dim_prerequisito": "ADR 005",
    "dim_perfil": "ADR 005",
    "ponte_perfil_prerequisito": "ADR 005",
    "ponte_paper_perfil": "ADR 005",
    "fato_execucao": "ADR 008",
    "ponte_paper_keyword": "ADR 008",
    "ponte_paper_autor": "ADR 008",
}


def _apagar_mortos(dir_saida: Path) -> None:
    for nome, adr in ARQUIVOS_MORTOS.items():
        for ext in (".parquet", ".csv"):
            caminho = dir_saida / f"{nome}{ext}"
            if caminho.exists():
                caminho.unlink()
                log.warning("%s removido: a tabela saiu no %s", caminho.name, adr)


# ── entrada ─────────────────────────────────────────────────────────────────


def rodar(
    conn: sqlite3.Connection,
    cfg: Config | None = None,
    *,
    run_id: str | None = None,
) -> ResultadoExport:
    cfg = cfg or config()
    dir_saida = cfg.dir_marts
    dir_saida.mkdir(parents=True, exist_ok=True)
    res = ResultadoExport(dir_saida=dir_saida)
    csv_tambem = cfg.export.csv

    tabelas: list[tuple[str, tuple[list[dict], pa.Schema]]] = [
        ("dim_paper", _dim_paper(conn)),
        ("fato_metrica", _fato_metrica(conn)),
        ("fato_triagem", _fato_triagem(conn)),
    ]
    for nome, schema in _SCHEMAS_SIMPLES.items():
        linhas, sch = _simples(conn, nome, schema)
        if nome == "ponte_paper_area":
            linhas = [{**linha, "is_primaria": _b(linha["is_primaria"])} for linha in linhas]
        tabelas.append((nome, (linhas, sch)))

    for nome, (linhas, schema) in tabelas:
        res.arquivos[nome] = _escrever(dir_saida, nome, linhas, schema, csv_tambem=csv_tambem)
    _apagar_mortos(dir_saida)

    if run_id is None:
        row = conn.execute(
            "SELECT run_id FROM log_execucao ORDER BY iniciado_em DESC LIMIT 1"
        ).fetchone()
        run_id = row["run_id"] if row else None

    manifest = {
        "versao_schema": VERSAO_SCHEMA,
        "gerado_em": dt.datetime.now().replace(microsecond=0).isoformat(),
        "run_id": run_id,
        "banco": str(cfg.caminho_banco),
        "linhas": res.arquivos,
    }
    caminho_manifest = dir_saida / "_manifest.json"
    tmp = caminho_manifest.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, caminho_manifest)
    res.manifest = caminho_manifest
    return res
