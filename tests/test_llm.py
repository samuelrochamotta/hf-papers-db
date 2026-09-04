"""Validacoes pos-LLM (secao 4.4), schemas e a regra do upvote (secao 6.6)."""

import json
import logging

import pytest

from hfpapers.llm import estagio_a as ea
from hfpapers.llm import estagio_b as eb
from hfpapers.llm import schemas
from hfpapers.llm.cliente import ErroValidacao

VOCAB = ea.Vocabulario(
    areas=[("Agentes & automação", "def a"), ("Avaliação & confiabilidade", "def b")],
    topicos=[("Agentes de codificação", "def t"), ("Ataque adversarial", "def u")],
)

PAPER = ea.PaperEntrada(
    paper_id="2608.00001",
    titulo="Um framework de agentes",
    abstract="Nosso sistema melhora a taxa de sucesso em 14%.",
    keywords=["agentic", "harness"],
    area_primaria="Agentes & automação",
    topicos=["Agentes de codificação"],
)


# Justificativas de tamanho legitimo. As validacoes exigem piso de 80 caracteres
# uteis (issue #7), entao toda fixture que passa por `validar` precisa de uma.
JUSTIFICATIVA_B = (
    "Entrega artefato adotavel por quem nao treina modelo: o padrao passou no teste de portabilidade e se sustenta fora do benchmark dos autores."
)
JUSTIFICATIVA_A = (
    "Propoe um harness de agentes reutilizavel fora do benchmark dos autores, entao segue para o Estagio B em vez de cair numa regra de descarte."
)


def _base_a(**over):
    d = {
        "veredito_preliminar": "candidato",
        "regra_fora": None,
        "justificativa": JUSTIFICATIVA_A,
        "area_primaria": "Agentes & automação",
        "areas_secundarias": [],
        "topicos": ["Agentes de codificação"],
        "candidato_novo_rotulo": None,
    }
    d.update(over)
    return d


def _base(**over):
    d = {
        "tem_artefato_nomeado": True,
        "padrao_extraido": {"nome": "Contrato de preservar-e-estender", "mecanismo": "Uma versao nova so e promovida se mantiver o que a anterior resolvia."},
        "teste_portabilidade": {
            "depende_do_nome_proprio": False,
            "colapsa_em_generalidade": False,
            "aprovado": True,
        },
        "veredito": "estrito",
        "justificativa_veredito": JUSTIFICATIVA_B,
        "decisao_fronteira": False,
        "ficha": {
            "achado": "a",
            "implicacao_pratica": "b",
            "exemplo_concreto": "c",
            "ressalva": "d",
        },
    }
    d.update(over)
    return d


# ── schema ──────────────────────────────────────────────────────────────────


def test_enum_de_area_e_topico_e_injetado():
    s = schemas.schema_estagio_a(VOCAB.rotulos_area, VOCAB.rotulos_topico)
    assert s["properties"]["area_primaria"]["enum"] == VOCAB.rotulos_area
    assert s["properties"]["topicos"]["items"]["enum"] == VOCAB.rotulos_topico
    assert s["properties"]["topicos"]["maxItems"] == 5


def test_schema_a_recusa_vocabulario_vazio():
    with pytest.raises(ValueError):
        schemas.schema_estagio_a([], [])


def test_os_dois_campos_de_justificativa_declaram_piso_e_teto():
    """Issue #7: teto sem piso deixava `"..."` passar pela saida estruturada."""
    a = schemas.schema_estagio_a(VOCAB.rotulos_area, VOCAB.rotulos_topico)
    for campo in (
        a["properties"]["justificativa"],
        schemas.SCHEMA_ESTAGIO_B["properties"]["justificativa_veredito"],
    ):
        assert campo["minLength"] == schemas.PISO_JUSTIFICATIVA
        assert campo["maxLength"] == schemas.TETO_JUSTIFICATIVA


def test_ordem_das_propriedades_do_estagio_b_e_normativa():
    props = list(schemas.SCHEMA_ESTAGIO_B["properties"])
    assert props.index("padrao_extraido") < props.index("veredito")
    assert props.index("teste_portabilidade") < props.index("veredito")
    assert props == schemas.SCHEMA_ESTAGIO_B["required"]


# ── validacoes da secao 4.4 ─────────────────────────────────────────────────


def test_fora_exige_ficha_nula():
    with pytest.raises(ErroValidacao):
        eb.validar(_base(veredito="fora", ficha={"achado": "a", "implicacao_pratica": "b", "exemplo_concreto": "c", "ressalva": "d"}))


def test_aprovado_exige_ficha_completa():
    with pytest.raises(ErroValidacao):
        eb.validar(_base(ficha=None))
    with pytest.raises(ErroValidacao):
        eb.validar(_base(ficha={"achado": " ", "implicacao_pratica": "b", "exemplo_concreto": "c", "ressalva": "d"}))


def test_sem_artefato_nomeado_zera_padrao_e_teste():
    with pytest.raises(ErroValidacao):
        eb.validar(_base(tem_artefato_nomeado=False))
    eb.validar(_base(tem_artefato_nomeado=False, padrao_extraido=None, teste_portabilidade=None))


