import datetime as dt

import pytest

from hfpapers import db


@pytest.fixture()
def conn(tmp_path):
    c = db.conectar(tmp_path / "t.db")
    yield c
    c.close()


def _paper(pid="2608.23552", **extra):
    base = {
        "paper_id": pid,
        "titulo": "Um titulo",
        "primeiro_visto_em": "2026-08-25T09:00:00",
    }
    base.update(extra)
    return base


def test_schema_cria_todas_as_tabelas(conn):
    diag = db.diagnostico_banco(conn)
    assert diag["tabelas_faltando"] == []
    assert diag["integridade"] == "ok"


def test_upsert_paper_nao_duplica_e_preserva_primeiro_visto(conn):
    db.upsert_paper(conn, _paper(titulo="v1"))
    db.upsert_paper(conn, _paper(titulo="v2", primeiro_visto_em="2026-09-01T00:00:00"))
    row = conn.execute("SELECT * FROM dim_paper").fetchall()
    assert len(row) == 1
    assert row[0]["titulo"] == "v2"
    assert row[0]["primeiro_visto_em"] == "2026-08-25T09:00:00"


def test_metrica_um_snapshot_por_paper_por_dia(conn):
    db.upsert_paper(conn, _paper())
    for upv in (10, 12):
        db.upsert_metrica(
            conn,
            {
                "paper_id": "2608.23552",
                "data_snapshot": dt.date(2026, 8, 25),
                "upvotes": upv,
                "origem": "daily",
            },
        )
    rows = conn.execute("SELECT * FROM fato_metrica").fetchall()
    assert len(rows) == 1
    assert rows[0]["upvotes"] == 12


def test_metrica_daily_nao_apaga_contadores_do_enriquecimento(conn):
    db.upsert_paper(conn, _paper())
    chave = {"paper_id": "2608.23552", "data_snapshot": "2026-08-25"}
    db.upsert_metrica(conn, {**chave, "qtd_modelos": 3, "origem": "por_paper"})
    db.upsert_metrica(conn, {**chave, "upvotes": 40, "qtd_modelos": None, "origem": "daily"})
    row = conn.execute("SELECT * FROM fato_metrica").fetchone()
    assert row["qtd_modelos"] == 3
    assert row["upvotes"] == 40


def test_fk_recusa_metrica_de_paper_inexistente(conn):
    import sqlite3

    with pytest.raises(sqlite3.IntegrityError):
        db.upsert_metrica(
            conn, {"paper_id": "9999.99999", "data_snapshot": "2026-08-25", "origem": "daily"}
        )


def test_calendario_semana_iso_e_dia_util():
    seg = db.linha_calendario(dt.date(2026, 8, 24))
    assert seg["ano_semana_iso"] == "2026-W35"
    assert seg["dia_semana"] == 1 and seg["eh_dia_util"] == 1
    assert seg["nome_dia_semana"] == "segunda-feira"
    sab = db.linha_calendario(dt.date(2026, 8, 22))
    assert sab["eh_dia_util"] == 0


def test_popular_calendario_e_idempotente(conn):
    n1 = db.popular_calendario(conn, dt.date(2026, 8, 1), dt.date(2026, 8, 31))
    db.popular_calendario(conn, dt.date(2026, 8, 1), dt.date(2026, 8, 31))
    assert n1 == 31
    assert db.contar(conn, "dim_calendario") == 31


def test_transacao_faz_rollback(conn):
    with pytest.raises(RuntimeError):
        with db.transacao(conn):
            db.upsert_paper(conn, _paper())
            raise RuntimeError("boom")
    assert db.contar(conn, "dim_paper") == 0


# ── migracao de coluna ──────────────────────────────────────────────────────

