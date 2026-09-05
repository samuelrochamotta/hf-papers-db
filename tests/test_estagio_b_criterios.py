"""Criterios de veredito, regra obrigatoria e contraparte da fronteira (tickets 02, 03, 06, 07).

Duas camadas: `eb.validar` isolado (as regras essenciais) e `eb.avaliar` sobre
um `ClienteLLM` real com o OpenAI dublado, para provar o que acontece quando o
modelo insiste - regra essencial vira `ErroLLM`, regra de fronteira e refeita
uma vez e depois gravada como veio.
"""

import json
from types import SimpleNamespace

import pytest
from conftest import RESPOSTA_B

from hfpapers.llm import estagio_a as ea
from hfpapers.llm import estagio_b as eb
from hfpapers.llm import schemas
from hfpapers.llm.cliente import ClienteLLM, ErroLLM, ErroValidacao, Preco

PAPER = ea.PaperEntrada(paper_id="2608.00001", titulo="T", abstract="A", keywords=[])

JUST_AMPLO = (
    "AMPLO porque e benchmark: mede a capacidade de agentes evoluirem o proprio harness, "
    "nao entrega um harness que o leitor adote."
)
JUST_FORA = (
    "FORA pela regra treino_ou_postreino: o payload principal e um objetivo de treino do "
    "modelo rascunho, e o leitor-alvo nao treina modelo."
)


def _b(**over):
    d = dict(RESPOSTA_B)
    d.update(over)
    return d


def _fora(**over):
    return _b(**{
        "veredito": "fora", "ficha": None, "criterios_veredito": [],
        "regra_fora": "treino_ou_postreino", "justificativa_veredito": JUST_FORA, **over,
    })


def _amplo(**over):
    return _b(**{
        "veredito": "amplo", "criterios_veredito": ["benchmark"],
        "justificativa_veredito": JUST_AMPLO, **over,
    })


# ── enums ───────────────────────────────────────────────────────────────────


def test_seis_regras_na_ordem_de_teste():
    assert schemas.REGRAS_FORA == [
        "treino_ou_postreino", "geracao_de_midia", "percepcao_robotica_embodied",
        "relatorio_tecnico_de_modelo", "fora_de_escopo", "portabilidade_reprovada",
    ]


def test_estagio_a_so_ve_as_regras_de_conteudo():
    s = schemas.schema_estagio_a(["a"], ["t"])
    assert s["properties"]["regra_fora"]["enum"] == [*schemas.REGRAS_FORA_CONTEUDO, None]
    assert "portabilidade_reprovada" not in s["properties"]["regra_fora"]["enum"]


def test_estagio_b_ve_as_seis_regras_e_a_contraparte_unificada():
    props = schemas.SCHEMA_ESTAGIO_B["properties"]
    assert props["regra_fora"]["enum"] == [*schemas.REGRAS_FORA, None]
    assert props["criterios_veredito"]["items"]["enum"] == schemas.CRITERIOS_VEREDITO
    assert len(schemas.CRITERIOS_VEREDITO) == 10
    assert props["fronteira_contraparte"]["enum"] == [*schemas.REGRAS_FORA, *schemas.CRITERIOS_VEREDITO, None]
    assert "minItems" not in props["criterios_veredito"]   # piso condicional fica em codigo


def test_criterios_vem_antes_do_veredito_e_a_contraparte_depois_da_flag():
    props = list(schemas.SCHEMA_ESTAGIO_B["properties"])
    assert props.index("teste_portabilidade") < props.index("criterios_veredito") < props.index("veredito")
    assert props.index("veredito") < props.index("regra_fora") < props.index("justificativa_veredito")
    assert props.index("decisao_fronteira") + 1 == props.index("fronteira_contraparte")


def test_lado_e_veredito_dos_criterios():
    assert schemas.lado("treino_ou_postreino") == "fora"
    assert schemas.lado("padrao_arquitetural") == "estrito"
    assert schemas.lado("benchmark") == "amplo"
    assert schemas.lado("x") is None
    assert schemas.veredito_dos_criterios([]) is None
    assert schemas.veredito_dos_criterios(["benchmark", "panorama"]) == "amplo"
    assert schemas.veredito_dos_criterios(["benchmark", "artefato_aberto"]) == "estrito"


