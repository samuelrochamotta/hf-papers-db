import datetime as dt
import sqlite3

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


# ── migracao para o regime do ADR 004 ──────────────────────────────────────

# A `fato_triagem` do regime estrito/amplo, com a ponte de criterios ao lado e
# a coluna derivada `tem_codigo_aberto` em `dim_paper`.
DDL_REGIME_V1 = """
DROP VIEW vw_artefato;
DROP VIEW vw_paper_perfil;
DROP TABLE fato_triagem;
CREATE TABLE fato_triagem (
    paper_id TEXT PRIMARY KEY REFERENCES dim_paper(paper_id),
    veredito TEXT NOT NULL CHECK (veredito IN ('fora','amplo','estrito')),
    regra_fora TEXT, justificativa TEXT, tem_artefato_nomeado INTEGER,
    portabilidade_aprovada INTEGER, portab_depende_nome INTEGER, portab_generalidade INTEGER,
    decisao_fronteira INTEGER DEFAULT 0, fronteira_contraparte TEXT,
    classificado_em TIMESTAMP NOT NULL, run_id TEXT NOT NULL, revisao INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX ix_triagem_veredito ON fato_triagem(veredito);
CREATE TABLE ponte_paper_criterio (
    paper_id TEXT NOT NULL REFERENCES dim_paper(paper_id),
    criterio TEXT NOT NULL,
    PRIMARY KEY (paper_id, criterio)
);
ALTER TABLE dim_paper ADD COLUMN tem_codigo_aberto INTEGER;
"""


def _banco_v1(caminho):
    import sqlite3

    db.conectar(caminho).close()            # schema atual, inclusive dim_paper
    bruto = sqlite3.connect(caminho)
    bruto.executescript(DDL_REGIME_V1)
    for pid in ("2608.1", "2608.2", "2608.3"):
        bruto.execute(
            "INSERT INTO dim_paper (paper_id, titulo, primeiro_visto_em) VALUES (?, 'T', '2026-08-25T09:00:00')",
            (pid,),
        )
    bruto.executemany(
        "INSERT INTO fato_triagem (paper_id, veredito, regra_fora, classificado_em, run_id, revisao, decisao_fronteira) "
        "VALUES (?, ?, ?, '2026-08-25T09:00:00', 'r', 3, 1)",
        [("2608.1", "amplo", None), ("2608.2", "estrito", None), ("2608.3", "fora", "treino_ou_postreino")],
    )
    bruto.execute("INSERT INTO ponte_paper_criterio VALUES ('2608.1', 'benchmark')")
    bruto.commit()
    bruto.close()


def test_migracao_v2_preserva_as_linhas_e_apaga_o_que_morreu(tmp_path):
    """Reconstrucao, porque o CHECK de `veredito` muda. As linhas sobrevivem:
    estrito e amplo viram `aprovado` sem natureza; `fora` guarda a regra que
    tinha, mesmo a que saiu - quem a acusa e o `doutor`."""
    caminho = tmp_path / "v1.db"
    _banco_v1(caminho)

    conn = db.conectar(caminho)
    try:
        linhas = {
            r["paper_id"]: (r["veredito"], r["regra_fora"], r["natureza"], r["revisao"])
            for r in conn.execute("SELECT * FROM fato_triagem")
        }
        assert linhas == {
            "2608.1": ("aprovado", None, None, 3),
            "2608.2": ("aprovado", None, None, 3),
            "2608.3": ("fora", "treino_ou_postreino", None, 3),
        }
        assert "decisao_fronteira" not in db.colunas(conn, "fato_triagem")
        assert db.colunas(conn, "ponte_paper_criterio") == []
        assert "tem_codigo_aberto" not in db.colunas(conn, "dim_paper")
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1   # religada

        db.migrar(conn)   # segunda vez: idempotente, nao reconstroi de novo
        assert db.contar(conn, "fato_triagem") == 3
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "UPDATE fato_triagem SET veredito = 'estrito' WHERE paper_id = '2608.1'"
            )
    finally:
        conn.close()


def test_banco_novo_nasce_no_regime_v2(conn):
    assert "natureza" in db.colunas(conn, "fato_triagem")
    assert "decisao_fronteira" not in db.colunas(conn, "fato_triagem")
    assert db.colunas(conn, "ponte_paper_criterio") == []
    assert db.diagnostico_banco(conn)["tabelas_faltando"] == []


