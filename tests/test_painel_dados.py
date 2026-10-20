"""O contrato de `DADOS` no regime do ADR 004: classificacao, vocabulario,
perfis e o par area > sub-area.

Os testes travam o que `montar_dados`/`montar_hall` entregam ao app: quais
entradas carregam degrau, natureza, textos e links, em que ordem os
vocabularios viajam, e quais NAO carregam nada disso (peso do arquivo). O
desenho e o recorte sao testados do lado do navegador, em `tests/js/`.
"""

from __future__ import annotations

import datetime as dt

from gerar_painel import NAO_CLASSIFICADO

DIA = dt.date(2020, 1, 1)
JANELA_LONGA = 100_000

PAR_PRIMARIO = {
    "paper_id": "p1", "area": "Contexto & recuperação",
    "subarea": "Memória de longo prazo", "is_primaria": True,
}

VOCAB = {
    # fora de ordem de proposito: quem ordena e `ordem`, nao o Parquet
    "dim_prerequisito": [
        {"prerequisito": "treino", "rotulo": "Treino", "definicao": "d4", "ordem": 4},
        {"prerequisito": "nenhum", "rotulo": "Nenhum", "definicao": "d1", "ordem": 1},
        {"prerequisito": "sem_acao", "rotulo": "Sem ação", "definicao": "d5", "ordem": 5},
        {"prerequisito": "implementar", "rotulo": "Implementar", "definicao": "d2", "ordem": 2},
        {"prerequisito": "acesso_interno", "rotulo": "Acesso interno", "definicao": "d3", "ordem": 3},
    ],
    "dim_natureza": [
        {"natureza": "panorama", "rotulo": "Panorama", "definicao": "", "ordem": 4},
        {"natureza": "proposta", "rotulo": "Proposta", "definicao": "", "ordem": 1},
    ],
    "dim_perfil": [
        {"perfil": "pesquisa_treino", "rotulo": "Treino/pesquisa", "ordem": 2},
        {"perfil": "produto", "rotulo": "Produto", "ordem": 1},
    ],
    "ponte_perfil_prerequisito": [
        {"perfil": "produto", "prerequisito": "nenhum"},
        {"perfil": "produto", "prerequisito": "implementar"},
        {"perfil": "pesquisa_treino", "prerequisito": "treino"},
    ],
}


