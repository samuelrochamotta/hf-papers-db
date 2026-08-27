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
