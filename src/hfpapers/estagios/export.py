"""Estagio 5 - EXPORT: materializa os Parquet que o Power BI le.

Tres regras que valem para o arquivo inteiro:

* datas saem como `date32`, nunca string - senao o relacionamento com
  `dim_calendario` nao fecha no Power BI;
* nada e pre-agregado: o grao fino vai inteiro e a agregacao e papel do DAX;
* escrita atomica (`os.replace`), porque o Power BI pode estar com o arquivo
  aberto na hora do export.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

import pyarrow as pa
import pyarrow.parquet as pq

from .. import db
from ..config import Config, config
from ..log import logger

log = logger("export")


@dataclass
class ResultadoExport:
    dir_saida: Path = Path(".")
    arquivos: dict[str, int] = field(default_factory=dict)
    manifest: Path | None = None


# ── conversores ─────────────────────────────────────────────────────────────


def _d(v: Any) -> Optional[dt.date]:
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


def _ts(v: Any) -> Optional[dt.datetime]:
    if v in (None, ""):
        return None
    if isinstance(v, dt.datetime):
        return v
    try:
        return dt.datetime.fromisoformat(str(v))
    except ValueError:
        return None


def _b(v: Any) -> Optional[bool]:
    return None if v is None else bool(v)


def faixa_upvotes(valor: Optional[int], bordas: Sequence[int]) -> str:
    """Bucket textual pronto para slicer: 0 | 1-9 | 10-49 | 50-99 | 100+."""
    if valor is None:
        return "sem dado"
    if valor < bordas[0]:
        return "0"
    for i, b in enumerate(bordas):
        proximo = bordas[i + 1] if i + 1 < len(bordas) else None
        if proximo is None:
            return f"{b}+"
        if valor < proximo:
            return f"{b}-{proximo - 1}"
    return f"{bordas[-1]}+"


# ── escrita ─────────────────────────────────────────────────────────────────


def _escrever(
    dir_saida: Path, nome: str, linhas: list[dict], schema: pa.Schema, *, csv_tambem: bool
) -> int:
    colunas = {c: [l.get(c) for l in linhas] for c in schema.names}
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
            for l in linhas:
                w.writerow({c: l.get(c) for c in schema.names})
        os.replace(tmp_csv, destino_csv)

    log.info("%s: %s linhas", destino.name, len(linhas))
    return len(linhas)


def _rows(conn: sqlite3.Connection, sql: str, params: Sequence = ()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params)]


# ── tabelas ─────────────────────────────────────────────────────────────────


def _dim_paper(conn: sqlite3.Connection, cfg: Config, hoje: dt.date) -> tuple[list[dict], pa.Schema]:
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
    linhas = []
    for r in brutas:
        data_hf = _d(r["data_hf_daily"])
        linhas.append(
            {
                **r,
                "data_arxiv": _d(r["data_arxiv"]),
                "data_hf_daily": data_hf,
                "primeiro_visto_em": _ts(r["primeiro_visto_em"]),
                "enriquecido_em": _ts(r["enriquecido_em"]),
                "tem_codigo_aberto": _b(r["tem_codigo_aberto"]),
                "tem_project_page": bool(r["project_page"]),
                "autor_participa": _b(r["autor_participa"]),
                "dias_desde_publicacao": (hoje - data_hf).days if data_hf else None,
                "faixa_upvotes_atual": faixa_upvotes(
                    r["upvotes_atual"], cfg.export.faixas_upvotes
                ),
            }
        )
    schema = pa.schema(
        [
            ("paper_id", pa.string()),
            ("titulo", pa.string()),
            ("abstract", pa.string()),
            ("ai_summary", pa.string()),
            ("ai_summary_model", pa.string()),
            ("data_arxiv", pa.date32()),
            ("data_hf_daily", pa.date32()),
            ("url_arxiv", pa.string()),
            ("url_hf", pa.string()),
            ("project_page", pa.string()),
            ("github_repo", pa.string()),
            ("github_repo_added_by", pa.string()),
            ("tem_codigo_aberto", pa.bool_()),
            ("tem_project_page", pa.bool_()),
            ("discussion_id", pa.string()),
            ("thumbnail_url", pa.string()),
            ("organizacao", pa.string()),
            ("organizacao_nome_longo", pa.string()),
            ("submetido_por", pa.string()),
            ("submetido_por_nome", pa.string()),
            ("autor_participa", pa.bool_()),
            ("qtd_autores", pa.int32()),
            ("qtd_autores_verificados", pa.int32()),
            ("upvotes_atual", pa.int32()),
            ("comentarios_atual", pa.int32()),
            ("github_stars_atual", pa.int32()),
            ("faixa_upvotes_atual", pa.string()),
            ("dias_desde_publicacao", pa.int32()),
            ("primeiro_visto_em", pa.timestamp("s")),
            ("enriquecido_em", pa.timestamp("s")),
        ]
    )
    return linhas, schema


def _fato_metrica(conn: sqlite3.Connection) -> tuple[list[dict], pa.Schema]:
    """Grao fino + duas derivacoes que o Power BI nao faz bem sozinho:

    * `qtd_modelos/datasets/spaces` propagados para frente com o ultimo valor
      nao nulo - eles so vem nos snapshots `por_paper` e sem isso o grafico abre
      buraco nos dias `daily`;
    * `upvotes_delta_dia`, que e o que revela o paper pegando tracao.
    """
    brutas = _rows(
        conn, "SELECT * FROM fato_metrica ORDER BY paper_id, data_snapshot"
    )
    linhas: list[dict] = []
    ultimo: dict[str, dict[str, Any]] = {}
    for r in brutas:
        pid = r["paper_id"]
        anterior = ultimo.get(pid, {})
        linha = dict(r)
        linha["data_snapshot"] = _d(r["data_snapshot"])
        for col in ("qtd_modelos", "qtd_datasets", "qtd_spaces"):
            if linha.get(col) is None:
                linha[col] = anterior.get(col)
        if r["upvotes"] is not None and anterior.get("upvotes") is not None:
            linha["upvotes_delta_dia"] = r["upvotes"] - anterior["upvotes"]
        else:
            linha["upvotes_delta_dia"] = None
        ultimo[pid] = {
            "upvotes": r["upvotes"] if r["upvotes"] is not None else anterior.get("upvotes"),
            "qtd_modelos": linha["qtd_modelos"],
            "qtd_datasets": linha["qtd_datasets"],
            "qtd_spaces": linha["qtd_spaces"],
        }
        linhas.append(linha)

    schema = pa.schema(
        [
            ("paper_id", pa.string()),
            ("data_snapshot", pa.date32()),
            ("upvotes", pa.int32()),
            ("upvotes_delta_dia", pa.int32()),
            ("comentarios", pa.int32()),
            ("github_stars", pa.int32()),
            ("qtd_modelos", pa.int32()),
            ("qtd_datasets", pa.int32()),
            ("qtd_spaces", pa.int32()),
            ("origem", pa.string()),
        ]
    )
    return linhas, schema


def _fato_triagem(conn: sqlite3.Connection) -> tuple[list[dict], pa.Schema]:
    linhas = []
    for r in _rows(conn, "SELECT * FROM fato_triagem"):
        linhas.append(
            {
                **r,
                "tem_artefato_nomeado": _b(r["tem_artefato_nomeado"]),
                "portabilidade_aprovada": _b(r["portabilidade_aprovada"]),
                "portab_depende_nome": _b(r["portab_depende_nome"]),
                "portab_generalidade": _b(r["portab_generalidade"]),
                "decisao_fronteira": _b(r["decisao_fronteira"]),
                "fronteira_contraparte": r["fronteira_contraparte"],
                "aprovado": r["veredito"] in ("amplo", "estrito"),
                "classificado_em": _ts(r["classificado_em"]),
            }
        )
    schema = pa.schema(
        [
            ("paper_id", pa.string()),
            ("veredito", pa.string()),
            ("aprovado", pa.bool_()),
            ("regra_fora", pa.string()),
            ("justificativa", pa.string()),
            ("tem_artefato_nomeado", pa.bool_()),
            ("portabilidade_aprovada", pa.bool_()),
            ("portab_depende_nome", pa.bool_()),
            ("portab_generalidade", pa.bool_()),
            ("decisao_fronteira", pa.bool_()),
            ("fronteira_contraparte", pa.string()),
            ("classificado_em", pa.timestamp("s")),
            ("run_id", pa.string()),
            ("revisao", pa.int32()),
        ]
    )
    return linhas, schema


def _dim_ficha(conn: sqlite3.Connection) -> tuple[list[dict], pa.Schema]:
    linhas = []
    for r in _rows(conn, "SELECT * FROM dim_ficha"):
        linhas.append({**r, "gerada_em": _ts(r["gerada_em"]), "tem_padrao": bool(r["padrao_nome"])})
    schema = pa.schema(
        [
            ("paper_id", pa.string()),
            ("achado", pa.string()),
            ("padrao_nome", pa.string()),
            ("padrao_mecanismo", pa.string()),
            ("tem_padrao", pa.bool_()),
            ("implicacao_pratica", pa.string()),
            ("exemplo_concreto", pa.string()),
            ("ressalva", pa.string()),
            ("gerada_em", pa.timestamp("s")),
            ("modelo_usado", pa.string()),
            ("run_id", pa.string()),
        ]
    )
    return linhas, schema


def _fato_execucao(conn: sqlite3.Connection) -> tuple[list[dict], pa.Schema]:
    linhas = []
    for r in _rows(conn, "SELECT * FROM log_execucao"):
        avisos = json.loads(r["avisos"]) if r["avisos"] else []
        linhas.append(
            {
                **r,
                "iniciado_em": _ts(r["iniciado_em"]),
                "finalizado_em": _ts(r["finalizado_em"]),
                "data_execucao": _d(r["iniciado_em"]),
                "qtd_avisos": len(avisos),
            }
        )
    schema = pa.schema(
        [
            ("run_id", pa.string()),
            ("data_execucao", pa.date32()),
            ("iniciado_em", pa.timestamp("s")),
            ("finalizado_em", pa.timestamp("s")),
            ("status", pa.string()),
            ("dias_cobertos", pa.string()),
            ("qtd_coletados", pa.int32()),
            ("qtd_novos", pa.int32()),
            ("qtd_ja_vistos", pa.int32()),
            ("qtd_fora", pa.int32()),
            ("qtd_amplo", pa.int32()),
            ("qtd_estrito", pa.int32()),
            ("taxa_fora", pa.float64()),
            ("qtd_refresh", pa.int32()),
            ("tokens_entrada", pa.int64()),
            ("tokens_saida", pa.int64()),
            ("custo_usd", pa.float64()),
            ("qtd_avisos", pa.int32()),
            ("avisos", pa.string()),
        ]
    )
    return linhas, schema


def _dim_calendario(conn: sqlite3.Connection) -> tuple[list[dict], pa.Schema]:
    linhas = [
        {**r, "data": _d(r["data"]), "eh_dia_util": _b(r["eh_dia_util"])}
        for r in _rows(conn, "SELECT * FROM dim_calendario ORDER BY data")
    ]
    schema = pa.schema(
        [
            ("data", pa.date32()),
            ("ano", pa.int32()),
            ("mes", pa.int32()),
            ("dia", pa.int32()),
            ("nome_mes", pa.string()),
            ("trimestre", pa.int32()),
            ("semana_iso", pa.int32()),
            ("ano_semana_iso", pa.string()),
            ("dia_semana", pa.int32()),
            ("nome_dia_semana", pa.string()),
            ("eh_dia_util", pa.bool_()),
        ]
    )
    return linhas, schema


def _simples(conn: sqlite3.Connection, tabela: str, schema: pa.Schema) -> tuple[list[dict], pa.Schema]:
    return _rows(conn, f"SELECT * FROM {tabela}"), schema


_SCHEMAS_SIMPLES = {
    "dim_area": pa.schema(
        [("area", pa.string()), ("definicao", pa.string()), ("desde", pa.string())]
    ),
    "dim_topico": pa.schema(
        [("topico", pa.string()), ("definicao", pa.string()), ("desde", pa.string())]
    ),
    "dim_vertente": pa.schema(
        [("vertente", pa.string()), ("definicao", pa.string()), ("desde", pa.string())]
    ),
    "ponte_paper_area": pa.schema(
        [
            ("paper_id", pa.string()),
            ("area", pa.string()),
            ("subarea", pa.string()),
            ("is_primaria", pa.bool_()),
        ]
    ),
    "ponte_paper_topico": pa.schema([("paper_id", pa.string()), ("topico", pa.string())]),
    # `ordem` vai como coluna, e nao so a linha da dominante: e ela que separa
    # a vertente dominante (1) da secundaria (2) nas medidas do Power BI.
    "ponte_paper_vertente": pa.schema(
        [("paper_id", pa.string()), ("vertente", pa.string()), ("ordem", pa.int32())]
    ),
    "ponte_paper_criterio": pa.schema([("paper_id", pa.string()), ("criterio", pa.string())]),
    "ponte_paper_keyword": pa.schema([("paper_id", pa.string()), ("keyword", pa.string())]),
    "ponte_paper_autor": pa.schema(
        [
            ("paper_id", pa.string()),
            ("ordem", pa.int32()),
            ("autor", pa.string()),
            ("hf_user", pa.string()),
            ("verificado", pa.bool_()),
        ]
    ),
}


# ── entrada ─────────────────────────────────────────────────────────────────


def rodar(
    conn: sqlite3.Connection,
    cfg: Optional[Config] = None,
    *,
    run_id: Optional[str] = None,
    hoje: Optional[dt.date] = None,
) -> ResultadoExport:
    cfg = cfg or config()
    hoje = hoje or db.hoje()
    dir_saida = cfg.dir_marts
    dir_saida.mkdir(parents=True, exist_ok=True)
    res = ResultadoExport(dir_saida=dir_saida)
    csv_tambem = cfg.export.csv

    db.garantir_calendario(conn)

    tabelas: list[tuple[str, tuple[list[dict], pa.Schema]]] = [
        ("dim_paper", _dim_paper(conn, cfg, hoje)),
        ("fato_metrica", _fato_metrica(conn)),
        ("fato_triagem", _fato_triagem(conn)),
        ("dim_ficha", _dim_ficha(conn)),
        ("dim_calendario", _dim_calendario(conn)),
        ("fato_execucao", _fato_execucao(conn)),
    ]
    for nome, schema in _SCHEMAS_SIMPLES.items():
        linhas, sch = _simples(conn, nome, schema)
        if nome in ("ponte_paper_area", "ponte_paper_autor"):
            campo = "is_primaria" if nome == "ponte_paper_area" else "verificado"
            linhas = [{**l, campo: _b(l[campo])} for l in linhas]
        tabelas.append((nome, (linhas, sch)))

    for nome, (linhas, schema) in tabelas:
        res.arquivos[nome] = _escrever(dir_saida, nome, linhas, schema, csv_tambem=csv_tambem)

    if run_id is None:
        row = conn.execute(
            "SELECT run_id FROM log_execucao ORDER BY iniciado_em DESC LIMIT 1"
        ).fetchone()
        run_id = row["run_id"] if row else None

    manifest = {
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
