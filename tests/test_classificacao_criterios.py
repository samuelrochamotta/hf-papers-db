"""Gravacao dos criterios, da regra e da contraparte pelo estagio de classificacao.

`ponte_paper_criterio` segue a ponte de area: reescrita a cada
classificacao, vazia para `fora`. Os avisos de fronteira do Estagio B chegam ao
resultado da rodada com o `paper_id` anexado.
"""

import pytest
from conftest import RESPOSTA_B, LLMDuble, povoar_vocabulario

from hfpapers import db
from hfpapers.estagios import classificacao
from hfpapers.llm.cliente import Resposta, Uso

PID = "2608.00001"


@pytest.fixture()
def base(conn):
    with db.transacao(conn):
        povoar_vocabulario(conn)
        db.upsert_paper(conn, {"paper_id": PID, "titulo": "P", "primeiro_visto_em": db.agora()})
    return conn


class LLMComResposta(LLMDuble):
    """Estagio A sempre `candidato`; Estagio B devolve `resposta_b` como veio,
    passando pelo `validar` como o cliente real."""

    def __init__(self, conn, cfg, resposta_b):
        super().__init__(conn, cfg, um_a_cada=1)
        self.resposta_b = resposta_b

    def chamar(self, *, etapa, modelo, prompt, validar=None, paper_id=None, **kw):
        if etapa != "estagio_b":
            return super().chamar(etapa=etapa, modelo=modelo, prompt=prompt, validar=validar, paper_id=paper_id, **kw)
        self.chamadas.append((etapa, paper_id))
        if validar:
            validar(self.resposta_b)
        return Resposta(self.resposta_b, Uso(1, 1, 0, 1), modelo, 1, 1)


def _criterios(conn):
    return [r["criterio"] for r in conn.execute("SELECT criterio FROM ponte_paper_criterio ORDER BY criterio")]


def _rodar(base, cfg, resposta_b, run_id):
    papers = classificacao.selecionar(base, force=True)
    return classificacao.rodar(base, LLMComResposta(base, cfg, resposta_b), papers, run_id=run_id, cfg=cfg)


def test_grava_criterios_regra_nula_e_contraparte(cfg, base):
    resposta = {
        **RESPOSTA_B,
        "criterios_veredito": ["artefato_aberto", "benchmark"],
        "decisao_fronteira": True,
        "fronteira_contraparte": "principio_sem_o_como",
    }
    res = _rodar(base, cfg, resposta, "run-1")

    assert res.estrito == 1 and res.avisos == []
    assert _criterios(base) == ["artefato_aberto", "benchmark"]
    row = base.execute("SELECT * FROM fato_triagem").fetchone()
    assert row["regra_fora"] is None
    assert row["decisao_fronteira"] == 1
    assert row["fronteira_contraparte"] == "principio_sem_o_como"


def test_reclassificacao_apaga_os_criterios_antigos(cfg, base):
    _rodar(base, cfg, {**RESPOSTA_B, "criterios_veredito": ["artefato_aberto", "benchmark"]}, "run-1")
    assert _criterios(base) == ["artefato_aberto", "benchmark"]

    _rodar(base, cfg, {**RESPOSTA_B, "criterios_veredito": ["padrao_arquitetural"]}, "run-2")
    assert _criterios(base) == ["padrao_arquitetural"]     # os dois antigos sumiram
    assert base.execute("SELECT revisao FROM fato_triagem").fetchone()["revisao"] == 2


def test_fora_no_estagio_b_grava_ponte_vazia_e_a_regra_do_b(cfg, base):
    _rodar(base, cfg, RESPOSTA_B, "run-1")
    assert _criterios(base) == ["padrao_arquitetural"]

    fora = {
        **RESPOSTA_B,
        "criterios_veredito": [], "veredito": "fora", "ficha": None,
        "regra_fora": "fora_de_escopo",
        "justificativa_veredito": "FORA pela regra fora_de_escopo: e econometria de precificacao de ativos, nao engenharia de sistemas com modelos de linguagem.",
    }
    res = _rodar(base, cfg, fora, "run-2")
    assert res.fora == 1
    assert _criterios(base) == []
    row = base.execute("SELECT veredito, regra_fora, fronteira_contraparte FROM fato_triagem").fetchone()
    assert (row["veredito"], row["regra_fora"], row["fronteira_contraparte"]) == ("fora", "fora_de_escopo", None)
    assert db.contar(base, "dim_ficha") == 0


def test_fora_no_estagio_a_tambem_limpa_criterios_e_ficha(cfg, base):
    _rodar(base, cfg, RESPOSTA_B, "run-1")
    assert _criterios(base) == ["padrao_arquitetural"] and db.contar(base, "dim_ficha") == 1

    papers = classificacao.selecionar(base, force=True)
    llm = LLMDuble(base, cfg, um_a_cada=1000)   # todo Estagio A vira RESPOSTA_A_FORA
    res = classificacao.rodar(base, llm, papers, run_id="run-2", cfg=cfg)

    assert res.fora == 1
    assert _criterios(base) == []
    assert db.contar(base, "dim_ficha") == 0
    row = base.execute("SELECT regra_fora, fronteira_contraparte FROM fato_triagem").fetchone()
    assert row["regra_fora"] == "treino_ou_postreino" and row["fronteira_contraparte"] is None


def test_avisos_de_fronteira_chegam_a_rodada_com_o_paper_id(cfg, base):
    resposta = {**RESPOSTA_B, "decisao_fronteira": False, "fronteira_contraparte": "benchmark"}
    res = _rodar(base, cfg, resposta, "run-1")
    assert res.avisos == [f"fronteira_contraparte_descartada:{PID}"]
    assert base.execute("SELECT fronteira_contraparte FROM fato_triagem").fetchone()[0] is None
