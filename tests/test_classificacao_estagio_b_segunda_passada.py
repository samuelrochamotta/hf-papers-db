"""Issue #1: falha do Estagio B nao fabrica veredito, ganha segunda passada.

Cobre o que `test_execucao.py::test_falha_do_estagio_b_nao_aborta_a_rodada` nao
cobre: a segunda passada resolvendo uma falha transitoria, e o paper com linha
existente (`--force`) sobrevivendo intacto a duas falhas. Chama
`classificacao.rodar` direto, sem HF nem respx - so a duble de LLM importa
aqui.
"""

import pytest
from conftest import RESPOSTA_B, LLMDuble, LLMQuebrado

from hfpapers import db
from hfpapers.estagios import classificacao
from hfpapers.llm.cliente import ErroLLM, Resposta, Uso
from hfpapers.llm.estagio_a import PaperEntrada


@pytest.fixture()
def base(conn):
    with db.transacao(conn):
        db.upsert_area(conn, {"area": "Agentes & automação", "definicao": "d"})
        db.upsert_topico(conn, {"topico": "Agentes de codificação", "definicao": "d"})
        db.upsert_paper(
            conn, {"paper_id": "2608.00001", "titulo": "P", "primeiro_visto_em": db.agora()}
        )
    return conn


def _entrada(paper_id: str = "2608.00001") -> PaperEntrada:
    return PaperEntrada(paper_id=paper_id, titulo="P", abstract="um abstract", keywords=[])


class LLMFalhaTransitoria(LLMDuble):
    """Derruba a 1a chamada do Estagio B; a 2a (ja na segunda passada) segue
    o caminho normal da duble - todo Estagio A vira "candidato" (RESPOSTA_A)."""

    def chamar(self, *, etapa, **kw):
        if etapa == "estagio_b" and self.tentativas_b == 0:
            self.tentativas_b += 1
            raise ErroLLM("instabilidade transitoria")
        return super().chamar(etapa=etapa, **kw)


class LLMComVeredito(LLMDuble):
    """Estagio B sempre devolve um veredito fixo - usado para exercitar os
    ramos de `_gravar_sucesso_b` (fora do escopo direto da falha do Estagio
    B) que a extracao da issue #1 passou a compartilhar entre a 1a e a 2a
    passada. "fora" nao aprova (ficha null); qualquer outro veredito aprova
    com a ficha padrao de `RESPOSTA_B`."""

    def __init__(self, *a, veredito: str, **kw):
        super().__init__(*a, **kw)
        self._veredito = veredito

    def chamar(self, *, etapa, modelo, prompt, validar=None, paper_id=None, **kw):
        if etapa != "estagio_b":
            return super().chamar(
                etapa=etapa, modelo=modelo, prompt=prompt, validar=validar,
                paper_id=paper_id, **kw,
            )
        self.chamadas.append((etapa, paper_id))
        self.tentativas_b += 1
        if self._veredito == "fora":
            dados = {
                **RESPOSTA_B,
                "veredito": "fora",
                "ficha": None,
                "justificativa_veredito": "colapsa em generalidade",
            }
        else:
            dados = {**RESPOSTA_B, "veredito": self._veredito}
        if validar:
            validar(dados)
        uso = Uso(100, 50, 0.0001, 1)
        self.uso.somar(uso)
        return Resposta(dados, uso, modelo, 1, 10)


