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

from .config import PERFIS_PADRAO, Config, Perfil, config
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
    "dim_natureza", "dim_prerequisito", "dim_perfil", "ponte_perfil_prerequisito",
    "tax_nao_encaixe", "ponte_paper_keyword", "ponte_paper_autor",
    "log_execucao", "log_llm", "dim_calendario",
]


# ── conexao ─────────────────────────────────────────────────────────────────


def conectar(
    caminho: Path | str,
    *,
    migrar_schema: bool = True,
    perfis: Optional[Sequence[Perfil]] = None,
) -> sqlite3.Connection:
    caminho = Path(caminho)
    if str(caminho) != ":memory:":
        caminho.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(caminho), timeout=30.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    if migrar_schema:
        migrar(conn, perfis=perfis)
    return conn


def abrir(cfg: Optional[Config] = None, **kwargs: Any) -> sqlite3.Connection:
    cfg = cfg or config()
    kwargs.setdefault("perfis", cfg.perfis)
    return conectar(cfg.caminho_banco, **kwargs)


# Colunas acrescentadas a tabelas que ja existiam em bancos de producao.
# `CREATE TABLE IF NOT EXISTS` nao toca uma tabela existente, entao a coluna
# nova precisa de `ALTER TABLE` proprio; a DDL em schema.sql continua sendo a
# fonte para banco criado do zero. Formato: (tabela, coluna, tipo SQL).
COLUNAS_MIGRADAS = [
    ("dim_paper", "data_arxiv_informada_hf", "DATE"),
    ("dim_paper", "data_arxiv_v1", "DATE"),
    ("dim_paper", "arxiv_v1_verificado_em", "TEXT"),
    # A auto-referencia entra por ALTER TABLE, que o SQLite so aceita com
    # default NULL - o que e exatamente o que a area raiz quer.
    ("dim_area", "area_pai", "TEXT NULL REFERENCES dim_area(area)"),
    ("log_llm", "provedor", "TEXT"),
    ("log_llm", "tokens_cache_leitura", "INTEGER"),
    ("log_execucao", "qtd_aprovados", "INTEGER"),
    ("log_execucao", "qtd_pr_nenhum", "INTEGER"),
    ("log_execucao", "qtd_pr_implementar", "INTEGER"),
    ("log_execucao", "qtd_pr_acesso_interno", "INTEGER"),
    ("log_execucao", "qtd_pr_treino", "INTEGER"),
    ("log_execucao", "qtd_pr_sem_acao", "INTEGER"),
]

# Views recriadas a cada `migrar`, depois das migracoes: no schema.sql elas
# seriam criadas antes da reconstrucao de `fato_triagem` e apontariam para
# colunas que um banco do regime anterior ainda nao tem.
#
# `vw_artefato` e a unica fonte de "tem artefato aberto". A evidencia e
# externa (repositorio, link no abstract, modelo ou dataset vinculado no HF em
# qualquer snapshot - o mais recente costuma vir com os contadores nulos); a
# LLM so distingue `liberado` de `prometido`, e so quando ha evidencia.
#
# `vw_paper_perfil` e a unica fonte de "da para agir": uma linha por aprovado
# e por perfil cujo conjunto de degraus contem o pre-requisito do paper.
VIEWS_SQL = """
DROP VIEW IF EXISTS vw_artefato;
CREATE VIEW vw_artefato AS
SELECT e.paper_id, e.evidencia, e.github_repo, e.links_abstract,
       CASE
           WHEN t.veredito IS NOT 'aprovado' THEN NULL
           WHEN t.natureza IN ('teoria', 'panorama') THEN NULL
           WHEN e.evidencia = 1 AND t.artefato_status = 'liberado' THEN 1
           ELSE 0
       END AS artefato_aberto
FROM (
    SELECT p.paper_id, p.github_repo,
           (instr(lower(COALESCE(p.abstract, '')), 'github.com/') > 0
            OR instr(lower(COALESCE(p.abstract, '')), 'huggingface.co/') > 0) AS links_abstract,
           CASE WHEN p.github_repo IS NOT NULL
                  OR instr(lower(COALESCE(p.abstract, '')), 'github.com/') > 0
                  OR instr(lower(COALESCE(p.abstract, '')), 'huggingface.co/') > 0
                  OR COALESCE(m.max_modelos, 0) > 0
                  OR COALESCE(m.max_datasets, 0) > 0
                THEN 1 ELSE 0 END AS evidencia
    FROM dim_paper p
    LEFT JOIN (
        SELECT paper_id, MAX(qtd_modelos) AS max_modelos, MAX(qtd_datasets) AS max_datasets
        FROM fato_metrica GROUP BY paper_id
    ) m ON m.paper_id = p.paper_id
) e
LEFT JOIN fato_triagem t ON t.paper_id = e.paper_id;

DROP VIEW IF EXISTS vw_paper_perfil;
CREATE VIEW vw_paper_perfil AS
SELECT t.paper_id, pp.perfil
FROM fato_triagem t
JOIN ponte_perfil_prerequisito pp ON pp.prerequisito = t.prerequisito
WHERE t.veredito = 'aprovado';
"""


