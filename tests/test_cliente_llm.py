"""Transporte da camada LLM: parametros, truncamento, retry e contabilidade.

Os dois bugs que estes testes travam foram encontrados em execucao real contra o
OpenRouter:

1. mandar `temperature` para um modelo que nao a anuncia zera a lista de
   provedores sob `require_parameters` e a chamada volta 404;
2. `finish_reason == 'length'` corta o JSON no meio, e retentar com o mesmo teto
   so repete o corte.
"""

import json
from types import SimpleNamespace

import pytest

from hfpapers.llm import schemas
from hfpapers.llm.cliente import ClienteLLM, ErroLLM, ErroValidacao, Preco, Uso

RESPOSTA = {"veredito": "amplo"}
RF = schemas.response_format("t", {"type": "object", "properties": {}})


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