def _montar(tmp_path, monkeypatch, papers, triagem, *, areas=None, vertentes=None,
            grade=None, fichas=None, dias_hall=JANELA_LONGA):
    import gerar_painel

    (tmp_path / "_manifest.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(gerar_painel, "DIR_MARTS", tmp_path)
    monkeypatch.setattr(gerar_painel, "CONFIG", tmp_path / "config-inexistente.yaml")
    tabelas = {
        "dim_paper": papers,
        "fato_triagem": triagem,
        "dim_ficha": fichas or [],
        "ponte_paper_area": areas or [],
        "ponte_paper_vertente": vertentes or [],
        "fato_metrica": [],
        "dim_area": grade or [],
        **VOCAB,
    }
    monkeypatch.setattr(gerar_painel, "ler", lambda nome: tabelas.get(nome, []))
    dados, _ = gerar_painel.montar_dados(janela=JANELA_LONGA, dias_hall=dias_hall)
    return dados


def _paper(pid, **extra):
    return {
        "paper_id": pid, "titulo": "T " + pid, "data_hf_daily": DIA, "data_arxiv": DIA,
        "upvotes_atual": 10, "organizacao": "org", "url_hf": "https://x/" + pid, **extra,
    }


def _triado(pid, veredito="aprovado", **extra):
    base = {"paper_id": pid, "veredito": veredito, "justificativa": "motivo forte"}
    if veredito == "fora":
        base["regra_fora"] = "geracao_de_midia"
    return {**base, **extra}


# ══════════════ classificacao na lista da janela ══════════════

def test_aprovado_carrega_degrau_natureza_textos_e_links(tmp_path, monkeypatch):
    dados = _montar(
        tmp_path, monkeypatch,
        [_paper("p1", github_repo="https://github.com/x/y", project_page="https://p")],
        [_triado("p1", prerequisito="nenhum", natureza="proposta",
                 pratica_contradita="reusar o mesmo prompt", falta_o_como=None,
                 artefato_aberto=True)],
    )
    p = dados["papers"][0]
    assert (p["v"], p["pr"], p["nt"], p["ao"]) == ("aprovado", "nenhum", "proposta", 1)
    assert p["pc"] == "reusar o mesmo prompt"
    assert "fo" not in p                       # texto ausente nao viaja vazio
    assert (p["gh"], p["pg"], p["oa"]) == ("https://github.com/x/y", "https://p", 1)


def test_descartado_nao_carrega_classificacao(tmp_path, monkeypatch):
    """Restricao de peso: a maioria dos papers da janela pode ser `fora`, e
    chave vazia repetida vira quilobyte. O descartado leva o repositorio so
    como coordenada da dispersao (`oa`)."""
    dados = _montar(
        tmp_path, monkeypatch,
        [_paper("p1", github_repo="https://github.com/x/y")],
        [_triado("p1", "fora")],
    )
    p = dados["papers"][0]
    assert p["rf"] == "geracao_de_midia" and p["oa"] == 1
    for chave in ("pr", "nt", "ao", "pc", "fo", "gh", "pg", "j", "h"):
        assert chave not in p


def test_aprovado_sem_prerequisito_vira_nao_classificado(tmp_path, monkeypatch):
    """A linha migrada de estrito/amplo antes da reclassificacao total: fica na
    janela, com o marcador, sem degrau inventado."""
    dados = _montar(tmp_path, monkeypatch, [_paper("p1")], [_triado("p1")])
    p = dados["papers"][0]
    assert (p["pr"], p["nt"], p["ao"]) == (NAO_CLASSIFICADO, None, 0)


def test_contrato_antigo_nao_viaja(tmp_path, monkeypatch):
    dados = _montar(tmp_path, monkeypatch, [_paper("p1")], [_triado("p1", prerequisito="treino")])
    p = dados["papers"][0]
    for chave in ("cr", "fc", "fr", "art"):
        assert chave not in p


# ══════════════ vocabulario e perfis ══════════════

def test_degraus_e_naturezas_saem_na_ordem_do_banco(tmp_path, monkeypatch):
    dados = _montar(tmp_path, monkeypatch, [_paper("p1")], [_triado("p1")])
    assert [d["k"] for d in dados["degraus"]] == [
        "nenhum", "implementar", "acesso_interno", "treino", "sem_acao",
    ]
    assert dados["degraus"][0] == {"k": "nenhum", "r": "Nenhum", "def": "d1"}
    assert [n["k"] for n in dados["naturezas"]] == ["proposta", "panorama"]


def test_perfis_saem_com_os_degraus_do_config(tmp_path, monkeypatch):
    dados = _montar(tmp_path, monkeypatch, [_paper("p1")], [_triado("p1")])
    assert dados["perfis"] == [
        {"p": "produto", "r": "Produto", "d": ["implementar", "nenhum"]},
        {"p": "pesquisa_treino", "r": "Treino/pesquisa", "d": ["treino"]},
    ]


# ══════════════ vertente e par area > sub-area ══════════════

def test_paper_carrega_a_vertente_com_a_dominante_em_primeiro(tmp_path, monkeypatch):
    dados = _montar(
        tmp_path, monkeypatch, [_paper("p1")], [_triado("p1")],
        vertentes=[
            {"paper_id": "p1", "vertente": "Escalar", "ordem": 2},
            {"paper_id": "p1", "vertente": "Baratear", "ordem": 1},
        ],
    )
    assert dados["papers"][0]["vt"] == ["Baratear", "Escalar"]


def test_a_subarea_do_par_primario_chega_ao_painel(tmp_path, monkeypatch):
    dados = _montar(tmp_path, monkeypatch, [_paper("p1")], [_triado("p1")], areas=[PAR_PRIMARIO])
    p = dados["papers"][0]
    assert (p["a"], p["sa"]) == ("Contexto & recuperação", "Memória de longo prazo")


def test_a_classificacao_acompanha_o_paper_ate_a_aba_historica(tmp_path, monkeypatch):
    dados = _montar(
        tmp_path, monkeypatch, [_paper("p1")],
        [_triado("p1", prerequisito="treino", natureza="proposta")],
        areas=[PAR_PRIMARIO],
        dias_hall=-1,      # corte no futuro: o paper sai da janela e entra no hall
    )
    entrada = dados["hall"][0]["ap"][0]
    assert (entrada["a"], entrada["sa"]) == ("Contexto & recuperação", "Memória de longo prazo")
    assert (entrada["pr"], entrada["nt"]) == ("treino", "proposta")


def test_paper_sem_par_nao_inventa_subarea(tmp_path, monkeypatch):
    dados = _montar(tmp_path, monkeypatch, [_paper("p1")], [_triado("p1")])
    assert (dados["papers"][0]["a"], dados["papers"][0]["sa"]) == (None, None)


GRADE = [
    {"area": "Contexto & recuperação", "definicao": "d1", "area_pai": None},
    {"area": "Interface & modalidade", "definicao": "d2", "area_pai": None},
    {"area": "Memória de longo prazo", "definicao": "", "area_pai": "Contexto & recuperação"},
    {"area": "Fala & áudio", "definicao": "", "area_pai": "Interface & modalidade"},
]


def test_o_menu_de_area_lista_so_as_raizes(tmp_path, monkeypatch):
    """`DADOS.areas` alimenta o filtro ÁREA, que compara com `p.a`, sempre raiz."""
    dados = _montar(tmp_path, monkeypatch, [_paper("p1")], [_triado("p1")],
                    areas=[PAR_PRIMARIO], grade=GRADE)
    assert dados["areas"] == [
        {"a": "Contexto & recuperação", "def": "d1"},
        {"a": "Interface & modalidade", "def": "d2"},
    ]