# ── validacao 1: fora sem regra ─────────────────────────────────────────────


def test_fora_sem_regra_e_rejeitado_no_estagio_a():
    base = {
        "veredito_preliminar": "fora", "regra_fora": None,
        "justificativa": "Descreve uma receita de pos-treino do proprio modelo dos autores, entao cai na regra de descarte antes do Estagio B.",
    }
    with pytest.raises(ErroValidacao, match="regra_fora"):
        ea.validar(base)
    ea.validar({**base, "regra_fora": "treino_ou_postreino"})


def test_fora_sem_regra_e_rejeitado_no_estagio_b():
    with pytest.raises(ErroValidacao, match="regra_fora"):
        eb.validar(_fora(regra_fora=None))
    eb.validar(_fora())


def test_portabilidade_reprovada_exige_teste_reprovado():
    with pytest.raises(ErroValidacao, match="portabilidade_reprovada"):
        eb.validar(_fora(regra_fora="portabilidade_reprovada"))   # teste de RESPOSTA_B aprovou
    reprovado = {"depende_do_nome_proprio": True, "colapsa_em_generalidade": False, "aprovado": False}
    eb.validar(_fora(regra_fora="portabilidade_reprovada", teste_portabilidade=reprovado))


# ── validacao 2: aprovado sem criterio ──────────────────────────────────────


@pytest.mark.parametrize("criterios", [[], None])
def test_aprovado_sem_criterio_e_rejeitado(criterios):
    with pytest.raises(ErroValidacao, match="criterio"):
        eb.validar(_b(criterios_veredito=criterios))


# ── validacao 3: veredito incoerente com a lista ────────────────────────────


def test_criterio_de_estrito_com_veredito_amplo_e_rejeitado():
    with pytest.raises(ErroValidacao, match="incoerente"):
        eb.validar(_amplo(criterios_veredito=["benchmark", "artefato_aberto"]))


def test_so_criterios_de_amplo_com_veredito_estrito_e_rejeitado():
    with pytest.raises(ErroValidacao, match="incoerente"):
        eb.validar(_b(criterios_veredito=["benchmark"]))


def test_fora_com_criterios_e_rejeitado():
    with pytest.raises(ErroValidacao, match="vazio"):
        eb.validar(_fora(criterios_veredito=["benchmark"]))


def test_mistura_de_lados_e_estrito_e_nao_obriga_fronteira():
    """SafeAtlas-VL: artefato aberto + benchmark, estrito, sem fronteira."""
    eb.validar(_b(criterios_veredito=["artefato_aberto", "benchmark"]))


# ── validacao 4: fronteira ──────────────────────────────────────────────────


def test_fronteira_sem_contraparte_e_incoerente():
    assert eb.incoerencia_de_fronteira(_b(decisao_fronteira=True)) is not None


@pytest.mark.parametrize(
    "veredito, contraparte",
    [("estrito", "artefato_aberto"), ("amplo", "benchmark"), ("fora", "fora_de_escopo")],
)
def test_contraparte_do_mesmo_lado_e_incoerente(veredito, contraparte):
    dados = {"veredito": veredito, "decisao_fronteira": True, "fronteira_contraparte": contraparte}
    assert "mesmo lado" in eb.incoerencia_de_fronteira(dados)


@pytest.mark.parametrize(
    "veredito, contraparte",
    [
        ("estrito", "benchmark"),            # estrito↔amplo
        ("amplo", "padrao_arquitetural"),    # amplo↔estrito
        ("amplo", "treino_ou_postreino"),    # aprovado→fora
        ("fora", "exige_acesso_interno"),    # fora→aprovado
    ],
)
def test_contraparte_do_outro_lado_e_coerente(veredito, contraparte):
    dados = {"veredito": veredito, "decisao_fronteira": True, "fronteira_contraparte": contraparte}
    assert eb.incoerencia_de_fronteira(dados) is None


def test_sem_fronteira_nao_ha_incoerencia_mesmo_com_contraparte():
    assert eb.incoerencia_de_fronteira(_b(decisao_fronteira=False, fronteira_contraparte="benchmark")) is None