def migrar(conn: sqlite3.Connection, *, perfis: Optional[Sequence[Perfil]] = None) -> None:
    """Aplica schema.sql, as colunas de `COLUNAS_MIGRADAS`, a reconstrucao de
    `ponte_paper_area`, a saida de `tax_candidato`, a contracao da grade
    anterior e a passagem para o regime do ADR 004; recria as views e
    sincroniza os perfis. Idempotente: tudo la e IF NOT EXISTS, a coluna so e
    adicionada quando falta, e as tabelas so sao tocadas uma vez.

    As views saem antes e voltam no fim: o SQLite revalida toda view a cada
    ALTER TABLE, e uma view apontando para coluna que a reconstrucao ainda nao
    criou derrubaria a migracao."""
    conn.executescript("DROP VIEW IF EXISTS vw_artefato; DROP VIEW IF EXISTS vw_paper_perfil;")
    conn.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))
    for tabela, coluna, tipo in COLUNAS_MIGRADAS:
        _garantir_coluna(conn, tabela, coluna, tipo)
    conn.execute("UPDATE dim_paper SET data_arxiv_informada_hf = data_arxiv "
                 "WHERE data_arxiv_informada_hf IS NULL AND data_arxiv IS NOT NULL")
    _migrar_ponte_paper_area(conn)
    _remover_tax_candidato(conn)
    _contrair_grade_antiga(conn)
    _migrar_triagem_v2(conn)
    conn.executescript(VIEWS_SQL)
    sincronizar_perfis(conn, PERFIS_PADRAO if perfis is None else perfis)


def ddl_de(tabela: str) -> list[str]:
    """Os comandos de `schema.sql` que criam `tabela` e os indices dela.

    `executescript` faz COMMIT implicito, entao nao serve dentro da transacao
    de uma reconstrucao; os comandos sao separados com
    `sqlite3.complete_statement`, que respeita comentario e string - um ";"
    num comentario de coluna nao corta o comando no meio.
    """
    comandos, buf = [], ""
    for linha in SCHEMA_SQL.read_text(encoding="utf-8").splitlines(keepends=True):
        buf += linha
        if sqlite3.complete_statement(buf):
            comandos.append(buf.strip())
            buf = ""
    alvo = (f"CREATE TABLE IF NOT EXISTS {tabela} (", f" ON {tabela}(")
    return [c for c in comandos if any(a in c for a in alvo)]


def sincronizar_perfis(conn: sqlite3.Connection, perfis: Sequence[Perfil]) -> None:
    """Reescreve `dim_perfil` e a ponte a partir do config: a fonte e o YAML, e
    o banco so espelha, para que a view e o `doutor` concordem com ele sem
    esperar o proximo export. Degrau desconhecido e erro de configuracao, e a
    chave estrangeira o recusa."""
    with transacao(conn):
        conn.execute("DELETE FROM ponte_perfil_prerequisito")
        conn.execute("DELETE FROM dim_perfil")
        for ordem, p in enumerate(perfis, start=1):
            conn.execute(
                "INSERT INTO dim_perfil (perfil, rotulo, ordem) VALUES (?, ?, ?)",
                (p.perfil, p.rotulo, ordem),
            )
            for degrau in dict.fromkeys(p.prerequisitos):
                conn.execute(
                    "INSERT INTO ponte_perfil_prerequisito (perfil, prerequisito) VALUES (?, ?)",
                    (p.perfil, degrau),
                )


def _migrar_triagem_v2(conn: sqlite3.Connection) -> None:
    """Passa `fato_triagem` para o regime do ADR 004, e apaga o que morreu com
    o anterior: `ponte_paper_criterio` e `dim_paper.tem_codigo_aberto`.

    E reconstrucao, e nao `ALTER TABLE`: o CHECK de `veredito` muda, e CHECK o
    SQLite so troca recriando a tabela. **As linhas sobrevivem**: estrito e
    amplo viram `aprovado`, com natureza e pre-requisito nulos ate a
    reclassificacao total; `fora` fica com a regra que tinha, mesmo as que
    sairam - o `doutor` as acusa. Recriar vazia, como `_migrar_ponte_paper_area`
    fez, deixaria o painel sem nada ate o fim de uma rodada de horas.

    Sem copia do regime anterior, por decisao do dono: a regua do piloto e o
    `.scratch/regime_v1.csv`, exportado antes da primeira execucao deste codigo.

    **Uma vez so, presa a existencia de `decisao_fronteira`** - a coluna que so
    o regime anterior tem. Numa transacao: um processo morto no meio volta ao
    regime anterior inteiro, e a passagem seguinte refaz.
    """
    if "decisao_fronteira" not in colunas(conn, "fato_triagem"):
        return
    total = contar(conn, "fato_triagem")
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        with transacao(conn):
            conn.execute("DROP INDEX IF EXISTS ix_triagem_veredito")
            conn.execute("ALTER TABLE fato_triagem RENAME TO _fato_triagem_v1")
            for ddl in ddl_de("fato_triagem"):
                conn.execute(ddl)
            conn.execute(
                "INSERT INTO fato_triagem (paper_id, veredito, regra_fora, justificativa, "
                "classificado_em, run_id, revisao) "
                "SELECT paper_id, CASE WHEN veredito = 'fora' THEN 'fora' ELSE 'aprovado' END, "
                "CASE WHEN veredito = 'fora' THEN regra_fora END, justificativa, "
                "classificado_em, run_id, revisao FROM _fato_triagem_v1"
            )
            conn.execute("DROP TABLE _fato_triagem_v1")
            conn.execute("DROP TABLE IF EXISTS ponte_paper_criterio")
            if "tem_codigo_aberto" in colunas(conn, "dim_paper"):
                conn.execute("ALTER TABLE dim_paper DROP COLUMN tem_codigo_aberto")
    finally:
        conn.execute("PRAGMA foreign_keys = ON")
    log.warning(
        "fato_triagem passou ao regime do ADR 004: %d linha(s) preservadas, "
        "estrito/amplo viraram 'aprovado' sem natureza nem pre-requisito ate a "
        "reclassificacao total; ponte_paper_criterio e tem_codigo_aberto removidas",
        total,
    )


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