def test_segunda_passada_resolve_falha_transitoria(cfg, base):
    """Criterio 2: quem falha na 1a passada e recupera na 2a segue o caminho
    normal - grava triagem e ficha, sem aviso e sem ficar pendente. E o
    Estagio A, que ja tinha rodado na 1a passada, nao repete na 2a."""
    llm = LLMFalhaTransitoria(base, cfg, um_a_cada=1)

    res = classificacao.rodar(base, llm, [_entrada()], run_id="run-1", cfg=cfg)

    assert llm.tentativas_b == 2  # 1a passada falhou, a segunda passada chamou de novo
    assert len([c for c in llm.chamadas if c[0] == "estagio_a"]) == 1  # A nao repete
    assert res.avisos == []
    assert res.nao_classificados == 0
    assert res.estrito == 1        # RESPOSTA_B: veredito "estrito"
    assert res.fichas == 1
    assert db.contar(base, "fato_triagem") == 1
    assert db.contar(base, "dim_ficha") == 1
    # o custo e os tokens da chamada que passou na 2a passada nao podem sumir
    # do total da rodada - senao a rodada mente sobre quanto gastou
    assert res.uso.chamadas == 2      # Estagio A + o B que passou na 2a passada
    assert res.uso.custo_usd == pytest.approx(0.0002)


def test_paper_novo_com_falha_nas_duas_passadas_fica_pendente(cfg, base):
    """Criterio 1: paper novo cujo Estagio B falha nas duas passadas nao grava
    nada em fato_triagem - fica pendente, repescado por `selecionar` sem
    `force`, exatamente como um paper novo."""
    llm = LLMQuebrado(base, cfg, um_a_cada=1)

    res = classificacao.rodar(base, llm, [_entrada()], run_id="run-1", cfg=cfg)

    assert llm.tentativas_b == 2
    assert db.contar(base, "fato_triagem") == 0
    assert db.contar(base, "dim_ficha") == 0
    assert res.nao_classificados == 1
    assert res.classificados == 0
    assert res.avisos == ["estagio_b_falhou:2608.00001"]

    pendentes = classificacao.selecionar(base)
    assert [p.paper_id for p in pendentes] == ["2608.00001"]


def test_force_com_falha_nas_duas_passadas_mantem_linha_e_ficha_intactas(cfg, base):
    """Criterio 3: paper que ja tem linha (reclassificar --force) e cujo
    Estagio B falha mesmo apos a segunda passada mantem a linha existente e a
    ficha intactas - nada e apagado nem sobrescrito no caminho de falha."""
    llm_ok = LLMDuble(base, cfg, um_a_cada=1)
    r1 = classificacao.rodar(base, llm_ok, [_entrada()], run_id="run-1", cfg=cfg)
    assert r1.estrito == 1 and r1.fichas == 1
    assert db.contar(base, "fato_triagem") == 1
    assert db.contar(base, "dim_ficha") == 1

    triagem_antes = dict(base.execute("SELECT * FROM fato_triagem").fetchone())
    ficha_antes = dict(base.execute("SELECT * FROM dim_ficha").fetchone())

    papers = classificacao.selecionar(base, force=True)
    assert [p.paper_id for p in papers] == ["2608.00001"]

    llm_quebrado = LLMQuebrado(base, cfg, um_a_cada=1)
    res = classificacao.rodar(base, llm_quebrado, papers, run_id="run-2", cfg=cfg)

    assert llm_quebrado.tentativas_b == 2  # as duas passadas realmente aconteceram
    assert res.nao_classificados == 1
    assert res.avisos == ["estagio_b_falhou:2608.00001"]
    assert db.contar(base, "fato_triagem") == 1
    assert db.contar(base, "dim_ficha") == 1
    assert dict(base.execute("SELECT * FROM fato_triagem").fetchone()) == triagem_antes
    assert dict(base.execute("SELECT * FROM dim_ficha").fetchone()) == ficha_antes


def test_reprovacao_do_estagio_b_apaga_ficha_orfa(cfg, base):
    """Ramo pre-existente de `_gravar_sucesso_b`, exposto sem rede pela
    extracao da issue #1: quando o Estagio B reprova (veredito "fora") um
    paper que ja tinha ficha de uma classificacao anterior, a ficha orfa e
    apagada - nao fica para tras contradizendo o veredito atual."""
    llm_ok = LLMDuble(base, cfg, um_a_cada=1)
    classificacao.rodar(base, llm_ok, [_entrada()], run_id="run-1", cfg=cfg)
    assert db.contar(base, "dim_ficha") == 1

    papers = classificacao.selecionar(base, force=True)
    llm_fora = LLMComVeredito(base, cfg, um_a_cada=1, veredito="fora")
    res = classificacao.rodar(base, llm_fora, papers, run_id="run-2", cfg=cfg)

    assert res.fora == 1
    assert db.contar(base, "dim_ficha") == 0
    row = base.execute("SELECT veredito FROM fato_triagem").fetchone()
    assert row["veredito"] == "fora"


