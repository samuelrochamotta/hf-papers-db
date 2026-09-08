"""Transporte da camada LLM: parametros, truncamento, retry e contabilidade.

Os tres bugs que estes testes travam foram encontrados em execucao real contra o
OpenRouter:

1. mandar `temperature` para um modelo que nao a anuncia zera a lista de
   provedores sob `require_parameters` e a chamada volta 404;
2. `finish_reason == 'length'` corta o JSON no meio, e retentar com o mesmo teto
   so repete o corte;
3. o modelo devolve um campo que satisfaz o schema e nao diz nada - `"..."` numa
   justificativa (issue #7). Quem barra e o `validar`, e o valor de barrar esta
   no que vem depois: a retentativa carrega a mensagem do erro de volta.
"""

import json
from types import SimpleNamespace

import pytest

from hfpapers.llm import estagio_a as ea
from hfpapers.llm import schemas
from hfpapers.llm.cliente import ClienteLLM, ErroLLM, ErroValidacao, Preco, Uso

RESPOSTA = {"veredito": "amplo"}
RF = schemas.response_format("t", {"type": "object", "properties": {}})

JUSTIFICATIVA = (
    "Propoe um harness de agentes reutilizavel fora do benchmark dos autores, "
    "entao segue para o Estagio B em vez de cair numa regra de descarte."
)


def _resposta_a(justificativa):
    """Resposta minima do Estagio A - so o campo que `ea.validar` olha importa."""
    return {"veredito_preliminar": "candidato", "justificativa": justificativa}


class OpenAIDuble:
    """Imita `client.chat.completions.create`, guardando os kwargs recebidos."""

    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.chamadas = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.chamadas.append(kw)
        conteudo, finish = self.respostas.pop(0)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=conteudo), finish_reason=finish
                )
            ],
            usage=SimpleNamespace(prompt_tokens=100, completion_tokens=50),
        )


def _cliente(cfg, respostas, parametros):
    return ClienteLLM(
        cfg,
        cliente=OpenAIDuble(respostas),
        precos={"modelo/teste-b": Preco(2e-6, 1e-5)},
        parametros=parametros,
    )


def _chamar(c, **kw):
    return c.chamar(
        etapa="estagio_b",
        modelo="modelo/teste-b",
        prompt="p",
        response_format=RF,
        temperatura=0.2,
        max_tokens=3000,
        **kw,
    )


def test_temperature_e_omitida_quando_o_modelo_nao_a_anuncia(cfg):
    c = _cliente(cfg, [(json.dumps(RESPOSTA), "stop")], {"modelo/teste-b": {"response_format"}})
    _chamar(c)
    assert "temperature" not in c.openai.chamadas[0]


def test_temperature_vai_quando_suportada(cfg):
    c = _cliente(
        cfg, [(json.dumps(RESPOSTA), "stop")], {"modelo/teste-b": {"response_format", "temperature"}}
    )
    _chamar(c)
    assert c.openai.chamadas[0]["temperature"] == 0.2


def test_sem_catalogo_manda_temperature(cfg):
    c = _cliente(cfg, [(json.dumps(RESPOSTA), "stop")], {})
    _chamar(c)
    assert c.openai.chamadas[0]["temperature"] == 0.2


def test_require_parameters_vai_no_corpo(cfg):
    c = _cliente(cfg, [(json.dumps(RESPOSTA), "stop")], {})
    _chamar(c)
    assert c.openai.chamadas[0]["extra_body"]["provider"]["require_parameters"] is True


def test_truncamento_retenta_com_teto_dobrado(cfg):
    c = _cliente(
        cfg,
        [('{"veredito": "amp', "length"), (json.dumps(RESPOSTA), "stop")],
        {"modelo/teste-b": {"response_format"}},
    )
    r = _chamar(c)
    assert r.dados == RESPOSTA
    assert [k["max_tokens"] for k in c.openai.chamadas] == [3000, 6000]
    assert r.tentativas == 2


def test_truncamento_persistente_vira_erro(cfg):
    c = _cliente(cfg, [('{"a"', "length")] * 3, {})
    with pytest.raises(ErroLLM):
        _chamar(c)
    assert [k["max_tokens"] for k in c.openai.chamadas] == [3000, 6000, 12000]


def test_validacao_reprovada_reenvia_com_a_mensagem(cfg):
    def validar(d):
        if d.get("veredito") != "estrito":
            raise ErroValidacao("veredito tem de ser estrito")

    c = _cliente(
        cfg,
        [(json.dumps(RESPOSTA), "stop"), (json.dumps({"veredito": "estrito"}), "stop")],
        {},
    )
    r = _chamar(c, validar=validar)
    assert r.dados["veredito"] == "estrito"
    assert "veredito tem de ser estrito" in c.openai.chamadas[1]["messages"][-1]["content"]


def test_justificativa_degenerada_retenta_e_o_modelo_se_corrige(cfg):
    """Issue #7: `"..."` passa pelo schema, entao quem barra e `validar`.

    O ciclo inteiro: a resposta degenerada vira `ErroValidacao`, o cliente
    reenvia com a mensagem anexada e a resposta seguinte, ja legitima, e aceita.
    """
    c = _cliente(
        cfg,
        [
            (json.dumps(_resposta_a("...")), "stop"),
            (json.dumps(_resposta_a(JUSTIFICATIVA)), "stop"),
        ],
        {},
    )
    r = _chamar(c, validar=ea.validar)
    assert r.dados["justificativa"] == JUSTIFICATIVA
    assert r.tentativas == 2
    assert "justificativa" in c.openai.chamadas[1]["messages"][-1]["content"]


