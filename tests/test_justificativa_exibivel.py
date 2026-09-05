"""`justificativa_exibivel` e os tres pontos onde o painel a consome (issue #2).

O app nao pode mostrar como "motivo da decisao" uma justificativa que so
registra falha de infra do Estagio B, nem um cabecalho vazio.
`justificativa_exibivel` e o unico lugar que decide
isso - `montar_hall` (aprovados e descartados) e `montar_dados` (lista viva)
tem de concordar com ela, sem reimplementar a regra.

Nao basta a linha executar: os testes de consumidor abaixo travam o par
`(j, h)` inteiro, nao so um dos dois campos, senao um consumidor que ignorasse
o codigo devolvido (por exemplo, sempre gravando `h=0`) passaria mesmo assim
sempre que a justificativa de teste fosse texto normal.
"""

from __future__ import annotations

import datetime as dt

import pytest
from gerar_painel import PREFIXO_FALLBACK, justificativa_exibivel

# Fixa e distante de "hoje" de proposito: os testes de `montar_dados` abaixo
# nao podem depender do relogio da maquina que roda a suite. `JANELA_LONGA`
# garante que `DIA` sempre caiba dentro da janela viva, para qualquer data real
# deste seculo.
DIA = dt.date(2020, 1, 1)
JANELA_LONGA = 100_000


# ══════════════ os codigos ══════════════

def test_texto_normal_passa_intacto_com_codigo_zero():
    assert justificativa_exibivel({"justificativa": "o payload principal e treino"}) == (
        "o payload principal e treino", 0
    )


def test_justificativa_de_fallback_do_estagio_b_e_codigo_dois():
    triagem = {"justificativa": PREFIXO_FALLBACK + " timeout na chamada"}
    assert justificativa_exibivel(triagem) == ("", 2)


def test_ausencia_de_justificativa_e_codigo_tres():
    assert justificativa_exibivel({"justificativa": ""}) == ("", 3)


def test_chave_justificativa_ausente_tambem_e_codigo_tres():
    """`triagem.get("justificativa")` sem a chave e o mesmo que string vazia."""
    assert justificativa_exibivel({}) == ("", 3)


# ══════════════ procedencia nao decide mais nada ══════════════

def test_run_id_nao_muda_o_codigo():
    """O codigo 1 morreu com o backfill: todo veredito sai do pipeline, entao a
    linha vale pelo texto que carrega, venha do `run_id` que vier."""
    triagem = {"run_id": "run-20260901-074155", "justificativa": "motivo forte"}
    assert justificativa_exibivel(triagem) == ("motivo forte", 0)
    assert justificativa_exibivel({**triagem, "justificativa": ""}) == ("", 3)


# ══════════════ os consumidores concordam (montar_dados) ══════════════

def _tabelas(papers, triagem):
    return {
        "dim_paper": papers,
        "fato_triagem": triagem,
        "dim_ficha": [],
        "ponte_paper_area": [],
        "ponte_paper_topico": [],
        "fato_metrica": [],
        "dim_area": [],
        "dim_topico": [],
    }


