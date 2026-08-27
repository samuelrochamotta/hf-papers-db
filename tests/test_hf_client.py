import datetime as dt

import httpx
import pytest
import respx

from hfpapers.config import Config
from hfpapers.fontes.hf_client import ClienteHF, ErroHF


@pytest.fixture()
def cfg_rapido():
    c = Config()
    c.hf.req_por_segundo = 1000     # sem espera artificial no teste
    c.hf.backoff_inicial_s = 0
    c.hf.tentativas = 3
    return c


@respx.mock
def test_daily_papers_parseia_o_lote_real(cfg_rapido, daily_bruto):
    respx.get("https://huggingface.co/api/daily_papers").mock(
        return_value=httpx.Response(200, json=daily_bruto)
    )
    with ClienteHF(cfg_rapido) as c:
        itens = c.daily_papers(dt.date(2026, 8, 25))
    assert len(itens) == 35
    assert all(i.paper.paper_id for i in itens)


@respx.mock
def test_item_invalido_nao_derruba_o_dia(cfg_rapido, daily_bruto):
    corrompido = [*daily_bruto[:3], {"paper": {"sem_id": True}}]
    respx.get("https://huggingface.co/api/daily_papers").mock(
        return_value=httpx.Response(200, json=corrompido)
    )
    with ClienteHF(cfg_rapido) as c:
        itens = c.daily_papers(dt.date(2026, 8, 25))
    assert len(itens) == 3


@respx.mock
def test_429_gera_retentativa(cfg_rapido, daily_bruto):
    rota = respx.get("https://huggingface.co/api/daily_papers").mock(
        side_effect=[
            httpx.Response(429),
            httpx.Response(200, json=daily_bruto[:2]),
        ]
    )
    with ClienteHF(cfg_rapido) as c:
        itens = c.daily_papers(dt.date(2026, 8, 25))
    assert rota.call_count == 2
    assert len(itens) == 2


@respx.mock
def test_404_nao_retenta(cfg_rapido):
    rota = respx.get("https://huggingface.co/api/papers/2608.00000").mock(
        return_value=httpx.Response(404)
    )
    with ClienteHF(cfg_rapido) as c:
        with pytest.raises(ErroHF):
            c.paper("2608.00000")
    assert rota.call_count == 1


@respx.mock
def test_paper_usa_id_base_na_url(cfg_rapido, paper_bruto):
    rota = respx.get("https://huggingface.co/api/papers/2608.23552").mock(
        return_value=httpx.Response(200, json=paper_bruto)
    )
    with ClienteHF(cfg_rapido) as c:
        p = c.paper("2608.23552v2")
    assert rota.called
    assert p.paper_id == "2608.23552"
