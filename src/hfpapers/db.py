"""Acesso ao SQLite: conexao, migracao, upserts idempotentes e calendario.

Duas regras que valem para o arquivo inteiro:

* datas e timestamps sao gravados como texto ISO (`2026-08-25`,
  `2026-08-25T09:31:00`). Nada de adapters implicitos do sqlite3 - eles foram
  depreciados no 3.12 e escondem o formato real do dado.
* todo `INSERT` de tabela com chave natural e `UPSERT`. Rodar o pipeline duas
  vezes no mesmo dia nao pode duplicar linha (secao 11 do PROMPT).
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Optional, Sequence

from .config import Config, config

SCHEMA_SQL = Path(__file__).with_name("schema.sql")

NOMES_MES = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]
NOMES_DIA_SEMANA = [
    "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
    "sexta-feira", "sábado", "domingo",
]

TABELAS_ESPERADAS = [
    "dim_paper", "fato_metrica", "fato_triagem", "dim_ficha",
    "dim_area", "dim_topico", "ponte_paper_area", "ponte_paper_topico",
    "tax_candidato", "ponte_paper_keyword", "ponte_paper_autor",
    "log_execucao", "log_llm", "dim_calendario",
]


# ── conexao ─────────────────────────────────────────────────────────────────


def conectar(caminho: Path | str, *, migrar_schema: bool = True) -> sqlite3.Connection:
    caminho = Path(caminho)
    if str(caminho) != ":memory:":
        caminho.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(caminho), timeout=30.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    if migrar_schema:
        migrar(conn)
    return conn


def abrir(cfg: Optional[Config] = None, **kwargs: Any) -> sqlite3.Connection:
    cfg = cfg or config()
    return conectar(cfg.caminho_banco, **kwargs)


def migrar(conn: sqlite3.Connection) -> None:
    """Aplica schema.sql. Idempotente: tudo la e IF NOT EXISTS."""
    conn.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))


@contextmanager
def transacao(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Transacao explicita por estagio: falha no estagio 3 nao desfaz o 1."""
    conn.execute("BEGIN")
    try:
        yield conn
    except Exception:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


# ── normalizacao de valores ─────────────────────────────────────────────────


def _valor(v: Any) -> Any:
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, dt.datetime):
        return v.replace(microsecond=0).isoformat()
    if isinstance(v, dt.date):
        return v.isoformat()
    if isinstance(v, Path):
        return str(v)
    return v


def agora() -> str:
    return dt.datetime.now().replace(microsecond=0).isoformat()


def hoje() -> dt.date:
    return dt.date.today()


# ── upsert generico ─────────────────────────────────────────────────────────


def upsert(
    conn: sqlite3.Connection,
    tabela: str,
    dados: Mapping[str, Any],
    chave: Sequence[str],
    *,
    nao_sobrescrever: Sequence[str] = (),
    manter_se_nulo: Sequence[str] = (),
) -> None:
    """INSERT ... ON CONFLICT(chave) DO UPDATE.

    `nao_sobrescrever`: colunas gravadas so na primeira insercao (ex.:
    `primeiro_visto_em`).
    `manter_se_nulo`: colunas cujo valor antigo sobrevive quando o novo e NULL -
    e como o refresh por data evita apagar um `github_stars` ja conhecido.
    """
    cols = list(dados.keys())
    vals = [_valor(dados[c]) for c in cols]
    marca = ", ".join("?" for _ in cols)
    alvo = ", ".join(chave)

    atualizaveis = [c for c in cols if c not in chave and c not in nao_sobrescrever]
    if atualizaveis:
        sets = []
        for c in atualizaveis:
            if c in manter_se_nulo:
                sets.append(f"{c} = COALESCE(excluded.{c}, {tabela}.{c})")
            else:
                sets.append(f"{c} = excluded.{c}")
        acao = "UPDATE SET " + ", ".join(sets)
    else:
        acao = "NOTHING"

    sql = (
        f"INSERT INTO {tabela} ({', '.join(cols)}) VALUES ({marca}) "
        f"ON CONFLICT({alvo}) DO {acao}"
    )
    conn.execute(sql, vals)


def inserir_ignorando(
    conn: sqlite3.Connection, tabela: str, dados: Mapping[str, Any]
) -> None:
    cols = list(dados.keys())
    vals = [_valor(dados[c]) for c in cols]
    sql = (
        f"INSERT OR IGNORE INTO {tabela} ({', '.join(cols)}) "
        f"VALUES ({', '.join('?' for _ in cols)})"
    )
    conn.execute(sql, vals)


# ── upserts nomeados ────────────────────────────────────────────────────────


def upsert_paper(conn: sqlite3.Connection, dados: Mapping[str, Any]) -> None:
    upsert(
        conn,
        "dim_paper",
        dados,
        chave=["paper_id"],
        nao_sobrescrever=["primeiro_visto_em"],
        manter_se_nulo=[
            "abstract", "ai_summary", "ai_summary_model", "data_arxiv",
            "data_hf_daily", "project_page", "github_repo", "github_repo_added_by",
            "discussion_id", "thumbnail_url", "organizacao", "organizacao_nome_longo",
            "submetido_por", "submetido_por_nome", "autor_participa", "qtd_autores",
            "qtd_autores_verificados", "enriquecido_em",
        ],
    )


