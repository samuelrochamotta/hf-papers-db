"""Gravacao do regime do ADR 004 pelo estagio de classificacao.

Natureza, pre-requisito e os dois textos vao para `fato_triagem`; o `fora`
apaga a ficha e deixa a classificacao nula; a evidencia de artefato sai de
`vw_artefato` para a entrada do Estagio B; `--retomar` leva so quem ainda nao
tem triagem da rodada.
"""

import pytest
from conftest import RESPOSTA_B, LLMDuble, povoar_vocabulario

from hfpapers import db, execucao
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
        self.prompts_b = []

    def chamar(self, *, etapa, modelo, prompt, validar=None, paper_id=None, **kw):
        if etapa != "estagio_b":
            return super().chamar(etapa=etapa, modelo=modelo, prompt=prompt, validar=validar, paper_id=paper_id, **kw)
        self.chamadas.append((etapa, paper_id))
        self.prompts_b.append(prompt)
        if validar:
            validar(self.resposta_b)
        return Resposta(self.resposta_b, Uso(1, 1, 0, 1), modelo, 1, 1)


def _rodar(base, cfg, resposta_b, run_id):
    papers = classificacao.selecionar(base, force=True)
    llm = LLMComResposta(base, cfg, resposta_b)
    return classificacao.rodar(base, llm, papers, run_id=run_id, cfg=cfg), llm


def test_grava_natureza_prerequisito_e_textos(cfg, base):
    resposta = {
        **RESPOSTA_B,
        "prerequisito": "nenhum",
        "pratica_contradita": "reusar o mesmo prompt de sistema entre modelos",
        "falta_o_como": None,
    }
    res, _ = _rodar(base, cfg, resposta, "run-1")

    assert (res.aprovados, res.fora) == (1, 0)
    assert res.por_prerequisito == {"nenhum": 1}
    row = base.execute("SELECT * FROM fato_triagem").fetchone()
    assert row["veredito"] == "aprovado" and row["regra_fora"] is None
    assert (row["natureza"], row["prerequisito"]) == ("proposta", "nenhum")
    assert row["pratica_contradita"] == "reusar o mesmo prompt de sistema entre modelos"
    assert db.contar(base, "dim_ficha") == 1


def test_perfil_sai_da_view(cfg, base):
    _rodar(base, cfg, {**RESPOSTA_B, "prerequisito": "treino"}, "run-1")
    perfis = [r[0] for r in base.execute("SELECT perfil FROM vw_paper_perfil")]
    assert perfis == ["pesquisa_treino"]


def test_fora_no_estagio_b_apaga_ficha_e_classificacao(cfg, base):
    _rodar(base, cfg, RESPOSTA_B, "run-1")
    fora = {
        **RESPOSTA_B,
        "regra_fora": "fora_de_escopo", "natureza": None, "padrao_extraido": None,
        "prerequisito": None, "ficha": None,
        "justificativa": "FORA por fora_de_escopo: e econometria de precificacao de ativos, sem modelo de linguagem nem pipeline com ele.",
    }
    res, _ = _rodar(base, cfg, fora, "run-2")
    assert res.fora == 1
    row = base.execute("SELECT * FROM fato_triagem").fetchone()
    assert (row["veredito"], row["regra_fora"], row["natureza"], row["prerequisito"]) == (
        "fora", "fora_de_escopo", None, None,
    )
    assert row["revisao"] == 2
    assert db.contar(base, "dim_ficha") == 0


def test_fora_no_estagio_a_apaga_a_ficha(cfg, base):
    _rodar(base, cfg, RESPOSTA_B, "run-1")
    papers = classificacao.selecionar(base, force=True)
    llm = LLMDuble(base, cfg, um_a_cada=1000)   # todo Estagio A vira RESPOSTA_A_FORA
    res = classificacao.rodar(base, llm, papers, run_id="run-2", cfg=cfg)
    assert res.fora == 1
    assert db.contar(base, "dim_ficha") == 0
    row = base.execute("SELECT regra_fora, natureza FROM fato_triagem").fetchone()
    assert (row["regra_fora"], row["natureza"]) == ("geracao_de_midia", None)


