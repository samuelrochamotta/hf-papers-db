"""Validacoes pos-LLM (secao 4.4), schemas e a regra do upvote (secao 6.6)."""

import json

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
        "justificativa_veredito": "entrega artefato adotavel",
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
