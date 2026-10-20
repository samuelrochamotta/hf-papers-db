"""Regras do Estagio B no regime do ADR 004: natureza, pre-requisito e ficha.

Tres camadas, as mesmas do modulo: `eb.validar` isolado (o que volta para o
modelo refazer), `eb.avaliar` sobre um `ClienteLLM` com o OpenAI dublado (as
sobrescritas e o que acontece quando o modelo insiste) e os avisos de
coerencia, que gravam como veio.
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

JUST_SEM_ACAO = (
    "Panorama sem acao direta: organiza as tecnicas de memoria de longo prazo, sem "
    "propor nem medir nada novo."
)
JUST_FORA = (
    "FORA por percepcao_robotica_embodied: o modelo classifica imagens e nao produz "
    "linguagem, entao nao e componente de pipeline com modelo de linguagem."
)


def _b(**over):
    d = dict(RESPOSTA_B)
    d.update(over)
    return d


def _fora(**over):
    return _b(**{
        "regra_fora": "percepcao_robotica_embodied", "natureza": None, "padrao_extraido": None,
        "prerequisito": None, "ficha": None, "justificativa": JUST_FORA, **over,
    })


def _panorama(**over):
    return _b(**{
        "natureza": "panorama", "padrao_extraido": None, "prerequisito": "sem_acao",
        "justificativa": JUST_SEM_ACAO, **over,
    })


# ── vocabulario ─────────────────────────────────────────────────────────────


def test_tres_regras_na_ordem_de_teste():
    """Treino, relatorio tecnico e portabilidade sairam (ADR 004); midia vem
    primeiro porque era o que a regra de treino escondia."""
    assert schemas.REGRAS_FORA == [
        "geracao_de_midia", "percepcao_robotica_embodied", "fora_de_escopo",
    ]


def test_vocabulario_do_banco_bate_com_os_enums(conn):
    """`dim_natureza` e `dim_prerequisito` sao semeadas no schema.sql; a ordem
    do banco e a ordem da escada, e as duas copias nao podem divergir."""
    naturezas = [r[0] for r in conn.execute("SELECT natureza FROM dim_natureza ORDER BY ordem")]
    degraus = [r[0] for r in conn.execute("SELECT prerequisito FROM dim_prerequisito ORDER BY ordem")]
    assert naturezas == schemas.NATUREZAS
    assert degraus == schemas.PREREQUISITOS


def test_ordem_normativa_dos_campos_do_schema_b():
    assert schemas.SCHEMA_ESTAGIO_B["required"] == [
        "regra_fora", "natureza", "padrao_extraido", "prerequisito",
        "pratica_contradita", "falta_o_como", "artefato_status", "justificativa", "ficha",
    ]
    assert list(schemas.SCHEMA_ESTAGIO_B["properties"]) == schemas.SCHEMA_ESTAGIO_B["required"]


# ── validar: o que volta para o modelo ──────────────────────────────────────


def test_resposta_padrao_e_valida():
    eb.validar(_b())


def test_fora_valido():
    eb.validar(_fora())


@pytest.mark.parametrize("campo,valor", [
    ("ficha", RESPOSTA_B["ficha"]), ("natureza", "proposta"), ("prerequisito", "nenhum"),
])
def test_fora_com_classificacao_e_invalido(campo, valor):
    with pytest.raises(ErroValidacao, match="descarte"):
        eb.validar(_fora(**{campo: valor}))


@pytest.mark.parametrize("campo", ["natureza", "prerequisito", "ficha"])
def test_aprovado_exige_natureza_prerequisito_e_ficha(campo):
    with pytest.raises(ErroValidacao):
        eb.validar(_b(**{campo: None}))


def test_ficha_com_campo_vazio_e_invalida():
    with pytest.raises(ErroValidacao, match="exemplo_concreto"):
        eb.validar(_b(ficha={**RESPOSTA_B["ficha"], "exemplo_concreto": "  "}))


@pytest.mark.parametrize("natureza", ["teoria", "panorama"])
def test_teoria_e_panorama_sao_sempre_sem_acao(natureza):
    eb.validar(_panorama(natureza=natureza))
    with pytest.raises(ErroValidacao, match="sem_acao"):
        eb.validar(_panorama(natureza=natureza, prerequisito="implementar"))


def test_proposta_nunca_e_sem_acao():
    with pytest.raises(ErroValidacao, match="proposta"):
        eb.validar(_b(prerequisito="sem_acao"))


def test_proposta_exige_padrao():
    with pytest.raises(ErroValidacao, match="padrao_extraido"):
        eb.validar(_b(padrao_extraido=None))


def test_padrao_so_existe_para_proposta():
    with pytest.raises(ErroValidacao, match="so existe"):
        eb.validar(_b(natureza="achado_empirico"))
    eb.validar(_b(natureza="achado_empirico", padrao_extraido=None))


def test_padrao_impessoal():
    padrao = {"nome": "N", "mecanismo": "Use um cache de prefixo quando voce tiver muito trafego."}
    with pytest.raises(ErroValidacao, match="impessoal"):
        eb.validar(_b(padrao_extraido=padrao))


def test_padrao_que_cita_o_nome_proprio_volta():
    """Substitui o teste de portabilidade autoavaliado: o nome que vem antes do
    ":" no titulo nao pode sustentar o padrao."""
    titulo = "OpenSearch-VL: Scaling Retrieval for Vision-Language Agents"
    padrao = {"nome": "Busca em duas fases", "mecanismo": "O OpenSearch-VL separa a busca grossa da fina."}
    with pytest.raises(ErroValidacao, match="OpenSearch-VL"):
        eb.validar(_b(padrao_extraido=padrao), titulo)
    eb.validar(_b(), titulo)  # o padrao do conftest nao cita o nome


@pytest.mark.parametrize("titulo,esperado", [
    ("SCAPO: Token Suppression for Safer Decoding", {"SCAPO"}),
    ("RetrievalRouter: Routing Queries Across Indexes", {"RetrievalRouter"}),
    ("MiMo-V2.6 Technical Report", set()),          # sem ":" nao ha nome a proteger
    ("LLM Agents: A Survey", set()),                 # sigla comum nao e nome
    ("Qwen3-Omni: one model, all modalities", {"Qwen3-Omni"}),
])
def test_nomes_proprios_do_titulo(titulo, esperado):
    assert eb.nomes_proprios(titulo) == esperado


def test_justificativa_curta_volta():
    with pytest.raises(ErroValidacao, match="piso"):
        eb.validar(_b(justificativa="curta"))


# ── avisos de coerencia: gravam como veio ───────────────────────────────────


def _resultado(**over):
    base = dict(
        paper_id="p", regra_fora=None, natureza="proposta", padrao_extraido=None,
        prerequisito="implementar", pratica_contradita=None, falta_o_como=None,
        artefato_status=None, justificativa="j", ficha=None,
    )
    base.update(over)
    return eb.ResultadoB(**base)


def test_contradicao_sem_degrau_avisa():
    r = _resultado(natureza="achado_empirico", prerequisito="sem_acao",
                   pratica_contradita="monitorar o raciocinio para detectar desvio")
    assert eb.avisos_de_coerencia(r, [], False) == [eb.AVISO_CONTRADICAO_SEM_DEGRAU]


def test_achado_sem_acao_avisa():
    r = _resultado(natureza="achado_empirico", prerequisito="sem_acao")
    assert eb.avisos_de_coerencia(r, [], False) == [eb.AVISO_ACHADO_SEM_ACAO]


def test_treinar_dominante_com_degrau_nenhum_sem_artefato_avisa():
    r = _resultado(prerequisito="nenhum")
    assert eb.avisos_de_coerencia(r, ["Treinar"], False) == [eb.AVISO_TREINAR_SEM_DEGRAU]
    assert eb.avisos_de_coerencia(r, ["Treinar"], True) == []
    assert eb.avisos_de_coerencia(r, ["Medir", "Treinar"], False) == []


def test_fora_nao_avisa():
    assert eb.avisos_de_coerencia(_resultado(regra_fora="fora_de_escopo"), ["Treinar"], False) == []


# ── avaliar com o cliente real e o OpenAI dublado ──────────────────────────


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


def _avaliar(cfg, respostas, paper=PAPER):
    duble = OpenAIDuble(respostas)
    cliente = ClienteLLM(cfg, cliente=duble, precos={"modelo/teste-b": Preco(0, 0)}, parametros={})
    return eb.avaliar(cliente, paper, cfg=cfg), duble


def test_artefato_sem_evidencia_e_sobrescrito_para_nulo(cfg):
    r, duble = _avaliar(cfg, [_b(artefato_status="liberado")])
    assert r.artefato_status is None
    assert len(duble.chamadas) == 1   # sobrescrita, nao retentativa


def test_artefato_com_evidencia_fica_como_veio(cfg):
    paper = ea.PaperEntrada(paper_id="p", titulo="T", evidencia_artefato=True,
                            links_artefato=["https://github.com/x/y"])
    r, duble = _avaliar(cfg, [_b(artefato_status="prometido")], paper)
    assert r.artefato_status == "prometido"
    assert "https://github.com/x/y" in duble.chamadas[0]["messages"][-1]["content"]


def test_textos_vazios_viram_nulo(cfg):
    r, _ = _avaliar(cfg, [_b(pratica_contradita="  ", falta_o_como="falta o criterio de parada")])
    assert r.pratica_contradita is None
    assert r.falta_o_como == "falta o criterio de parada"


def test_fora_zera_o_resto(cfg):
    r, _ = _avaliar(cfg, [_fora(pratica_contradita="x", artefato_status="liberado")])
    assert (r.veredito, r.regra_fora) == ("fora", "percepcao_robotica_embodied")
    assert r.pratica_contradita is None and r.artefato_status is None and r.ficha is None


def test_regra_essencial_insistente_vira_erro_llm(cfg):
    with pytest.raises(ErroLLM):
        _avaliar(cfg, [_b(prerequisito="sem_acao")] * cfg.llm.retry.tentativas)


def test_refeita_uma_vez_e_aceita(cfg):
    r, duble = _avaliar(cfg, [_b(prerequisito="sem_acao"), _b()])
    assert r.prerequisito == "implementar"
    assert "proposta" in duble.chamadas[1]["messages"][-1]["content"]