def upsert_metrica(conn: sqlite3.Connection, dados: Mapping[str, Any]) -> None:
    """Um snapshot por paper por dia. Segunda rodada do dia sobrescreve.

    `qtd_modelos/datasets/spaces` so vem no enriquecimento (`origem='por_paper'`);
    num snapshot `daily` chegam NULL e o valor antigo do dia e preservado.
    """
    upsert(
        conn,
        "fato_metrica",
        dados,
        chave=["paper_id", "data_snapshot"],
        manter_se_nulo=[
            "upvotes", "comentarios", "github_stars",
            "qtd_modelos", "qtd_datasets", "qtd_spaces",
        ],
    )


def upsert_triagem(conn: sqlite3.Connection, dados: Mapping[str, Any]) -> None:
    upsert(conn, "fato_triagem", dados, chave=["paper_id"])


def upsert_ficha(conn: sqlite3.Connection, dados: Mapping[str, Any]) -> None:
    upsert(conn, "dim_ficha", dados, chave=["paper_id"])


def upsert_area(conn: sqlite3.Connection, dados: Mapping[str, Any]) -> None:
    upsert(conn, "dim_area", dados, chave=["area"])


def upsert_topico(conn: sqlite3.Connection, dados: Mapping[str, Any]) -> None:
    upsert(conn, "dim_topico", dados, chave=["topico"])


def upsert_candidato(conn: sqlite3.Connection, dados: Mapping[str, Any]) -> None:
    upsert(conn, "tax_candidato", dados, chave=["rotulo", "tipo"])


def upsert_execucao(conn: sqlite3.Connection, dados: Mapping[str, Any]) -> None:
    upsert(conn, "log_execucao", dados, chave=["run_id"], nao_sobrescrever=["iniciado_em"])


def registrar_llm(conn: sqlite3.Connection, dados: Mapping[str, Any]) -> None:
    inserir_ignorando(conn, "log_llm", dados)


# ── consultas de apoio ──────────────────────────────────────────────────────


def ids_existentes(conn: sqlite3.Connection, ids: Iterable[str]) -> set[str]:
    ids = list(ids)
    if not ids:
        return set()
    marca = ", ".join("?" for _ in ids)
    cur = conn.execute(f"SELECT paper_id FROM dim_paper WHERE paper_id IN ({marca})", ids)
    return {r["paper_id"] for r in cur}


def contar(conn: sqlite3.Connection, tabela: str, onde: str = "", params: Sequence = ()) -> int:
    sql = f"SELECT COUNT(*) AS n FROM {tabela}"
    if onde:
        sql += f" WHERE {onde}"
    return int(conn.execute(sql, params).fetchone()["n"])


def max_data_hf(conn: sqlite3.Connection) -> Optional[dt.date]:
    row = conn.execute("SELECT MAX(data_hf_daily) AS d FROM dim_paper").fetchone()
    if not row or not row["d"]:
        return None
    return dt.date.fromisoformat(str(row["d"])[:10])


# ── calendario ──────────────────────────────────────────────────────────────


def linha_calendario(d: dt.date) -> dict[str, Any]:
    ano_iso, semana_iso, dia_iso = d.isocalendar()
    return {
        "data": d.isoformat(),
        "ano": d.year,
        "mes": d.month,
        "dia": d.day,
        "nome_mes": NOMES_MES[d.month - 1],
        "trimestre": (d.month - 1) // 3 + 1,
        "semana_iso": semana_iso,
        "ano_semana_iso": f"{ano_iso}-W{semana_iso:02d}",
        "dia_semana": dia_iso,
        "nome_dia_semana": NOMES_DIA_SEMANA[dia_iso - 1],
        "eh_dia_util": int(dia_iso <= 5),
    }


def popular_calendario(
    conn: sqlite3.Connection, inicio: dt.date, fim: dt.date
) -> int:
    """Preenche dim_calendario no intervalo fechado [inicio, fim]."""
    if fim < inicio:
        inicio, fim = fim, inicio
    n = 0
    d = inicio
    while d <= fim:
        upsert(conn, "dim_calendario", linha_calendario(d), chave=["data"])
        d += dt.timedelta(days=1)
        n += 1
    return n


def garantir_calendario(conn: sqlite3.Connection, *, margem_dias: int = 400) -> int:
    """Cobre do primeiro dado conhecido ate hoje + margem, sem buracos."""
    row = conn.execute(
        "SELECT MIN(d) AS d FROM ("
        "  SELECT MIN(data_hf_daily) AS d FROM dim_paper"
        "  UNION ALL SELECT MIN(data_arxiv) FROM dim_paper"
        "  UNION ALL SELECT MIN(data_snapshot) FROM fato_metrica"
        ")"
    ).fetchone()
    inicio = dt.date.fromisoformat(str(row["d"])[:10]) if row and row["d"] else hoje()
    inicio = min(inicio, hoje()) - dt.timedelta(days=7)
    return popular_calendario(conn, inicio, hoje() + dt.timedelta(days=margem_dias))


# ── integridade (usado pelo `doutor`) ───────────────────────────────────────


def diagnostico_banco(conn: sqlite3.Connection) -> dict[str, Any]:
    tabelas = {
        r["name"]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    faltando = [t for t in TABELAS_ESPERADAS if t not in tabelas]
    integridade = conn.execute("PRAGMA integrity_check").fetchone()[0]
    fks = conn.execute("PRAGMA foreign_key_check").fetchall()
    contagens = {t: contar(conn, t) for t in TABELAS_ESPERADAS if t in tabelas}
    return {
        "tabelas_faltando": faltando,
        "integridade": integridade,
        "fk_violacoes": len(fks),
        "contagens": contagens,
        "journal_mode": conn.execute("PRAGMA journal_mode").fetchone()[0],
    }