def test_justificativa_degenerada_insistente_vira_erro_llm(cfg):
    """Esgotadas as tentativas sobe `ErroLLM` - e o paper cai em pendencia por
    `estagios/classificacao.py`, em vez de gravar "..." como se fosse motivo."""
    c = _cliente(cfg, [(json.dumps(_resposta_a("...")), "stop")] * 3, {})
    with pytest.raises(ErroLLM):
        _chamar(c, validar=ea.validar)
    assert len(c.openai.chamadas) == 3


def test_json_invalido_retenta(cfg):
    c = _cliente(cfg, [("nao e json", "stop"), (json.dumps(RESPOSTA), "stop")], {})
    assert _chamar(c).dados == RESPOSTA


def test_custo_e_registrado_em_log_llm(cfg, conn):
    c = _cliente(cfg, [(json.dumps(RESPOSTA), "stop")], {})
    c.conn = conn
    c.run_id = "run-teste"
    _chamar(c)
    r = conn.execute("SELECT * FROM log_llm").fetchone()
    assert r["etapa"] == "estagio_b" and r["erro"] is None
    assert r["tokens_entrada"] == 100 and r["tokens_saida"] == 50
    assert r["custo_usd"] == pytest.approx(100 * 2e-6 + 50 * 1e-5)
    assert c.uso.chamadas == 1


def test_somente_precos_nao_fala_com_a_rede(cfg):
    c = ClienteLLM.somente_precos(cfg, precos={"m": Preco(1e-6, 1e-6)})
    assert c.openai is None
    assert c.estimar("m", 1_000_000, 0) == pytest.approx(1.0)
    assert c.uso == Uso()


# ── esforco de raciocinio e corpo de erro sem `choices` ─────────────────────
#
# Os dois nasceram da mesma rodada real, em 2026-09-08. O GLM 5.3 flash raciocina
# de forma obrigatoria (`reasoning.enabled: false` volta HTTP 400) e, com o prompt
# da grade facetada, gastava 2.343 tokens de rascunho para produzir 540 caracteres
# de JSON: 174 s por chamada, 33% de truncamento no Estagio B. Medido em 140 papers
# e 420 chamadas, `reasoning.effort` derruba a saida para 220 tokens sem mexer na
# classificacao - a concordancia entre `low` e `medium` (87%) e maior que a de
# `low` consigo mesmo (82%), ou seja, a diferenca entre os dois some no ruido.


class OpenAISemChoices:
    """O OpenRouter devolvendo corpo de erro com HTTP 200 e `choices` nulo.

    Nao e hipotese: capturado em 2026-09-08 com
    `{"error": {"message": "Provider returned error", "code": 429}}`. O SDK nao
    levanta nada, entao `r.choices[0]` estourava `TypeError` e queimava a
    tentativa sem dizer o motivo.
    """

    def __init__(self, mensagem="Provider returned error"):
        self.mensagem = mensagem
        self.chamadas = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.chamadas.append(kw)
        return SimpleNamespace(
            choices=None, usage=None, error={"message": self.mensagem, "code": 429}
        )


def test_esforco_de_raciocinio_vai_no_corpo_quando_configurado(cfg):
    cfg.llm.estagio_b.esforco_raciocinio = "medium"
    c = _cliente(cfg, [(json.dumps(RESPOSTA), "stop")], {})
    _chamar(c, esforco_raciocinio=cfg.llm.estagio_b.esforco_raciocinio)
    assert c.openai.chamadas[0]["extra_body"]["reasoning"] == {"effort": "medium"}


def test_esforco_de_raciocinio_ausente_nao_manda_o_campo(cfg):
    """Modelo que nao anuncia `reasoning` some da lista sob `require_parameters`.

    E a armadilha do `temperature` de novo (issue #1), entao o campo so vai
    quando alguem o pediu.
    """
    c = _cliente(cfg, [(json.dumps(RESPOSTA), "stop")], {})
    _chamar(c)
    assert "reasoning" not in c.openai.chamadas[0]["extra_body"]


def test_corpo_de_erro_sem_choices_vira_erro_nomeado(cfg):
    c = ClienteLLM(
        cfg,
        cliente=OpenAISemChoices(),
        precos={"modelo/teste-b": Preco(2e-6, 1e-5)},
        parametros={},
    )
    with pytest.raises(ErroLLM) as e:
        _chamar(c)
    # A mensagem do provedor tem de sobreviver ate aqui: sem ela o operador ve
    # `TypeError` e vai procurar bug no nosso codigo.
    assert "Provider returned error" in str(e.value)
    assert len(c.openai.chamadas) == 3


def test_corpo_de_erro_sem_choices_e_registrado_em_log_llm(cfg, conn):
    c = ClienteLLM(
        cfg,
        cliente=OpenAISemChoices(),
        precos={"modelo/teste-b": Preco(2e-6, 1e-5)},
        parametros={},
        conn=conn,
    )
    with pytest.raises(ErroLLM):
        _chamar(c)
    c.drenar_registros(conn)
    erros = [
        r["erro"]
        for r in conn.execute("SELECT erro FROM log_llm WHERE erro IS NOT NULL")
    ]
    assert len(erros) == 3
    assert all("sem choices" in e for e in erros)