# A `fato_triagem` como era antes da coluna `fronteira_contraparte`.
DDL_ANTIGA_FATO_TRIAGEM = """
DROP TABLE fato_triagem;
CREATE TABLE fato_triagem (
    paper_id TEXT PRIMARY KEY REFERENCES dim_paper(paper_id),
    veredito TEXT NOT NULL CHECK (veredito IN ('fora','amplo','estrito')),
    regra_fora TEXT, justificativa TEXT, tem_artefato_nomeado INTEGER,
    portabilidade_aprovada INTEGER, portab_depende_nome INTEGER, portab_generalidade INTEGER,
    decisao_fronteira INTEGER DEFAULT 0,
    classificado_em TIMESTAMP NOT NULL, run_id TEXT NOT NULL, revisao INTEGER NOT NULL DEFAULT 1
);
"""


def test_migracao_acrescenta_fronteira_contraparte_em_banco_antigo(tmp_path):
    """`CREATE TABLE IF NOT EXISTS` nao toca tabela existente: a coluna nova
    precisa do ALTER TABLE de `db.migrar`, e ele tem de preservar as linhas."""
    import sqlite3

    caminho = tmp_path / "antigo.db"
    db.conectar(caminho).close()            # schema atual, inclusive dim_paper
    bruto = sqlite3.connect(caminho)
    bruto.executescript(DDL_ANTIGA_FATO_TRIAGEM)
    bruto.execute(
        "INSERT INTO dim_paper (paper_id, titulo, primeiro_visto_em) "
        "VALUES ('2608.1', 'T', '2026-08-25T09:00:00')"
    )
    bruto.execute(
        "INSERT INTO fato_triagem (paper_id, veredito, classificado_em, run_id) "
        "VALUES ('2608.1', 'amplo', '2026-08-25T09:00:00', 'r')"
    )
    bruto.commit()
    bruto.close()

    conn = db.conectar(caminho)
    try:
        assert "fronteira_contraparte" in db.colunas(conn, "fato_triagem")
        row = conn.execute("SELECT veredito, fronteira_contraparte FROM fato_triagem").fetchone()
        assert (row["veredito"], row["fronteira_contraparte"]) == ("amplo", None)
        db.migrar(conn)   # segunda vez: idempotente, nao tenta ADD COLUMN de novo
        assert db.colunas(conn, "fato_triagem").count("fronteira_contraparte") == 1
        assert "ponte_paper_criterio" not in db.diagnostico_banco(conn)["tabelas_faltando"]
    finally:
        conn.close()


def test_banco_novo_ja_nasce_com_a_coluna_e_a_ponte(conn):
    assert "fronteira_contraparte" in db.colunas(conn, "fato_triagem")
    assert db.contar(conn, "ponte_paper_criterio") == 0


# A `dim_area` como era antes da coluna `area_pai` (grade plana, sem hierarquia).
DDL_ANTIGA_DIM_AREA = """
DROP TABLE dim_area;
CREATE TABLE dim_area (
    area TEXT PRIMARY KEY,
    definicao TEXT NOT NULL,
    desde DATE
);
"""


def test_migracao_acrescenta_area_pai_sem_perder_linhas(tmp_path):
    """A hierarquia de area chega por ALTER TABLE, e o banco de producao ja tem
    a dimensao povoada: a area que estava la vira raiz, com pai nulo."""
    import sqlite3

    caminho = tmp_path / "antigo.db"
    db.conectar(caminho).close()
    bruto = sqlite3.connect(caminho)
    bruto.executescript(DDL_ANTIGA_DIM_AREA)
    bruto.execute(
        "INSERT INTO dim_area (area, definicao, desde) "
        "VALUES ('Agentes & automação', 'd', '2026-08-25')"
    )
    bruto.commit()
    bruto.close()

    conn = db.conectar(caminho)
    try:
        assert "area_pai" in db.colunas(conn, "dim_area")
        row = conn.execute("SELECT * FROM dim_area").fetchone()
        assert (row["area"], row["definicao"], row["area_pai"]) == ("Agentes & automação", "d", None)
        db.migrar(conn)   # segunda vez: idempotente, nao tenta ADD COLUMN de novo
        assert db.colunas(conn, "dim_area").count("area_pai") == 1
        assert db.diagnostico_banco(conn)["tabelas_faltando"] == []
        assert db.contar(conn, "dim_vertente") == 0
    finally:
        conn.close()


