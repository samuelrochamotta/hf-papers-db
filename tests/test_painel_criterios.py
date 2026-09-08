"""O contrato de `DADOS`: criterios de veredito, contraparte de fronteira e o
par area > sub-area.

O painel passou a responder duas perguntas novas - "por que o pipeline aprova"
(o grafico) e "por que ESTE paper e estrito" (a ficha) - e as duas leem os
mesmos dois campos: a lista de criterios do paper e, quando houve decisao de
fronteira, o rotulo que quase venceu.

Os testes aqui travam o contrato de `montar_dados`/`montar_hall` com o app:
quais entradas carregam `cr`/`fc`, em que ordem, e quais NAO carregam (peso do
arquivo). O mapa enum -> rotulo legivel nao e testado aqui de proposito: ele
mora em `painel_app.js`, porque so o navegador o consome.
"""

from __future__ import annotations

import datetime as dt

DIA = dt.date(2020, 1, 1)
JANELA_LONGA = 100_000


def _tabelas(papers, triagem, criterios, fichas=None, areas=None, vertentes=None):
    return {
        "dim_paper": papers,
        "fato_triagem": triagem,
        "dim_ficha": fichas or [],
        "ponte_paper_area": areas or [],
        "ponte_paper_vertente": vertentes or [],
        "ponte_paper_criterio": criterios,
        "fato_metrica": [],
        "dim_area": [],
    }