def _montar_dados_com(tmp_path, monkeypatch, papers, triagem):
    import gerar_painel

    (tmp_path / "_manifest.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(gerar_painel, "DIR_MARTS", tmp_path)
    # Isola tambem o config.yaml real do repo: sem isso `modelos()` e
    # `janela_hall()` leriam o arquivo versionado, amarrando um teste unitario
    # a um estado que nao e dele (mesmo sem nenhuma asserção sobre o valor).
    monkeypatch.setattr(gerar_painel, "CONFIG", tmp_path / "config-inexistente.yaml")
    tabelas = _tabelas(papers, triagem)
    monkeypatch.setattr(gerar_painel, "ler", lambda nome: tabelas.get(nome, []))

    dados, _manifest = gerar_painel.montar_dados(janela=JANELA_LONGA, dias_hall=JANELA_LONGA)
    return dados


def test_lista_so_embute_justificativa_para_veredito_diferente_de_fora(tmp_path, monkeypatch):
    """Restricao de peso da issue: um `fora` na janela viva nao pode carregar `j`/`h`.

    A janela tem ~2500 papers e a maioria e `fora` - se cada um carregasse um
    cabecalho vazio (`j: "", h: 3`) o `DADOS` embutido cresceria por nada. A
    chave tem de estar simplesmente ausente, nao vazia.
    """
    papers = [
        {"paper_id": "aprovado", "titulo": "A", "data_hf_daily": DIA, "data_arxiv": DIA,
         "upvotes_atual": 10, "organizacao": "org", "url_hf": "https://x/a"},
        {"paper_id": "fora", "titulo": "B", "data_hf_daily": DIA, "data_arxiv": DIA,
         "upvotes_atual": 5, "organizacao": "org", "url_hf": "https://x/b"},
    ]
    triagem = [
        {"paper_id": "aprovado", "veredito": "estrito", "justificativa": "motivo forte"},
        {"paper_id": "fora", "veredito": "fora", "justificativa": "motivo do descarte"},
    ]
    dados = _montar_dados_com(tmp_path, monkeypatch, papers, triagem)
    por_id = {p["id"]: p for p in dados["papers"]}

    assert por_id["aprovado"]["j"] == "motivo forte"
    assert por_id["aprovado"]["h"] == 0
    assert "j" not in por_id["fora"]
    assert "h" not in por_id["fora"]


@pytest.mark.parametrize("veredito", ["estrito", "amplo"])
def test_lista_embute_justificativa_para_qualquer_veredito_aprovado(tmp_path, monkeypatch, veredito):
    papers = [{"paper_id": "p1", "titulo": "A", "data_hf_daily": DIA, "data_arxiv": DIA,
               "upvotes_atual": 10, "organizacao": "org", "url_hf": "https://x/a"}]
    triagem = [{"paper_id": "p1", "veredito": veredito, "justificativa": "motivo"}]
    dados = _montar_dados_com(tmp_path, monkeypatch, papers, triagem)
    entrada = dados["papers"][0]

    assert entrada["j"] == "motivo"
    assert entrada["h"] == 0


@pytest.mark.parametrize(
    "extra_triagem, esperado",
    [
        pytest.param(
            {"justificativa": PREFIXO_FALLBACK + " timeout"}, ("", 2),
            id="fallback-estagio-b",
        ),
        pytest.param(
            {"justificativa": ""}, ("", 3),
            id="sem-justificativa",
        ),
    ],
)
def test_lista_repassa_o_codigo_que_justificativa_exibivel_devolveu(
    tmp_path, monkeypatch, extra_triagem, esperado
):
    """Fecha o buraco que `test_lista_embute_justificativa_...` deixava aberto.

    Aqueles testes so usam justificativa de texto normal (codigo 0): um
    consumidor que ignorasse `justificativa_exibivel` e sempre gravasse
    `h=0` passaria por eles do mesmo jeito. Aqui o `(j, h)` inteiro que
    `montar_dados` grava tem de bater com o que a funcao pura devolveria -
    caso concreto e nao hipotetico: `estagios/classificacao.py` grava
    `veredito="amplo"` com o prefixo de fallback quando o Estagio B falha,
    e essa linha cai na janela viva do mesmo jeito que um "amplo" comum.
    """
    papers = [{"paper_id": "p1", "titulo": "A", "data_hf_daily": DIA, "data_arxiv": DIA,
               "upvotes_atual": 10, "organizacao": "org", "url_hf": "https://x/a"}]
    triagem = [{"paper_id": "p1", "veredito": "amplo", **extra_triagem}]
    dados = _montar_dados_com(tmp_path, monkeypatch, papers, triagem)
    entrada = dados["papers"][0]

    assert (entrada["j"], entrada["h"]) == esperado
