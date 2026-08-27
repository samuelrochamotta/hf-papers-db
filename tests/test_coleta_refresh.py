import datetime as dt

import httpx
import respx

from hfpapers import db
from hfpapers.config import Config
from hfpapers.estagios import coleta, refresh
from hfpapers.fontes.hf_client import ClienteHF
from hfpapers.fontes.modelos import ItemDiario

HOJE = dt.date(2026, 8, 26)


def _cliente():
    c = Config()
    c.hf.req_por_segundo = 1000
    c.hf.backoff_inicial_s = 0
    return ClienteHF(c)


def test_gravar_itens_e_idempotente(conn, daily_bruto):
    itens = [ItemDiario.model_validate(x) for x in daily_bruto]
    with db.transacao(conn):
        novos, ja = coleta.gravar_itens(conn, itens, data_snapshot=HOJE)
    assert len(novos) == 35 and ja == 0

    with db.transacao(conn):
        novos2, ja2 = coleta.gravar_itens(conn, itens, data_snapshot=HOJE)
    assert novos2 == [] and ja2 == 35
    assert db.contar(conn, "dim_paper") == 35
    assert db.contar(conn, "fato_metrica") == 35


def test_gravar_itens_preenche_pontes(conn, daily_bruto):
    itens = [ItemDiario.model_validate(x) for x in daily_bruto[:5]]
    with db.transacao(conn):
        coleta.gravar_itens(conn, itens, data_snapshot=HOJE)
    assert db.contar(conn, "ponte_paper_autor") > 0
    assert db.contar(conn, "ponte_paper_keyword") > 0


@respx.mock
def test_coleta_marca_dia_util_com_poucos_papers(conn, daily_bruto):
    respx.get("https://huggingface.co/api/daily_papers").mock(
        return_value=httpx.Response(200, json=daily_bruto[:5])
    )
    with _cliente() as c:
        r = coleta.rodar(conn, c, datas=[dt.date(2026, 8, 25)], hoje=HOJE)
    assert any(a.startswith("coleta_suspeita") for a in r.avisos)


@respx.mock
def test_fim_de_semana_vazio_nao_e_erro(conn):
    respx.get("https://huggingface.co/api/daily_papers").mock(
        return_value=httpx.Response(200, json=[])
    )
    with _cliente() as c:
        r = coleta.rodar(conn, c, datas=[dt.date(2026, 8, 22)], hoje=HOJE)
    assert r.coletados == 0 and r.avisos == []


def test_dias_faltantes_cobre_a_lacuna(conn, daily_bruto):
    itens = [ItemDiario.model_validate(x) for x in daily_bruto[:1]]
    with db.transacao(conn):
        coleta.gravar_itens(conn, itens, data_snapshot=dt.date(2026, 8, 25))
    ultimo = db.max_data_hf(conn)
    faltantes = coleta.dias_faltantes(conn, hoje=ultimo + dt.timedelta(days=3))
    assert len(faltantes) == 3
    assert faltantes[0] == ultimo + dt.timedelta(days=1)


@respx.mock
def test_refresh_usa_uma_requisicao_por_data(conn, daily_bruto):
    """35 papers, 1 data -> 1 requisicao. E a economia da secao 2.3."""
    itens = [ItemDiario.model_validate(x) for x in daily_bruto]
    with db.transacao(conn):
        coleta.gravar_itens(conn, itens, data_snapshot=dt.date(2026, 8, 25))

    subiu = []
    for x in daily_bruto:
        y = dict(x)
        y["paper"] = {**x["paper"], "upvotes": (x["paper"].get("upvotes") or 0) + 10}
        subiu.append(y)
    rota = respx.get("https://huggingface.co/api/daily_papers").mock(
        return_value=httpx.Response(200, json=subiu)
    )

    cfg = Config().refresh
    with _cliente() as c:
        r = refresh.rodar(conn, c, cfg, hoje=HOJE, forcar_semanal=False)

    assert rota.call_count == 1
    assert r.papers_atualizados == 35
    # dois snapshots por paper: o do dia da coleta e o de hoje
    assert db.contar(conn, "fato_metrica") == 70
    novo = conn.execute(
        "SELECT upvotes FROM fato_metrica WHERE data_snapshot = ? ORDER BY paper_id LIMIT 1",
        (HOJE.isoformat(),),
    ).fetchone()
    antigo = conn.execute(
        "SELECT upvotes FROM fato_metrica WHERE data_snapshot = ? ORDER BY paper_id LIMIT 1",
        ("2026-08-25",),
    ).fetchone()
    assert novo["upvotes"] == antigo["upvotes"] + 10
