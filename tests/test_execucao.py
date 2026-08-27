"""Pipeline ponta a ponta com HF e LLM dublados: idempotencia e dry-run."""

import datetime as dt

import httpx
import pytest
import respx

from hfpapers import db, execucao, taxonomia
from hfpapers.estagios import classificacao
from hfpapers.fontes.hf_client import ClienteHF
from hfpapers.llm.cliente import ClienteLLM, Preco, Resposta, Uso

HOJE = dt.date(2026, 8, 26)

RESPOSTA_A = {
    "veredito_preliminar": "candidato",
    "regra_fora": None,
    "justificativa": "propoe um harness reutilizavel",
    "area_primaria": "Agentes & automação",
    "areas_secundarias": [],
    "topicos": ["Agentes de codificação"],
    "candidato_novo_rotulo": None,
}
RESPOSTA_A_FORA = {**RESPOSTA_A, "veredito_preliminar": "fora", "regra_fora": "treino_ou_postreino"}
RESPOSTA_B = {
    "tem_artefato_nomeado": True,
    "padrao_extraido": {"nome": "Contrato de preservar-e-estender", "mecanismo": "Uma versao nova so entra se mantiver o que a anterior resolvia."},
    "teste_portabilidade": {
        "depende_do_nome_proprio": False,
        "colapsa_em_generalidade": False,
        "aprovado": True,
    },
    "veredito": "estrito",
    "justificativa_veredito": "entrega artefato adotavel",
    "decisao_fronteira": False,
    "ficha": {
        "achado": "a", "implicacao_pratica": "b", "exemplo_concreto": "c", "ressalva": "d",
    },
}


class LLMDuble(ClienteLLM):
    """Nao fala com a rede: devolve respostas fixas e conta as chamadas."""

    def __init__(self, conn=None, cfg=None, um_a_cada=3):
        self.cfg = cfg
        self.conn = conn
        self.run_id = "teste"
        self.uso = Uso()
        self._precos = {"modelo/teste-a": Preco(1e-6, 2e-6), "modelo/teste-b": Preco(2e-6, 1e-5)}
        self.openai = None
        self.chamadas = []
        self.um_a_cada = um_a_cada

    def chamar(self, *, etapa, modelo, prompt, validar=None, paper_id=None, **kw):
        self.chamadas.append((etapa, paper_id))
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


@pytest.fixture()
def base(cfg, daily_bruto):
    conn = db.abrir(cfg)
    with db.transacao(conn):
        db.upsert_area(conn, {"area": "Agentes & automação", "definicao": "d"})
        db.upsert_topico(conn, {"topico": "Agentes de codificação", "definicao": "d"})
    yield conn
    conn.close()


def _hf():
    from hfpapers.config import Config

    c = Config()
    c.hf.req_por_segundo = 1000
    c.hf.backoff_inicial_s = 0
    return ClienteHF(c)


@respx.mock
def test_run_completo_e_depois_idempotente(cfg, base, daily_bruto, paper_bruto):
    respx.get("https://huggingface.co/api/daily_papers").mock(
        return_value=httpx.Response(200, json=daily_bruto[:6])
    )
    respx.get(url__regex=r"https://huggingface\.co/api/papers/.+").mock(
        return_value=httpx.Response(200, json=paper_bruto)
    )
    llm = LLMDuble(base, cfg)

    r1 = execucao.rodar(
        cfg=cfg, conn=base, data=dt.date(2026, 8, 25), hoje=HOJE,
        cliente_hf=_hf(), cliente_llm=llm,
    )
    assert r1.coletados == 6 and r1.novos == 6
    assert r1.fora + r1.amplo + r1.estrito == 6
    assert r1.status == "ok"
    assert db.contar(base, "fato_triagem") == 6
    triagens_1 = db.contar(base, "fato_triagem")
    chamadas_1 = len(llm.chamadas)
    assert r1.arquivos["dim_paper"] == 6

    # segunda rodada no mesmo dia: nenhuma linha nova de triagem, nenhuma chamada
    r2 = execucao.rodar(
        cfg=cfg, conn=base, data=dt.date(2026, 8, 25), hoje=HOJE,
        cliente_hf=_hf(), cliente_llm=llm,
    )
    assert db.contar(base, "fato_triagem") == triagens_1
    assert len(llm.chamadas) == chamadas_1
    assert r2.fora == 0 and r2.aprovados == 0
    # e o snapshot de metricas do dia continua sendo um por paper
    assert db.contar(base, "fato_metrica", "data_snapshot = ?", (HOJE.isoformat(),)) == 6