# A `ponte_paper_area` como era antes da sub-area: chave `(paper_id, area)`.
DDL_ANTIGA_PONTE_AREA = """
DROP TABLE ponte_paper_area;
CREATE TABLE ponte_paper_area (
    paper_id TEXT NOT NULL REFERENCES dim_paper(paper_id),
    area TEXT NOT NULL REFERENCES dim_area(area),
    is_primaria INTEGER NOT NULL,
    PRIMARY KEY (paper_id, area)
);
"""


def _banco_com_ponte_antiga(caminho) -> None:
    import sqlite3

    db.conectar(caminho).close()
    bruto = sqlite3.connect(caminho)
    bruto.executescript(DDL_ANTIGA_PONTE_AREA)
    bruto.execute(
        "INSERT INTO dim_paper (paper_id, titulo, primeiro_visto_em) "
        "VALUES ('2608.1', 'T', '2026-08-25T09:00:00')"
    )
    bruto.execute(
        "INSERT INTO dim_area (area, definicao, desde) VALUES ('Antiga', 'd', '2026-08-25')"
    )
    bruto.execute(
        "INSERT INTO ponte_paper_area (paper_id, area, is_primaria) VALUES ('2608.1', 'Antiga', 1)"
    )
    bruto.commit()
    bruto.close()


def test_migracao_recria_a_ponte_de_area_com_a_subarea_na_chave(tmp_path):
    """Chave primaria o SQLite so troca recriando a tabela. Os pares antigos sao
    descartados: sao da grade plana, que nao tem sub-area, e nao ha valor
    honesto para a coluna NOT NULL que entra."""
    caminho = tmp_path / "antigo.db"
    _banco_com_ponte_antiga(caminho)

    conn = db.conectar(caminho)
    try:
        assert "subarea" in db.colunas(conn, "ponte_paper_area")
        assert db.contar(conn, "ponte_paper_area") == 0
        assert db.contar(conn, "dim_paper") == 1        # so a ponte foi reconstruida
        assert db.contar(conn, "dim_area") == 1
        db.migrar(conn)   # segunda vez: idempotente, nao recria a tabela de novo
        assert db.colunas(conn, "ponte_paper_area").count("subarea") == 1
        assert db.diagnostico_banco(conn)["tabelas_faltando"] == []
    finally:
        conn.close()


def test_banco_antigo_ganha_a_ponte_de_vertente_ao_abrir(tmp_path):
    """A ponte de vertente e tabela nova: nao precisa de migracao propria porque
    `schema.sql` roda em toda abertura, e o banco de producao a ganha vazia."""
    import sqlite3

    caminho = tmp_path / "sem_vertente.db"
    db.conectar(caminho).close()
    bruto = sqlite3.connect(caminho)
    bruto.executescript("DROP TABLE ponte_paper_vertente;")
    bruto.commit()
    bruto.close()

    conn = db.conectar(caminho)
    try:
        assert db.colunas(conn, "ponte_paper_vertente") == ["paper_id", "vertente", "ordem"]
        assert db.diagnostico_banco(conn)["tabelas_faltando"] == []
    finally:
        conn.close()


def test_a_ponte_de_area_aceita_duas_subareas_irmas_do_mesmo_paper(conn):
    """O par secundario de mesma area com sub-area diferente, que a chave
    `(paper_id, area)` proibia (user story 33)."""
    with db.transacao(conn):
        db.upsert_paper(
            conn, {"paper_id": "2608.1", "titulo": "T", "primeiro_visto_em": db.agora()}
        )
        db.upsert_area(conn, {"area": "Contexto", "definicao": "d"})
        for sub in ("Memória", "RAG"):
            db.upsert_area(conn, {"area": sub, "definicao": "d", "area_pai": "Contexto"})
        for sub, primaria in (("Memória", 1), ("RAG", 0)):
            db.inserir_ignorando(
                conn,
                "ponte_paper_area",
                {"paper_id": "2608.1", "area": "Contexto", "subarea": sub,
                 "is_primaria": primaria},
            )
    assert db.contar(conn, "ponte_paper_area") == 2