def test_veredito_amplo_e_gravado_e_contado(cfg, base):
    """`_gravar_sucesso_b` tambem grava e conta o veredito "amplo" - a issue
    #1 e literalmente sobre parar de fabricar esse veredito na falha, entao o
    caminho em que ele e legitimo (o Estagio B decidiu de verdade) precisa
    continuar gravando ficha e contando em `res.amplo`, nao em `res.estrito`."""
    llm = LLMComVeredito(base, cfg, um_a_cada=1, veredito="amplo")

    res = classificacao.rodar(base, llm, [_entrada()], run_id="run-1", cfg=cfg)

    assert res.amplo == 1
    assert res.estrito == 0
    assert res.fichas == 1
    assert db.contar(base, "fato_triagem") == 1
    assert db.contar(base, "dim_ficha") == 1
    row = base.execute("SELECT veredito FROM fato_triagem").fetchone()
    assert row["veredito"] == "amplo"


def test_caminho_sem_falha_nao_dispara_segunda_passada(cfg, base):
    """Criterio 9: nenhuma mudanca de comportamento quando o Estagio B nao
    falha - grava na 1a passada e nao ha segunda passada nenhuma."""
    llm = LLMDuble(base, cfg, um_a_cada=1)

    res = classificacao.rodar(base, llm, [_entrada()], run_id="run-1", cfg=cfg)

    assert res.nao_classificados == 0
    assert res.avisos == []
    assert len([c for c in llm.chamadas if c[0] == "estagio_b"]) == 1  # sem 2a passada
    assert db.contar(base, "fato_triagem") == 1


def test_backoff_da_segunda_passada(cfg, base, monkeypatch):
    """Criterio 2: a espera antes da segunda passada precisa ser maior que a
    do `llm.retry` (0.5s aqui) - e uma so espera para o lote inteiro, nao uma
    por paper falho. Fixamos o numero (2.0s = 0.5 * 4) porque o valor e o
    contrato: um multiplicador zerado ou baixo demais degradaria a segunda
    passada para uma retentativa na mesma janela de instabilidade que causou
    a falha - exatamente o que a issue diz nao funcionar."""
    cfg.llm.retry.backoff_inicial_s = 0.5
    esperas: list[float] = []
    monkeypatch.setattr(classificacao.time, "sleep", esperas.append)
    with db.transacao(base):
        db.upsert_paper(
            base, {"paper_id": "2608.00002", "titulo": "P2", "primeiro_visto_em": db.agora()}
        )
    llm = LLMQuebrado(base, cfg, um_a_cada=1)
    entradas = [_entrada("2608.00001"), _entrada("2608.00002")]

    classificacao.rodar(base, llm, entradas, run_id="run-1", cfg=cfg)

    assert len(esperas) == 1                          # uma espera para o lote, nao por paper
    assert esperas == [pytest.approx(2.0)]             # 0.5 * 4, numero fixo
    assert esperas[0] > cfg.llm.retry.backoff_inicial_s  # o contrato: maior que o retry interno


def test_sem_falha_nao_espera(cfg, base, monkeypatch):
    """Sem falha nenhuma, a segunda passada nem roda - `time.sleep` nem e
    chamado."""
    cfg.llm.retry.backoff_inicial_s = 0.5
    esperas: list[float] = []
    monkeypatch.setattr(classificacao.time, "sleep", esperas.append)
    llm = LLMDuble(base, cfg, um_a_cada=1)

    classificacao.rodar(base, llm, [_entrada()], run_id="run-1", cfg=cfg)

    assert esperas == []