def test_perfis_sao_sincronizados_do_config(tmp_path):
    from hfpapers.config import Perfil

    conn = db.conectar(tmp_path / "p.db")
    try:
        assert [r[0] for r in conn.execute("SELECT perfil FROM dim_perfil ORDER BY ordem")] == [
            "produto", "pesquisa_treino",
        ]
        db.sincronizar_perfis(conn, [Perfil(perfil="tudo_menos_treino", rotulo="X",
                                            prerequisitos=["nenhum", "implementar", "acesso_interno"])])
        assert [tuple(r) for r in conn.execute("SELECT perfil, prerequisito FROM ponte_perfil_prerequisito ORDER BY prerequisito")] == [
            ("tudo_menos_treino", "acesso_interno"), ("tudo_menos_treino", "implementar"),
            ("tudo_menos_treino", "nenhum"),
        ]
        with pytest.raises(sqlite3.IntegrityError):   # degrau que nao existe
            db.sincronizar_perfis(conn, [Perfil(perfil="x", rotulo="X", prerequisitos=["inventado"])])
    finally:
        conn.close()


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


def test_banco_antigo_perde_tax_candidato_ao_abrir(tmp_path):
    """Os candidatos acumulados descrevem uma grade que deixou de existir, e a
    informacao que carregavam ja foi extraida no desenho da nova. A tabela sai
    inteira: o que a substitui - `tax_nao_encaixe` - nao guarda rotulo nenhum."""
    import sqlite3

    caminho = tmp_path / "com_candidato.db"
    db.conectar(caminho).close()
    bruto = sqlite3.connect(caminho)
    bruto.executescript(
        "CREATE TABLE tax_candidato ("
        "  rotulo TEXT NOT NULL, tipo TEXT NOT NULL, definicao TEXT NOT NULL,"
        "  papers TEXT NOT NULL, promovido INTEGER NOT NULL DEFAULT 0,"
        "  criado_em TIMESTAMP NOT NULL, PRIMARY KEY (rotulo, tipo));"
        "INSERT INTO tax_candidato VALUES ('World models', 'topico', 'd', '[]', 0, 'x');"
    )
    bruto.commit()
    bruto.close()

    conn = db.conectar(caminho)
    try:
        assert db.colunas(conn, "tax_candidato") == []
        assert db.colunas(conn, "tax_nao_encaixe") == [
            "paper_id", "eixo", "justificativa", "registrado_em"
        ]
        db.migrar(conn)   # segunda vez: idempotente, nao tenta apagar de novo
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


def test_banco_antigo_perde_a_grade_de_topicos_ao_abrir(tmp_path):
    """A contracao do ticket 05, na abertura: a dimensao de topicos, a ponte
    dela e as areas da grade plana saem juntas do banco.

    A area plana e reconhecida pela forma - raiz sem sub-area -, que e o que a
    distinguia da grade facetada enquanto as duas conviveram. O par facetado
    fica: ele e da grade nova, e so a plana e vocabulario anterior.
    """
    import sqlite3

    caminho = tmp_path / "com_topico.db"
    conn = db.conectar(caminho)
    with db.transacao(conn):
        db.upsert_area(conn, {"area": "Harness & orquestração", "definicao": "d"})
        db.upsert_area(
            conn,
            {"area": "Sistemas multiagente", "definicao": "d", "area_pai": "Harness & orquestração"},
        )
        db.upsert_area(conn, {"area": "Agentes & automação", "definicao": "d"})
        db.upsert_paper(
            conn, {"paper_id": "2608.00001", "titulo": "P", "primeiro_visto_em": db.agora()}
        )
    conn.close()

    bruto = sqlite3.connect(caminho)
    bruto.executescript(
        "CREATE TABLE dim_topico ("
        "  topico TEXT PRIMARY KEY, definicao TEXT NOT NULL, desde DATE);"
        "CREATE TABLE ponte_paper_topico ("
        "  paper_id TEXT NOT NULL, topico TEXT NOT NULL, PRIMARY KEY (paper_id, topico));"
        "INSERT INTO dim_topico VALUES ('Agentes de codificação', 'd', '2026-08-01');"
        "INSERT INTO ponte_paper_topico VALUES ('2608.00001', 'Agentes de codificação');"
    )
    bruto.commit()
    bruto.close()

    conn = db.conectar(caminho)
    try:
        assert db.colunas(conn, "dim_topico") == []
        assert db.colunas(conn, "ponte_paper_topico") == []
        assert [r["area"] for r in conn.execute("SELECT area FROM dim_area ORDER BY area")] == [
            "Harness & orquestração",
            "Sistemas multiagente",
        ]
        db.migrar(conn)   # segunda vez: idempotente, nao tem mais o que apagar
        assert db.contar(conn, "dim_area") == 2
        assert db.diagnostico_banco(conn)["tabelas_faltando"] == []
    finally:
        conn.close()
