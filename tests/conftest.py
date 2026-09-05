import json
from pathlib import Path

import pytest

from hfpapers import db
from hfpapers.config import Config
from hfpapers.llm.cliente import ClienteLLM, ErroLLM, Preco, Resposta, Uso

FIXTURES = Path(__file__).parent / "fixtures"
SEED = Path(__file__).parents[1] / "seed"

# ── dublês de LLM compartilhados entre test_execucao.py e os arquivos da
# issue #1 que exercitam a falha do Estagio B a partir de `classificacao.rodar`
# diretamente. Moram aqui, e nao num `from test_execucao import ...`, porque
# `conftest` ja esta em `sys.modules` quando os modulos de teste sao
# importados pelo pytest - um `from conftest import ...` reaproveita essa
# instancia unica, em vez de arriscar duas copias divergentes do mesmo dublê.

RESPOSTA_A = {
    "veredito_preliminar": "candidato",
    "regra_fora": None,
    # Longa de proposito: `validar` exige piso de 80 caracteres uteis nos dois
    # estagios (issue #7), e os dublês passam por `validar` como o cliente real.
    "justificativa": "Propoe um harness de agentes reutilizavel fora do benchmark dos autores, entao segue para o Estagio B em vez de cair numa regra de descarte.",
    "area_primaria": "Agentes & automação",
    "areas_secundarias": [],
    "topicos": ["Agentes de codificação"],
    "candidato_novo_rotulo": None,
}
RESPOSTA_A_FORA = {
    **RESPOSTA_A,
    "veredito_preliminar": "fora",
    "regra_fora": "treino_ou_postreino",
    # Propria, e nao herdada: a de `RESPOSTA_A` diz que o paper segue para o
    # Estagio B, o oposto deste veredito. Ninguem afirma o conteudo, mas e o
    # texto que aparece em `fato_triagem` de quem for depurar.
    "justificativa": "Descreve uma receita de pos-treino do proprio modelo dos autores, entao cai na regra de descarte antes de chegar ao Estagio B.",
}
RESPOSTA_B = {
    "tem_artefato_nomeado": True,
    "padrao_extraido": {"nome": "Contrato de preservar-e-estender", "mecanismo": "Uma versao nova so entra se mantiver o que a anterior resolvia."},
    "teste_portabilidade": {
        "depende_do_nome_proprio": False,
        "colapsa_em_generalidade": False,
        "aprovado": True,
    },
    "criterios_veredito": ["padrao_arquitetural"],
    "veredito": "estrito",
    "regra_fora": None,
    "justificativa_veredito": "ESTRITO porque e padrao arquitetural: o contrato de preservar-e-estender e reproduzivel pela descricao, sem depender do codigo dos autores.",
    "decisao_fronteira": False,
    "fronteira_contraparte": None,
    "ficha": {
        "achado": "a", "implicacao_pratica": "b", "exemplo_concreto": "c", "ressalva": "d",
    },
}


class LLMDuble(ClienteLLM):
    """Nao fala com a rede: devolve respostas fixas e conta as chamadas.

    `tentativas_b` conta as chamadas de `estagio_b` a parte (alem de
    `chamadas`) para os dublês de falha do Estagio B (issue #1) poderem
    afirmar que as duas passadas realmente aconteceram, nao so uma.
    """

    def __init__(self, conn=None, cfg=None, um_a_cada=3):
        self.cfg = cfg
        self.conn = conn
        self.run_id = "teste"
        self.uso = Uso()
        self._precos = {"modelo/teste-a": Preco(1e-6, 2e-6), "modelo/teste-b": Preco(2e-6, 1e-5)}
        self.openai = None
        self.chamadas = []
        self.um_a_cada = um_a_cada
        self.tentativas_b = 0

    def chamar(self, *, etapa, modelo, prompt, validar=None, paper_id=None, **kw):
        self.chamadas.append((etapa, paper_id))
        if etapa == "estagio_b":
            self.tentativas_b += 1
        if etapa == "estagio_a":
            n = len([c for c in self.chamadas if c[0] == "estagio_a"])
            dados = RESPOSTA_A if n % self.um_a_cada == 0 else RESPOSTA_A_FORA
        else:
            dados = RESPOSTA_B
        if validar:
            validar(dados)
        uso = Uso(100, 50, 0.0001, 1)
        self.uso.somar(uso)
        return Resposta(dados, uso, modelo, 1, 10)


class LLMQuebrado(LLMDuble):
    """Derruba o Estagio B sempre - nas duas passadas, sem excecao."""

    def chamar(self, *, etapa, **kw):
        if etapa == "estagio_b":
            self.tentativas_b += 1
            raise ErroLLM("provedor fora do ar")
        return super().chamar(etapa=etapa, **kw)


@pytest.fixture()
def daily_bruto() -> list[dict]:
    return json.loads((FIXTURES / "daily_papers_2026-08-25.json").read_text(encoding="utf-8"))


@pytest.fixture()
def paper_bruto() -> dict:
    return json.loads((FIXTURES / "paper_2608.23552.json").read_text(encoding="utf-8"))


@pytest.fixture()
def conn(tmp_path):
    c = db.conectar(tmp_path / "t.db")
    yield c
    c.close()


@pytest.fixture()
def cfg(tmp_path) -> Config:
    """Config isolada: banco e marts no tmp, prompts reais do repo."""
    raiz = Path(__file__).parents[1]
    c = Config()
    c.raiz = raiz
    c.paths.banco = str(tmp_path / "hfpapers.db")
    c.paths.marts = str(tmp_path / "marts")
    c.paths.relatorios = str(tmp_path / "relatorios")
    c.paths.estado = str(tmp_path / "estado")
    c.paths.logs = str(tmp_path / "logs")
    c.llm.estagio_a.modelo = "modelo/teste-a"
    c.llm.estagio_b.modelo = "modelo/teste-b"
    c.llm.retry.backoff_inicial_s = 0     # sem espera artificial nos testes
    return c


@pytest.fixture()
def seed_dir() -> Path:
    return SEED