def test_reprovado_na_portabilidade_tem_de_sair_fora():
    reprovado = {
        "depende_do_nome_proprio": True,
        "colapsa_em_generalidade": False,
        "aprovado": False,
    }
    with pytest.raises(ErroValidacao):
        eb.validar(_base(teste_portabilidade=reprovado))
    eb.validar(_base(teste_portabilidade=reprovado, veredito="fora", ficha=None))


def test_aprovado_incoerente_com_as_duas_falhas():
    with pytest.raises(ErroValidacao):
        eb.validar(
            _base(
                teste_portabilidade={
                    "depende_do_nome_proprio": True,
                    "colapsa_em_generalidade": False,
                    "aprovado": True,
                }
            )
        )


def test_padrao_com_segunda_pessoa_e_rejeitado():
    with pytest.raises(ErroValidacao):
        eb.validar(
            _base(
                padrao_extraido={
                    "nome": "X",
                    "mecanismo": "Voce deve manter as duas versoes e comparar.",
                }
            )
        )


def test_padrao_com_imperativo_e_rejeitado():
    with pytest.raises(ErroValidacao):
        eb.validar(
            _base(padrao_extraido={"nome": "X", "mecanismo": "Use um verificador automatico."})
        )


def test_padrao_impessoal_passa():
    eb.validar(_base())


# ── piso da justificativa (issue #7) ────────────────────────────────────────

# `minLength` no schema nao basta: a rede em codigo e que segura o caso real.
DEGENERADAS = [
    "...",                    # o que o paper 2608.06867 devolveu na migracao da issue #3
    "",
    "   ",
    "Sem motivo.",
    ". " * 60,                # 120 caracteres, zero conteudo: passa por um teto so
    None,                     # campo ausente na resposta
]


@pytest.mark.parametrize("texto", DEGENERADAS)
def test_justificativa_degenerada_e_rejeitada_no_estagio_b(texto):
    with pytest.raises(ErroValidacao):
        eb.validar(_base(justificativa_veredito=texto))


@pytest.mark.parametrize("texto", DEGENERADAS)
def test_justificativa_degenerada_e_rejeitada_no_estagio_a(texto):
    with pytest.raises(ErroValidacao):
        ea.validar(_base_a(justificativa=texto))


def test_reticencias_sao_rejeitadas_nos_dois_estagios():
    """O caso concreto da issue: `"..."` nao e vazio, entao atravessava a defesa
    do painel (`justificativa_exibivel`) e era exibido como se fosse conteudo."""
    with pytest.raises(ErroValidacao) as e_b:
        eb.validar(_base(justificativa_veredito="..."))
    assert "justificativa_veredito" in str(e_b.value)
    with pytest.raises(ErroValidacao) as e_a:
        ea.validar(_base_a(justificativa="..."))
    assert "justificativa" in str(e_a.value)


def test_justificativa_legitima_passa_nos_dois_estagios():
    eb.validar(_base())
    ea.validar(_base_a())


def test_justificativa_no_limite_do_piso_passa():
    """80 caracteres uteis e o piso, nao o degrau abaixo dele."""
    texto = "o" + "l" * (schemas.PISO_JUSTIFICATIVA - 1)
    eb.validar(_base(justificativa_veredito=f"  {texto}  "))
    with pytest.raises(ErroValidacao):
        eb.validar(_base(justificativa_veredito=texto[:-1]))


def test_justificativa_acima_do_teto_passa_e_so_avisa(caplog):
    """O teto nao e simetrico ao piso: estourar por cima e cosmetico.

    Derrubar aqui custaria a taxonomia do paper no Estagio A e marcaria a rodada
    como parcial - caro demais para uma coluna `TEXT` sem constraint que o
    painel renderiza sem reclamar. Fica o aviso, para um provedor mal comportado
    aparecer no log sem custar papers.
    """
    longa = "Entrega artefato adotavel. " * 20
    assert len(longa) > schemas.TETO_JUSTIFICATIVA
    with caplog.at_level(logging.WARNING, logger="hfpapers.llm"):
        eb.validar(_base(justificativa_veredito=longa))
    assert "acima do teto" in caplog.text


# ── regra do upvote (secao 6.6, criterio de aceite 7) ───────────────────────


def _payload_estagio_a(cfg):
    return ea.montar_prompt(PAPER, VOCAB, cfg)


def test_upvotes_nao_aparecem_em_nenhum_prompt(cfg):
    a = _payload_estagio_a(cfg)
    b = eb.montar_prompt(PAPER, cfg)
    for texto in (a, b):
        baixo = texto.lower()
        assert "upvote" not in baixo
        assert "voto" not in baixo


def test_paper_entrada_nao_carrega_upvotes():
    assert not hasattr(PAPER, "upvotes")
    assert "upvotes" not in json.dumps(PAPER.__dict__, default=str)


def test_prompt_injeta_o_vocabulario_e_o_paper(cfg):
    a = _payload_estagio_a(cfg)
    assert "Agentes & automação" in a and "Ataque adversarial" in a
    assert PAPER.titulo in a and PAPER.abstract in a
    assert "{AREAS}" not in a and "{TITULO}" not in a


def test_prompt_b_declara_a_ordem_do_raciocinio(cfg):
    b = eb.montar_prompt(PAPER, cfg)
    assert b.index("padrao_extraido") < b.index("`veredito`")
    assert "antes de o veredito ser decidido" in b