@respx.mock
def test_force_reclassifica_e_incrementa_revisao(cfg, base, daily_bruto, paper_bruto):
    respx.get("https://huggingface.co/api/daily_papers").mock(
        return_value=httpx.Response(200, json=daily_bruto[:3])
    )
    respx.get(url__regex=r"https://huggingface\.co/api/papers/.+").mock(
        return_value=httpx.Response(200, json=paper_bruto)
    )
    llm = LLMDuble(base, cfg)
    execucao.rodar(cfg=cfg, conn=base, data=dt.date(2026, 8, 25), hoje=HOJE,
                   cliente_hf=_hf(), cliente_llm=llm)
    revisao_1 = base.execute("SELECT MAX(revisao) AS r FROM fato_triagem").fetchone()["r"]

    papers = classificacao.selecionar(base, data="2026-08-25", force=True)
    classificacao.rodar(base, llm, papers, run_id="run-2", cfg=cfg)
    revisao_2 = base.execute("SELECT MAX(revisao) AS r FROM fato_triagem").fetchone()["r"]
    assert revisao_2 == revisao_1 + 1


@respx.mock
def test_falha_do_estagio_b_nao_aborta_a_rodada(cfg, base, daily_bruto, paper_bruto):
    from hfpapers.llm.cliente import ErroLLM

    class LLMQuebrado(LLMDuble):
        def chamar(self, *, etapa, **kw):
            if etapa == "estagio_b":
                raise ErroLLM("provedor fora do ar")
            return super().chamar(etapa=etapa, **kw)

    respx.get("https://huggingface.co/api/daily_papers").mock(
        return_value=httpx.Response(200, json=daily_bruto[:6])
    )
    respx.get(url__regex=r"https://huggingface\.co/api/papers/.+").mock(
        return_value=httpx.Response(200, json=paper_bruto)
    )
    llm = LLMQuebrado(base, cfg)
    r = execucao.rodar(cfg=cfg, conn=base, data=dt.date(2026, 8, 25), hoje=HOJE,
                       cliente_hf=_hf(), cliente_llm=llm)

    assert any(a.startswith("estagio_b_falhou") for a in r.avisos)
    assert db.contar(base, "fato_triagem") == 6      # os demais foram gravados
    assert db.contar(base, "dim_ficha") == 0


@respx.mock
def test_dry_run_nao_grava_nem_gasta_token(cfg, base, daily_bruto):
    respx.get("https://huggingface.co/api/daily_papers").mock(
        return_value=httpx.Response(200, json=daily_bruto)
    )
    precos = {"modelo/teste-a": Preco(1e-6, 2e-6), "modelo/teste-b": Preco(2e-6, 1e-5)}
    import hfpapers.llm.cliente as mod

    original = mod.tabela_precos
    mod.tabela_precos = lambda cfg=None: precos
    try:
        r = execucao.dry_run(cfg=cfg, conn=base, data=dt.date(2026, 8, 25), hoje=HOJE,
                             cliente_hf=_hf())
    finally:
        mod.tabela_precos = original

    assert r.coletados == 35 and r.a_classificar == 35
    assert r.estimativa.total_usd > 0
    assert [i["etapa"] for i in r.estimativa.itens] == ["estagio_a", "estagio_b"]
    assert db.contar(base, "dim_paper") == 0        # nada gravado
    assert db.contar(base, "log_llm") == 0


@respx.mock
def test_candidato_de_taxonomia_e_registrado(cfg, base, daily_bruto, paper_bruto):
    class LLMComCandidato(LLMDuble):
        def chamar(self, *, etapa, **kw):
            r = super().chamar(etapa=etapa, **kw)
            if etapa == "estagio_a":
                r.dados = {
                    **r.dados,
                    "candidato_novo_rotulo": {
                        "rotulo": "Séries temporais",
                        "tipo": "topico",
                        "definicao": "Previsão sobre sequências indexadas no tempo.",
                    },
                }
            return r

    respx.get("https://huggingface.co/api/daily_papers").mock(
        return_value=httpx.Response(200, json=daily_bruto[:2])
    )
    respx.get(url__regex=r"https://huggingface\.co/api/papers/.+").mock(
        return_value=httpx.Response(200, json=paper_bruto)
    )
    execucao.rodar(cfg=cfg, conn=base, data=dt.date(2026, 8, 25), hoje=HOJE,
                   cliente_hf=_hf(), cliente_llm=LLMComCandidato(base, cfg))

    # dois papers distintos citaram o mesmo rotulo -> promovido
    assert "Séries temporais" in taxonomia.topicos(base)
