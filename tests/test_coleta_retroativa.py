"""Coleta retroativa: o laco de dias antigos, e o que ele promete nao fazer.

O contrato observavel e o conteudo do banco depois da varredura: quais papers
entraram, com que `data_hf_daily`, quantos ficaram sem enriquecimento, e o que
NAO apareceu - nenhuma linha de triagem, nenhuma chamada de modelo.
"""

from __future__ import annotations

import datetime as dt

import httpx
import respx

import coleta_retroativa as retro
from hfpapers import db
from hfpapers.config import Config
from hfpapers.estagios import coleta
from hfpapers.fontes.hf_client import ClienteHF
from hfpapers.fontes.modelos import ItemDiario

HOJE = dt.date(2026, 9, 7)


def _cliente():
    c = Config()
    c.hf.req_por_segundo = 1000
    c.hf.backoff_inicial_s = 0
    return ClienteHF(c)


def _item(paper_id: str, dia: dt.date) -> dict:
    return {
        "paper": {
            "id": paper_id,
            "title": f"Paper {paper_id}",
            "summary": "resumo",
            "submittedOnDailyAt": f"{dia.isoformat()}T00:00:00.000Z",
            "publishedAt": f"{(dia - dt.timedelta(days=2)).isoformat()}T00:00:00.000Z",
            "upvotes": 3,
        },
        "numComments": 1,
    }


def _feed(por_dia: dict[str, list[dict]]):
    """Rota de daily_papers que responde conforme o parametro `date`."""

    def responder(request: httpx.Request) -> httpx.Response:
        data = request.url.params.get("date")
        return httpx.Response(200, json=por_dia.get(data, []))

    return responder


def _detalhe(request: httpx.Request, **kw) -> httpx.Response:
    pid = request.url.path.rsplit("/", 1)[-1]
    return httpx.Response(
        200,
        json={
            "id": pid,
            "title": f"Paper {pid}",
            "numTotalModels": 2,
            "numTotalDatasets": 1,
            "numTotalSpaces": 0,
        },
    )


def _rotas(por_dia: dict[str, list[dict]]):
    """Devolve (rota do feed diario, rota do detalhe) para quem conta requisicao."""
    feed = respx.get("https://huggingface.co/api/daily_papers").mock(
        side_effect=_feed(por_dia)
    )
    detalhe = respx.route(method="GET", path__startswith="/api/papers/").mock(
        side_effect=_detalhe
    )
    return feed, detalhe


@respx.mock
def test_janela_traz_os_papers_de_cada_dia(conn):
    _rotas(
        {
            "2026-05-04": [_item("2605.00001", dt.date(2026, 5, 4))],
            "2026-05-05": [
                _item("2605.00002", dt.date(2026, 5, 5)),
                _item("2605.00003", dt.date(2026, 5, 5)),
            ],
        }
    )
    with _cliente() as c:
        r = retro.rodar(
            conn, c, inicio=dt.date(2026, 5, 4), fim=dt.date(2026, 5, 5), hoje=HOJE
        )

    assert r.novos == 3
    assert db.contar(conn, "dim_paper") == 3
    assert r.por_dia == {"2026-05-04": 1, "2026-05-05": 2}


@respx.mock
def test_paper_retroativo_entra_enriquecido(conn):
    _rotas({"2026-05-04": [_item("2605.00001", dt.date(2026, 5, 4))]})
    with _cliente() as c:
        r = retro.rodar(
            conn, c, inicio=dt.date(2026, 5, 4), fim=dt.date(2026, 5, 4), hoje=HOJE
        )

    assert r.enriquecidos == 1
    linha = conn.execute(
        "SELECT enriquecido_em FROM dim_paper WHERE paper_id = ?", ("2605.00001",)
    ).fetchone()
    assert linha["enriquecido_em"] is not None
    metrica = conn.execute(
        "SELECT qtd_modelos FROM fato_metrica WHERE paper_id = ? AND origem = 'por_paper'",
        ("2605.00001",),
    ).fetchone()
    assert metrica["qtd_modelos"] == 2


@respx.mock
def test_retomada_nao_duplica_paper_nem_reconsulta_dia_pronto(conn):
    por_dia = {
        "2026-05-04": [_item("2605.00001", dt.date(2026, 5, 4))],
        "2026-05-05": [_item("2605.00002", dt.date(2026, 5, 5))],
    }
    feed, detalhe = _rotas(por_dia)
    janela = dict(inicio=dt.date(2026, 5, 4), fim=dt.date(2026, 5, 5), hoje=HOJE)
    with _cliente() as c:
        retro.rodar(conn, c, **janela)
        requisicoes = feed.call_count, detalhe.call_count
        segunda = retro.rodar(conn, c, **janela)

    assert db.contar(conn, "dim_paper") == 2
    assert segunda.dias == []
    assert (feed.call_count, detalhe.call_count) == requisicoes


@respx.mock
def test_dia_coletado_sem_enriquecimento_e_completado_na_retomada(conn):
    """Estado que uma queda entre os dois estagios deixa no banco."""
    dia = dt.date(2026, 5, 4)
    itens = [ItemDiario.model_validate(_item("2605.00001", dia))]
    with db.transacao(conn):
        coleta.gravar_itens(conn, itens, data_snapshot=HOJE)

    _rotas({dia.isoformat(): [_item("2605.00001", dia)]})
    with _cliente() as c:
        r = retro.rodar(conn, c, inicio=dia, fim=dia, hoje=HOJE)

    assert r.enriquecidos == 1
    assert db.contar(conn, "dim_paper") == 1
    assert db.contar(conn, "dim_paper", "enriquecido_em IS NULL") == 0


@respx.mock
def test_varredura_nao_classifica_nem_chama_modelo(conn):
    _rotas(
        {
            "2026-05-04": [_item("2605.00001", dt.date(2026, 5, 4))],
            "2026-06-01": [_item("2606.00001", dt.date(2026, 6, 1))],
        }
    )
    with _cliente() as c:
        r = retro.rodar(
            conn,
            c,
            inicio=dt.date(2026, 5, 4),
            fim=dt.date(2026, 6, 1),
            hoje=HOJE,
            run_id="retro-teste",
        )

    conf = retro.conferir(conn, inicio=dt.date(2026, 5, 4), fim=dt.date(2026, 6, 1),
                          run_id=r.run_id)
    assert conf.chamadas_llm == 0
    assert conf.triagens == 0
    assert conf.por_mes == {"2026-05": 1, "2026-06": 1}
    assert conf.sem_enriquecimento == 0

    linha = conn.execute(
        "SELECT status, qtd_coletados, custo_usd FROM log_execucao WHERE run_id = ?",
        ("retro-teste",),
    ).fetchone()
    assert linha["status"] == "ok"
    assert linha["qtd_coletados"] == 2
    assert linha["custo_usd"] == 0


@respx.mock
def test_dia_magro_nao_vira_aviso_de_coleta_suspeita(conn):
    """O piso de papers por dia util calibra a rodada diaria, nao a varredura."""
    _rotas({"2026-05-04": [_item("2605.00001", dt.date(2026, 5, 4))]})
    with _cliente() as c:
        r = retro.rodar(conn, c, inicio=dt.date(2026, 5, 4), fim=dt.date(2026, 5, 4),
                        hoje=HOJE)
    assert r.avisos == []
