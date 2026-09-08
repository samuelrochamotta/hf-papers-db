"""Pipeline ponta a ponta com HF e LLM dublados: idempotencia e dry-run."""

import datetime as dt

import httpx
import pytest
import respx
from conftest import LLMComNaoEncaixe, LLMDuble, LLMQuebrado, povoar_vocabulario

from hfpapers import db, execucao, taxonomia
from hfpapers.estagios import classificacao
from hfpapers.fontes.hf_client import ClienteHF
from hfpapers.llm.cliente import Preco

HOJE = dt.date(2026, 8, 26)


@pytest.fixture()
def base(cfg, daily_bruto):
    conn = db.abrir(cfg)
    with db.transacao(conn):
        povoar_vocabulario(conn)
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
    respx.get("https://huggingface.co/api/daily_papers").mock(
        return_value=httpx.Response(200, json=daily_bruto[:6])
    )
    respx.get(url__regex=r"https://huggingface\.co/api/papers/.+").mock(
        return_value=httpx.Response(200, json=paper_bruto)
    )
    llm = LLMQuebrado(base, cfg)
    r = execucao.rodar(cfg=cfg, conn=base, data=dt.date(2026, 8, 25), hoje=HOJE,
                       cliente_hf=_hf(), cliente_llm=llm)

    # 2 dos 6 papers viram "candidato" no Estagio A (um_a_cada=3) e caem no
    # Estagio B, que a duble sempre derruba - nas duas passadas. Nenhum dos
    # dois ganha linha fabricada: ficam pendentes. Os outros 4 sao "fora" no
    # Estagio A e nem chegam ao Estagio B, entao sao gravados normalmente.
    avisos_b = [a for a in r.avisos if a.startswith("estagio_b_falhou")]
    assert len(avisos_b) == 2
    assert db.contar(base, "fato_triagem") == 4      # so os "fora" foram gravados
    assert db.contar(base, "dim_ficha") == 0
    assert r.nao_classificados == 2
    # o denominador chega ao guardrail: sem isso o aviso de volume ficaria
    # "volume_atipico:0", mudo sobre os 2 que nao foram classificados
    assert "volume_atipico:0 (+2 pendentes)" in r.avisos

    # os 2 pendentes nao tem linha em fato_triagem -> selecionar (sem force)
    # os repesca na rodada seguinte, como papers novos.
    pendentes = classificacao.selecionar(base, data="2026-08-25")
    assert len(pendentes) == 2


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
def test_nao_encaixe_da_rodada_entra_na_fila_de_revisao(cfg, base, daily_bruto, paper_bruto):
    """A rodada diaria alimenta a fila de revisao da grade e nao promove nada:
    quem promove e a revisao da grade, por quorum, fora do ato de classificar."""
    respx.get("https://huggingface.co/api/daily_papers").mock(
        return_value=httpx.Response(200, json=daily_bruto[:2])
    )
    respx.get(url__regex=r"https://huggingface\.co/api/papers/.+").mock(
        return_value=httpx.Response(200, json=paper_bruto)
    )
    vocabulario_antes = (taxonomia.arvore_de_areas(base), taxonomia.vertentes(base))
    execucao.rodar(cfg=cfg, conn=base, data=dt.date(2026, 8, 25), hoje=HOJE,
                   cliente_hf=_hf(), cliente_llm=LLMComNaoEncaixe(base, cfg))

    fila = taxonomia.nao_encaixes(base, eixo="subarea")
    assert len(fila) == db.contar(base, "fato_triagem") > 0
    assert fila[0]["justificativa"].startswith("Cache semântico")
    assert (taxonomia.arvore_de_areas(base), taxonomia.vertentes(base)) == vocabulario_antes


# ── reclassificar ───────────────────────────────────────────────────────────


def _papers(conn, n=3, dia="2026-08-25"):
    """Papers crus, sem passar pela coleta: o que `reclassificar` precisa e uma
    linha em `dim_paper`, nao uma rodada inteira dublada."""
    with db.transacao(conn):
        for i in range(n):
            db.upsert_paper(
                conn,
                {
                    "paper_id": f"2608.0000{i}",
                    "titulo": f"Paper {i}",
                    "abstract": "Um resumo qualquer, longo o bastante para o prompt. " * 3,
                    "data_hf_daily": dia,
                    "primeiro_visto_em": "2026-08-25T07:30:00",
                },
            )