def _montar(
    tmp_path, monkeypatch, papers, triagem, criterios, *, areas=None, vertentes=None,
    dias_hall=JANELA_LONGA,
):
    import gerar_painel

    (tmp_path / "_manifest.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(gerar_painel, "DIR_MARTS", tmp_path)
    monkeypatch.setattr(gerar_painel, "CONFIG", tmp_path / "config-inexistente.yaml")
    tabelas = _tabelas(papers, triagem, criterios, areas=areas, vertentes=vertentes)
    monkeypatch.setattr(gerar_painel, "ler", lambda nome: tabelas.get(nome, []))
    dados, _ = gerar_painel.montar_dados(janela=JANELA_LONGA, dias_hall=dias_hall)
    return dados


def _paper(pid, **extra):
    return {
        "paper_id": pid, "titulo": "T " + pid, "data_hf_daily": DIA, "data_arxiv": DIA,
        "upvotes_atual": 10, "organizacao": "org", "url_hf": "https://x/" + pid, **extra,
    }


def _triado(pid, veredito, **extra):
    return {"paper_id": pid, "veredito": veredito, "justificativa": "motivo forte", **extra}


# ══════════════ a lista da janela viva ══════════════

def test_paper_carrega_a_vertente_com_a_dominante_em_primeiro(tmp_path, monkeypatch):
    """O painel exibe a vertente no lugar do topico, e a ordem e informacao: a
    de ordem 1 e a dominante e precisa aparecer primeiro no card, qualquer que
    seja a ordem em que o Parquet devolveu as linhas."""
    dados = _montar(
        tmp_path, monkeypatch,
        [_paper("p1")],
        [_triado("p1", "estrito")],
        [],
        vertentes=[
            {"paper_id": "p1", "vertente": "Escalar", "ordem": 2},
            {"paper_id": "p1", "vertente": "Baratear", "ordem": 1},
        ],
    )
    assert dados["papers"][0]["vt"] == ["Baratear", "Escalar"]


def test_aprovado_carrega_a_lista_de_criterios(tmp_path, monkeypatch):
    dados = _montar(
        tmp_path, monkeypatch,
        [_paper("p1")],
        [_triado("p1", "estrito")],
        [{"paper_id": "p1", "criterio": "artefato_aberto"},
         {"paper_id": "p1", "criterio": "benchmark"}],
    )
    assert dados["papers"][0]["cr"] == ["artefato_aberto", "benchmark"]


def test_criterios_saem_em_ordem_estavel(tmp_path, monkeypatch):
    """O painel e commitado todo dia: a ordem da ponte nao pode virar diff.

    O Parquet devolve as linhas na ordem em que o banco as gravou, que nao e
    garantida entre rodadas. Sem ordenacao, dois papers com os mesmos dois
    criterios sairiam ora numa ordem ora noutra e o commit diario ganharia um
    diff que nao significa nada - o mesmo motivo de `por_voto` desempatar.
    """
    dados = _montar(
        tmp_path, monkeypatch,
        [_paper("p1")],
        [_triado("p1", "estrito")],
        [{"paper_id": "p1", "criterio": "vulnerabilidade"},
         {"paper_id": "p1", "criterio": "artefato_aberto"},
         {"paper_id": "p1", "criterio": "padrao_arquitetural"}],
    )
    assert dados["papers"][0]["cr"] == [
        "artefato_aberto", "padrao_arquitetural", "vulnerabilidade"
    ]


def test_criterio_repetido_na_ponte_conta_uma_vez(tmp_path, monkeypatch):
    """A barra do grafico conta ocorrencia de paper, nao linha de tabela."""
    dados = _montar(
        tmp_path, monkeypatch,
        [_paper("p1")],
        [_triado("p1", "amplo")],
        [{"paper_id": "p1", "criterio": "benchmark"},
         {"paper_id": "p1", "criterio": "benchmark"}],
    )
    assert dados["papers"][0]["cr"] == ["benchmark"]


def test_aprovado_sem_criterio_carrega_lista_vazia(tmp_path, monkeypatch):
    """Linha antiga, anterior a `criterios_veredito`: existe e nao tem criterio.

    A chave sai vazia em vez de ausente para o app poder distinguir "aprovado
    sem criterio registrado" de "paper que nem e aprovado" sem consultar `v`.
    """
    dados = _montar(tmp_path, monkeypatch, [_paper("p1")], [_triado("p1", "amplo")], [])
    assert dados["papers"][0]["cr"] == []


def test_descartado_nao_carrega_criterios(tmp_path, monkeypatch):
    """Mesma restricao de peso de `j`/`h`: a maioria da janela e `fora`."""
    dados = _montar(
        tmp_path, monkeypatch,
        [_paper("p1")],
        [_triado("p1", "fora", regra_fora="fora_de_escopo")],
        [],
    )
    assert "cr" not in dados["papers"][0]


def test_descartado_nao_carrega_marca_de_fronteira(tmp_path, monkeypatch):
    """`fr` e do cabecalho da decisao, que so os aprovados renderizam.

    Um `fora` com `decisao_fronteira` existe (o veredito podia ter ido para o
    outro lado), mas ninguem le esse campo nele: o selo sai de
    `cabecalhoDecisao`, alcancavel so por aprovado, e a lista de descartados do
    hall nem carrega `fr`. Fora do bloco dos aprovados ele viajava em ~315
    papers da janela sem leitor.
    """
    dados = _montar(
        tmp_path, monkeypatch,
        [_paper("p1")],
        [_triado("p1", "fora", regra_fora="fora_de_escopo", decisao_fronteira=True,
                 fronteira_contraparte="benchmark")],
        [],
    )
    entrada = dados["papers"][0]
    assert "fr" not in entrada
    assert "fc" not in entrada


# ══════════════ contraparte da fronteira ══════════════

def test_fronteira_carrega_a_contraparte(tmp_path, monkeypatch):
    dados = _montar(
        tmp_path, monkeypatch,
        [_paper("p1")],
        [_triado("p1", "estrito", decisao_fronteira=True,
                 fronteira_contraparte="benchmark")],
        [{"paper_id": "p1", "criterio": "artefato_aberto"}],
    )
    entrada = dados["papers"][0]
    assert entrada["fr"] == 1
    assert entrada["fc"] == "benchmark"


def test_sem_fronteira_nao_carrega_contraparte(tmp_path, monkeypatch):
    dados = _montar(
        tmp_path, monkeypatch,
        [_paper("p1")], [_triado("p1", "estrito")],
        [{"paper_id": "p1", "criterio": "artefato_aberto"}],
    )
    assert "fc" not in dados["papers"][0]


def test_fronteira_sem_contraparte_registrada_nao_inventa_chave(tmp_path, monkeypatch):
    """Linha antiga com `decisao_fronteira` e contraparte nula.

    O selo generico ("decisão de fronteira") continua saindo pelo `fr`; o que
    nao pode acontecer e o app imprimir "fronteira: quase null".
    """
    dados = _montar(
        tmp_path, monkeypatch,
        [_paper("p1")],
        [_triado("p1", "estrito", decisao_fronteira=True, fronteira_contraparte=None)],
        [],
    )
    entrada = dados["papers"][0]
    assert entrada["fr"] == 1
    assert "fc" not in entrada


# ══════════════ o hall le o mesmo contrato ══════════════

def test_aprovado_do_hall_carrega_criterios_e_contraparte(tmp_path, monkeypatch):
    """A ficha do hall usa o mesmo cabecalho de decisao da aba viva.

    Se so a janela carregasse `cr`, a mesma funcao do app desenharia a linha do
    veredito completa numa aba e truncada na outra.
    """
    dados = _montar(
        tmp_path, monkeypatch,
        [_paper("p1")],
        [_triado("p1", "estrito", decisao_fronteira=True,
                 fronteira_contraparte="fora_de_escopo")],
        [{"paper_id": "p1", "criterio": "artefato_aberto"}],
        dias_hall=-1,   # corte no futuro: o paper sai da janela e cai no hall
    )
    entrada = dados["hall"][0]["ap"][0]
    assert entrada["cr"] == ["artefato_aberto"]
    assert entrada["fc"] == "fora_de_escopo"


def test_descartado_do_hall_nao_carrega_criterios(tmp_path, monkeypatch):
    dados = _montar(
        tmp_path, monkeypatch,
        [_paper("p1")],
        [_triado("p1", "fora", regra_fora="fora_de_escopo")],
        [],
        dias_hall=-1,
    )
    entrada = dados["hall"][0]["de"][0]
    assert "cr" not in entrada


# ══════════════ a ponte nao mistura papers ══════════════

def test_criterio_de_um_paper_nao_vaza_para_o_outro(tmp_path, monkeypatch):
    dados = _montar(
        tmp_path, monkeypatch,
        [_paper("p1"), _paper("p2")],
        [_triado("p1", "estrito"), _triado("p2", "amplo")],
        [{"paper_id": "p1", "criterio": "artefato_aberto"},
         {"paper_id": "p2", "criterio": "panorama"}],
    )
    por_id = {p["id"]: p for p in dados["papers"]}
    assert por_id["p1"]["cr"] == ["artefato_aberto"]
    assert por_id["p2"]["cr"] == ["panorama"]


# ══════════════ o par area > sub-area ══════════════

PAR_PRIMARIO = {
    "paper_id": "p1",
    "area": "Contexto & recuperação",
    "subarea": "Memória de longo prazo",
    "is_primaria": True,
}


def test_a_subarea_do_par_primario_chega_ao_painel(tmp_path, monkeypatch):
    """Quem le o painel enxerga em que peca do sistema o paper mexe e em que
    sub-area dela - o par inteiro, nao so o nivel de cima."""
    dados = _montar(
        tmp_path, monkeypatch,
        [_paper("p1")],
        [_triado("p1", "estrito")],
        [],
        areas=[PAR_PRIMARIO],
    )
    p = dados["papers"][0]
    assert (p["a"], p["sa"]) == ("Contexto & recuperação", "Memória de longo prazo")


def test_a_subarea_acompanha_o_paper_ate_a_aba_historica(tmp_path, monkeypatch):
    """O hall e derivado dos mesmos Parquet: perder a sub-area la deixaria o
    podio dizendo menos do que a janela viva."""
    dados = _montar(
        tmp_path, monkeypatch,
        [_paper("p1")],
        [_triado("p1", "estrito")],
        [],
        areas=[PAR_PRIMARIO],
        dias_hall=-1,      # corte no futuro: o paper sai da janela e entra no hall
    )
    entrada = dados["hall"][0]["ap"][0]
    assert (entrada["a"], entrada["sa"]) == ("Contexto & recuperação", "Memória de longo prazo")


def test_paper_sem_par_nao_inventa_subarea(tmp_path, monkeypatch):
    dados = _montar(tmp_path, monkeypatch, [_paper("p1")], [_triado("p1", "amplo")], [])
    assert (dados["papers"][0]["a"], dados["papers"][0]["sa"]) == (None, None)