def test_validador_refaz_a_fronteira_uma_vez_e_depois_deixa_passar():
    v = eb.Validador()
    torto = _b(decisao_fronteira=True, fronteira_contraparte=None)
    with pytest.raises(ErroValidacao, match="fronteira_contraparte"):
        v(torto)
    v(torto)                                  # segunda vez: passa como veio
    assert v.avisos == ["fronteira_incoerente"]
    assert torto["decisao_fronteira"] is True  # a flag nunca vira false pela nossa mao


def test_validador_nao_relaxa_as_regras_essenciais():
    v = eb.Validador()
    for _ in range(3):
        with pytest.raises(ErroValidacao):
            v(_b(criterios_veredito=[]))


# ── com o ClienteLLM real e o OpenAI dublado ────────────────────────────────


class OpenAIDuble:
    def __init__(self, respostas):
        self.respostas = [json.dumps(r) for r in respostas]
        self.chamadas = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.chamadas.append(kw)
        conteudo = self.respostas.pop(0)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=conteudo), finish_reason="stop")],
            usage=SimpleNamespace(prompt_tokens=100, completion_tokens=50),
        )


def _avaliar(cfg, respostas):
    duble = OpenAIDuble(respostas)
    cliente = ClienteLLM(cfg, cliente=duble, precos={"modelo/teste-b": Preco(0, 0)}, parametros={})
    return eb.avaliar(cliente, PAPER, cfg=cfg), duble


def test_veredito_incoerente_e_refeito_e_o_modelo_se_corrige(cfg):
    r, duble = _avaliar(cfg, [_amplo(criterios_veredito=["benchmark", "artefato_aberto"]), _b(criterios_veredito=["artefato_aberto", "benchmark"])])
    assert r.veredito == "estrito"
    assert r.criterios_veredito == ["artefato_aberto", "benchmark"]
    assert len(duble.chamadas) == 2
    assert "incoerente" in duble.chamadas[1]["messages"][-1]["content"]


def test_veredito_incoerente_persistente_vira_erro_llm(cfg):
    torto = _amplo(criterios_veredito=["artefato_aberto"])
    with pytest.raises(ErroLLM):
        _avaliar(cfg, [torto] * cfg.llm.retry.tentativas)


def test_fronteira_incoerente_e_refeita_uma_vez_e_o_modelo_se_corrige(cfg):
    r, duble = _avaliar(cfg, [_b(decisao_fronteira=True), _b(decisao_fronteira=True, fronteira_contraparte="benchmark")])
    assert len(duble.chamadas) == 2
    assert r.decisao_fronteira is True and r.fronteira_contraparte == "benchmark"
    assert r.avisos == []


def test_fronteira_incoerente_persistente_grava_como_veio_com_aviso(cfg):
    torto = _b(decisao_fronteira=True, fronteira_contraparte="artefato_aberto")   # mesmo lado
    r, duble = _avaliar(cfg, [torto, torto])
    assert len(duble.chamadas) == 2                       # refez uma vez, nao tres
    assert r.decisao_fronteira is True                    # a flag fica
    assert r.fronteira_contraparte == "artefato_aberto"   # como veio
    assert r.avisos == ["fronteira_incoerente"]


def test_contraparte_sem_fronteira_e_descartada_com_aviso(cfg):
    r, duble = _avaliar(cfg, [_b(decisao_fronteira=False, fronteira_contraparte="benchmark")])
    assert len(duble.chamadas) == 1
    assert r.decisao_fronteira is False
    assert r.fronteira_contraparte is None
    assert r.avisos == ["fronteira_contraparte_descartada"]


def test_fora_do_estagio_b_carrega_a_regra_e_lista_vazia(cfg):
    r, _ = _avaliar(cfg, [_fora()])
    assert r.veredito == "fora" and r.regra_fora == "treino_ou_postreino"
    assert r.criterios_veredito == [] and r.ficha is None


def test_aprovado_nao_carrega_regra_e_deduplica_criterios(cfg):
    r, _ = _avaliar(cfg, [_b(regra_fora="fora_de_escopo", criterios_veredito=["padrao_arquitetural", "padrao_arquitetural"])])
    assert r.regra_fora is None
    assert r.criterios_veredito == ["padrao_arquitetural"]