def test_reclassificar_tudo_registra_a_rodada_em_log_execucao(cfg, base):
    _papers(base, 3)
    r = execucao.reclassificar(cfg=cfg, conn=base, tudo=True, cliente_llm=LLMDuble(base, cfg))

    assert r.selecionados == 3
    assert r.fora + r.amplo + r.estrito == 3
    assert r.status == "ok"

    linha = base.execute(
        "SELECT * FROM log_execucao WHERE run_id = ?", (r.run_id,)
    ).fetchone()
    assert linha is not None
    assert linha["finalizado_em"] is not None
    assert linha["status"] == "ok"
    assert (linha["qtd_fora"], linha["qtd_amplo"], linha["qtd_estrito"]) == (
        r.fora, r.amplo, r.estrito,
    )
    assert linha["taxa_fora"] == pytest.approx(r.fora / 3)
    # nada de coleta nem de refresh aconteceu: os campos ficam zerados, nao herdados
    assert (linha["qtd_coletados"], linha["qtd_novos"], linha["qtd_refresh"]) == (0, 0, 0)
    # e a triagem carrega o run_id da rodada, que e o que o painel trava
    assert db.contar(base, "fato_triagem", "run_id = ?", (r.run_id,)) == 3


def test_reclassificar_dirigido_tambem_registra_a_rodada(cfg, base):
    """`--data` e `--paper` deixam de ser invisiveis para o doutor."""
    _papers(base, 3)
    r = execucao.reclassificar(
        cfg=cfg, conn=base, ids=["2608.00000"], cliente_llm=LLMDuble(base, cfg)
    )
    assert r.selecionados == 1
    assert db.contar(base, "log_execucao", "run_id = ?", (r.run_id,)) == 1


def test_reclassificar_sem_alvo_nao_abre_execucao(cfg, base):
    """Base sem paper nenhum: nada a fazer e nenhuma linha de rodada vazia."""
    r = execucao.reclassificar(cfg=cfg, conn=base, tudo=True, cliente_llm=LLMDuble(base, cfg))
    assert r.selecionados == 0
    assert db.contar(base, "log_execucao") == 0


def test_reclassificar_registra_o_nao_encaixe_e_nao_cria_rotulo(cfg, base):
    """A varredura em massa nao precisa mais congelar vocabulario nenhum: a
    classificacao deixou de promover, entao a rodada dirigida e a total tem o
    mesmo efeito sobre a grade - nenhum."""
    _papers(base, 3)
    vocabulario_antes = (taxonomia.arvore_de_areas(base), taxonomia.vertentes(base))
    for alvo in ({"tudo": True}, {"data": "2026-08-25"}):
        execucao.reclassificar(
            cfg=cfg, conn=base, cliente_llm=LLMComNaoEncaixe(base, cfg), **alvo
        )
        assert [r["paper_id"] for r in taxonomia.nao_encaixes(base, eixo="subarea")] == [
            "2608.00000", "2608.00001", "2608.00002"
        ]
        assert (taxonomia.arvore_de_areas(base), taxonomia.vertentes(base)) == vocabulario_antes


def test_reclassificar_lista_os_papers_que_o_estagio_b_derrubou(cfg, base):
    """A lista impressa no fim da rodada sai daqui: e o que o operador cola de
    volta em `reclassificar --paper`."""
    _papers(base, 3)
    r = execucao.reclassificar(
        cfg=cfg, conn=base, tudo=True, cliente_llm=LLMQuebrado(base, cfg)
    )

    assert r.falhas_estagio_b == ["2608.00002"]     # 1 dos 3 chega ao Estagio B
    assert r.nao_classificados == 1
    assert db.contar(base, "fato_triagem") == 2     # os dois `fora` do Estagio A


def test_conferir_le_o_criterio_de_conclusao_da_rodada(cfg, base):
    _papers(base, 3)
    r = execucao.reclassificar(cfg=cfg, conn=base, tudo=True, cliente_llm=LLMDuble(base, cfg))
    assert execucao.conferir(base, r.run_id) == {"outro_run_id": 0, "sem_triagem": 0}

    # um paper novo que ninguem classificou, e uma triagem de outra rodada
    _papers(base, 4)
    base.execute(
        "UPDATE fato_triagem SET run_id = 'run-velha' WHERE paper_id = '2608.00000'"
    )
    base.commit()
    assert execucao.conferir(base, r.run_id) == {"outro_run_id": 1, "sem_triagem": 1}
