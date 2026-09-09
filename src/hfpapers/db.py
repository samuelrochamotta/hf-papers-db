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
from .log import logger

SCHEMA_SQL = Path(__file__).with_name("schema.sql")

log = logger("db")

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
    "dim_area", "dim_vertente",
    "ponte_paper_area", "ponte_paper_vertente",
    "ponte_paper_criterio",
    "tax_nao_encaixe", "ponte_paper_keyword", "ponte_paper_autor",
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


# Colunas acrescentadas a tabelas que ja existiam em bancos de producao.
# `CREATE TABLE IF NOT EXISTS` nao toca uma tabela existente, entao a coluna
# nova precisa de `ALTER TABLE` proprio; a DDL em schema.sql continua sendo a
# fonte para banco criado do zero. Formato: (tabela, coluna, tipo SQL).
COLUNAS_MIGRADAS = [
    ("dim_paper", "data_arxiv_informada_hf", "DATE"),
    ("dim_paper", "data_arxiv_v1", "DATE"),
    ("dim_paper", "arxiv_v1_verificado_em", "TEXT"),
    ("fato_triagem", "fronteira_contraparte", "TEXT"),
    # A auto-referencia entra por ALTER TABLE, que o SQLite so aceita com
    # default NULL - o que e exatamente o que a area raiz quer.
    ("dim_area", "area_pai", "TEXT NULL REFERENCES dim_area(area)"),
    ("log_llm", "provedor", "TEXT"),
]


def migrar(conn: sqlite3.Connection) -> None:
    """Aplica schema.sql, as colunas de `COLUNAS_MIGRADAS`, a reconstrucao de
    `ponte_paper_area`, a saida de `tax_candidato` e a contracao da grade
    anterior. Idempotente: tudo la e IF NOT EXISTS, a coluna so e adicionada
    quando falta, e as tabelas so sao tocadas uma vez."""
    conn.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))
    for tabela, coluna, tipo in COLUNAS_MIGRADAS:
        _garantir_coluna(conn, tabela, coluna, tipo)
    conn.execute("UPDATE dim_paper SET data_arxiv_informada_hf = data_arxiv "
                 "WHERE data_arxiv_informada_hf IS NULL AND data_arxiv IS NOT NULL")
    _migrar_ponte_paper_area(conn)
    _remover_tax_candidato(conn)
    _contrair_grade_antiga(conn)


def colunas(conn: sqlite3.Connection, tabela: str) -> list[str]:
    return [r["name"] for r in conn.execute(f"PRAGMA table_info({tabela})")]


def _garantir_coluna(conn: sqlite3.Connection, tabela: str, coluna: str, tipo: str) -> None:
    if coluna in colunas(conn, tabela):
        return
    conn.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")


def _migrar_ponte_paper_area(conn: sqlite3.Connection) -> None:
    """Reconstroi `ponte_paper_area` com a sub-area dentro da chave primaria.

    Nao e `ALTER TABLE`: a chave `(paper_id, area)` proibia o par secundario de
    mesma area com sub-area diferente, e chave primaria o SQLite so troca
    recriando a tabela.

    **A tabela volta vazia, e isso e deliberado.** As linhas antigas sao da
    grade plana, que nao tem nivel de sub-area, entao nao ha valor honesto para
    a coluna NOT NULL que entra: repetir a area no lugar da sub-area gravaria um
    par que `taxonomia.aplicar_classificacao` passa a recusar por falta de
    parentesco. Elas tambem nao sobreviveriam ao ticket 05, que apaga a grade
    plana de `dim_area` e as deixaria com chave estrangeira pendurada. Quem
    repovoa a ponte para a base inteira e a reclassificacao do ticket 07.

    Idempotente e a prova de queda no meio: `migrar` roda o schema.sql antes,
    entao um processo morto entre o DROP e a recriacao recria a tabela na
    passagem seguinte.
    """
    if "subarea" in colunas(conn, "ponte_paper_area"):
        return
    descartadas = contar(conn, "ponte_paper_area")
    conn.execute("DROP TABLE ponte_paper_area")
    conn.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))
    log.warning(
        "ponte_paper_area reconstruida com a sub-area na chave primaria: "
        "%d pares da grade plana descartados (repovoados pela reclassificacao)",
        descartadas,
    )


def _remover_tax_candidato(conn: sqlite3.Connection) -> None:
    """Apaga `tax_candidato` e os candidatos que ela guardava.

    Nao ha migracao de conteudo para `tax_nao_encaixe` porque nao ha conteudo a
    migrar: o candidato era um rotulo *proposto* para uma grade que deixou de
    existir - as seis variantes de robotica, as tres de world models -, e a
    informacao que essas familias carregavam ja foi extraida e usada no desenho
    da grade facetada. O nao-encaixe nem tem campo de rotulo onde po-las.

    Idempotente pela propria pergunta: tabela ausente nao tem o que apagar.
    """
    if not colunas(conn, "tax_candidato"):
        return
    descartados = contar(conn, "tax_candidato")
    conn.execute("DROP TABLE tax_candidato")
    log.warning(
        "tax_candidato removida: %d candidato(s) descartados - a fila de revisao "
        "agora e tax_nao_encaixe, que registra o eixo em vez de propor rotulo",
        descartados,
    )