def test_evidencia_de_artefato_chega_ao_estagio_b(cfg, base):
    with db.transacao(base):
        db.upsert_paper(base, {
            "paper_id": PID, "titulo": "P", "primeiro_visto_em": db.agora(),
            "github_repo": "https://github.com/autores/repo",
        })
    papers = classificacao.selecionar(base, force=True)
    assert papers[0].evidencia_artefato is True
    assert papers[0].links_artefato == ["https://github.com/autores/repo"]

    res, llm = _rodar(base, cfg, {**RESPOSTA_B, "artefato_status": "liberado"}, "run-1")
    assert "https://github.com/autores/repo" in llm.prompts_b[0]
    row = base.execute("SELECT artefato_aberto FROM vw_artefato").fetchone()
    assert row["artefato_aberto"] == 1


@pytest.mark.parametrize("abstract,esperado", [
    ("Code at https://github.com/a/b.", 1),
    ("Weights: https://huggingface.co/org/model", 1),
    ("No link here.", 0),
])
def test_link_no_abstract_e_evidencia(base, abstract, esperado):
    with db.transacao(base):
        db.upsert_paper(base, {"paper_id": PID, "titulo": "P", "abstract": abstract,
                               "primeiro_visto_em": db.agora()})
    assert base.execute("SELECT evidencia FROM vw_artefato").fetchone()[0] == esperado


def test_modelo_vinculado_em_snapshot_antigo_e_evidencia(base):
    """O snapshot mais recente costuma vir com os contadores nulos; a view le
    o maximo de todos."""
    with db.transacao(base):
        db.upsert_metrica(base, {"paper_id": PID, "data_snapshot": "2026-09-01", "qtd_modelos": 2, "origem": "por_paper"})
        db.upsert_metrica(base, {"paper_id": PID, "data_snapshot": "2026-10-01", "qtd_modelos": None, "origem": "daily"})
    assert base.execute("SELECT evidencia FROM vw_artefato").fetchone()[0] == 1


def test_selecionar_exceto_run_id_leva_so_quem_falta(cfg, base):
    with db.transacao(base):
        db.upsert_paper(base, {"paper_id": "2608.00002", "titulo": "Q", "primeiro_visto_em": db.agora()})
    _rodar(base, cfg, RESPOSTA_B, "run-total")
    with db.transacao(base):
        base.execute("UPDATE fato_triagem SET run_id = 'run-velho' WHERE paper_id = '2608.00002'")
    papers = classificacao.selecionar(base, force=True, exceto_run_id="run-total")
    assert [p.paper_id for p in papers] == ["2608.00002"]


def test_reclassificar_retomar_reaproveita_o_run_id_e_reconta(cfg, base):
    with db.transacao(base):
        db.upsert_paper(base, {"paper_id": "2608.00002", "titulo": "Q", "primeiro_visto_em": db.agora()})
    primeira = execucao.reclassificar(
        cfg=cfg, conn=base, ids=[PID], cliente_llm=LLMComResposta(base, cfg, RESPOSTA_B),
    )
    r = execucao.reclassificar(
        cfg=cfg, conn=base, tudo=True, retomar=primeira.run_id,
        cliente_llm=LLMComResposta(base, cfg, RESPOSTA_B),
    )
    assert r.run_id == primeira.run_id
    assert r.selecionados == 1                       # so o que faltava
    assert r.aprovados == 2                          # recontado da rodada inteira
    assert execucao.conferir(base, r.run_id) == {"outro_run_id": 0, "sem_triagem": 0}
    linha = base.execute("SELECT qtd_aprovados, qtd_pr_implementar FROM log_execucao WHERE run_id = ?", (r.run_id,)).fetchone()
    assert tuple(linha) == (2, 2)