def _contrair_grade_antiga(conn: sqlite3.Connection) -> None:
    """Apaga o vocabulario anterior: a dimensao de topicos, a ponte dela e as
    areas da grade plana.

    Sai tudo de uma vez porque e uma coisa so - a grade que a facetada
    substituiu -, e sai sem versionamento pelo principio do ADR 001: uma fonte
    de verdade por decisao. A rastreabilidade fica no `run_id` da rodada e no
    historico de `config/taxonomia_inicial.json` no git, nao numa coluna de
    versao que toda consulta teria de filtrar para sempre.

    A area plana e reconhecida pela forma - raiz sem sub-area -, o mesmo teste
    que separava as duas grades enquanto elas conviviam em `dim_area`. As
    linhas de `ponte_paper_area` que apontavam para ela ja tinham saido na
    reconstrucao acima, que devolve a ponte vazia.

    **Uma vez so, e presa a existencia de `dim_topico`.** Sem essa condicao a
    regra "raiz sem sub-area sai" valeria para sempre e apagaria em silencio
    uma area raiz nova, gravada antes da primeira sub-area dela.
    """
    if not colunas(conn, "dim_topico"):
        return
    topicos = contar(conn, "dim_topico")
    pontes = contar(conn, "ponte_paper_topico")
    conn.executescript("DROP TABLE ponte_paper_topico; DROP TABLE dim_topico;")
    areas = conn.execute(
        "DELETE FROM dim_area WHERE area_pai IS NULL AND area NOT IN "
        "(SELECT area_pai FROM dim_area WHERE area_pai IS NOT NULL)"
    ).rowcount
    log.warning(
        "grade anterior removida: %d topico(s), %d linha(s) da ponte de topico "
        "e %d area(s) da grade plana - quem reclassifica na grade facetada e a "
        "rodada seguinte",
        topicos, pontes, areas,
    )


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
) -> int:
    """Devolve 1 se a linha entrou e 0 se o IGNORE a descartou.

    Quem so quer gravar ignora o retorno; quem precisa separar insercao de
    linha ja existente (`taxonomia.carregar`, para dizer quantos rotulos o
    banco ja tinha) nao tem outro jeito sem consultar a tabela antes.
    """
    cols = list(dados.keys())
    vals = [_valor(dados[c]) for c in cols]
    sql = (
        f"INSERT OR IGNORE INTO {tabela} ({', '.join(cols)}) "
        f"VALUES ({', '.join('?' for _ in cols)})"
    )
    return conn.execute(sql, vals).rowcount


# ── upserts nomeados ────────────────────────────────────────────────────────


def upsert_paper(conn: sqlite3.Connection, dados: Mapping[str, Any]) -> None:
    if {"data_arxiv_v1", "arxiv_v1_verificado_em"} & dados.keys():
        raise ValueError("v1 deve ser escrita exclusivamente por registrar_arxiv_v1")
    dados = dict(dados)
    if "data_arxiv_informada_hf" in dados:
        dados["data_arxiv"] = dados["data_arxiv_informada_hf"]
    elif "data_arxiv" in dados:
        dados["data_arxiv_informada_hf"] = dados["data_arxiv"]
    upsert(
        conn,
        "dim_paper",
        dados,
        chave=["paper_id"],
        nao_sobrescrever=["primeiro_visto_em"],
        manter_se_nulo=[
            "abstract", "ai_summary", "ai_summary_model", "data_arxiv", "data_arxiv_informada_hf",
            "data_hf_daily", "project_page", "github_repo", "github_repo_added_by",
            "discussion_id", "thumbnail_url", "organizacao", "organizacao_nome_longo",
            "submetido_por", "submetido_por_nome", "autor_participa", "qtd_autores",
            "qtd_autores_verificados", "enriquecido_em",
        ],
    )


def registrar_arxiv_v1(conn: sqlite3.Connection, pid: str, data: str, verificado: str) -> bool:
    """Preenche uma vez; uma revalidacao divergente nunca sobrescreve a v1."""
    dt.date.fromisoformat(data)
    with transacao(conn):
        conn.execute("UPDATE dim_paper SET data_arxiv_v1=?, arxiv_v1_verificado_em=? "
                     "WHERE paper_id=? AND data_arxiv_v1 IS NULL", (data, verificado, pid))
        row = conn.execute("SELECT data_arxiv_v1 FROM dim_paper WHERE paper_id=?", (pid,)).fetchone()
    return bool(row and row[0] == data)


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


def upsert_vertente(conn: sqlite3.Connection, dados: Mapping[str, Any]) -> None:
    upsert(conn, "dim_vertente", dados, chave=["vertente"])


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
        "  UNION ALL SELECT MIN(data_arxiv_v1) FROM dim_paper"
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
