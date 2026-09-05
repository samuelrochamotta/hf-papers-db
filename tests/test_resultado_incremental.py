"""O acumulado da classificacao pertence a quem chama, nao ao `return`.

Achado da revisao do bloco 2: quando a varredura estourava no meio,
`log_execucao` era fechada com `qtd_fora = qtd_amplo = qtd_estrito = 0`, porque
esses campos so eram preenchidos com o valor **devolvido** por
`classificacao.rodar`. Numa rodada de horas isso perde a contagem de centenas
de triagens ja gravadas - e ainda faz `doutor.checar_pendencias` recusar a
rodada como corte, porque ele so considera execucao que classificou alguem.

Aqui tambem mora a passagem da concorrencia pelo `execucao.reclassificar`: e o
unico chamador que a expoe na linha de comando.
"""

import pytest
from conftest import LLMDuble

from hfpapers import db, doutor, execucao
from hfpapers.estagios import classificacao
from hfpapers.llm.estagio_a import PaperEntrada


EXPLODE_EM = "2608.00002"  # o terceiro do lote: dois passam antes


class LLMExplode(LLMDuble):
    """Classifica normalmente ate chegar em `explode_em`, e entao estoura.

    Pelo `paper_id`, e nao por contagem de chamadas: sob concorrencia a ordem
    das chamadas nao e estavel, e o teste ficaria decidindo por sorteio quantos
    papers passaram antes do estouro.

    `RuntimeError`, e nao `ErroLLM`, de proposito: `ErroLLM` e falha prevista
    (vira aviso e o paper e pulado). O que este teste cobre e o estouro que a
    rodada **nao** trata - disco cheio, banco travado, Ctrl+C - e que sobe ate
    quem chamou.
    """

    def __init__(self, conn, cfg, *, explode_em=EXPLODE_EM):
        super().__init__(conn, cfg, um_a_cada=1)
        self.explode_em = explode_em

    def chamar(self, *, etapa, paper_id=None, **kw):
        if etapa == "estagio_a" and paper_id == self.explode_em:
            raise RuntimeError("banco travado")
        return super().chamar(etapa=etapa, paper_id=paper_id, **kw)


@pytest.fixture()
def base(cfg):
    conn = db.abrir(cfg)
    with db.transacao(conn):
        db.upsert_area(conn, {"area": "Agentes & automação", "definicao": "d"})
        db.upsert_topico(conn, {"topico": "Agentes de codificação", "definicao": "d"})
        for i in range(5):
            db.upsert_paper(
                conn,
                {
                    "paper_id": f"2608.0000{i}",
                    "titulo": f"Paper {i}",
                    "abstract": "Um resumo qualquer, longo o bastante para o prompt. " * 3,
                    "data_hf_daily": "2026-08-25",
                    "primeiro_visto_em": "2026-08-25T07:30:00",
                },
            )
    yield conn
    conn.close()


def _entradas(n=5):
    return [
        PaperEntrada(paper_id=f"2608.0000{i}", titulo=f"Paper {i}", abstract="um abstract", keywords=[])
        for i in range(n)
    ]


@pytest.mark.parametrize("concorrencia", [1, 4])
def test_acumulado_sobrevive_ao_estouro_da_varredura(cfg, base, concorrencia):
    """O objeto passado em `res` e o mesmo que a varredura vai enchendo: o que
    foi classificado antes do estouro fica com quem chamou. Vale nas duas
    varreduras - a paralela nao pode perder o acumulado no caminho."""
    res = classificacao.ResultadoClassificacao()
    llm = LLMExplode(base, cfg)

    with pytest.raises(RuntimeError):
        classificacao.rodar(
            base, llm, _entradas(), run_id="run-1", cfg=cfg,
            concorrencia=concorrencia, res=res,
        )

    assert res.classificados == 2          # os dois que passaram antes do estouro
    assert res.uso.chamadas > 0            # e o que eles custaram
    assert db.contar(base, "fato_triagem") == 2


def test_log_execucao_guarda_o_que_a_rodada_alcancou(cfg, base):
    """A consequencia que motivou o conserto: rodada que estoura no meio fecha
    com `status='erro'`, mas com as contagens reais - nao com zeros."""
    llm = LLMExplode(base, cfg)

    with pytest.raises(RuntimeError):
        execucao.reclassificar(cfg=cfg, conn=base, tudo=True, cliente_llm=llm)

    linha = base.execute("SELECT * FROM log_execucao ORDER BY iniciado_em").fetchone()
    assert linha["status"] == "erro"
    assert linha["qtd_fora"] + linha["qtd_amplo"] + linha["qtd_estrito"] == 2
    assert linha["custo_usd"] > 0


def test_rodada_que_estourou_serve_de_corte_para_o_doutor(cfg, base):
    """O outro efeito do zero: `checar_pendencias` so aceita como corte a
    ultima execucao que classificou alguem. Com as contagens zeradas essa
    rodada nao existia para ele, e os tres papers que ela nao alcancou passavam
    por "na fila" - em `ok`. Com as contagens reais eles viram o que sao:
    pendentes que ja tiveram a sua chance."""
    llm = LLMExplode(base, cfg)
    with pytest.raises(RuntimeError):
        execucao.reclassificar(cfg=cfg, conn=base, tudo=True, cliente_llm=llm)

    item = doutor.checar_pendencias(cfg)
    assert item.estado == doutor.AVISO
    assert item.dados["atrasados"] == 3


# ── passagem da concorrencia ────────────────────────────────────────────────


def test_reclassificar_usa_a_concorrencia_do_config_por_padrao(cfg, base, monkeypatch):
    pedidos = []
    real = classificacao.rodar
    monkeypatch.setattr(
        classificacao, "rodar",
        lambda *a, **kw: (pedidos.append(kw.get("concorrencia")), real(*a, **kw))[1],
    )
    cfg.llm.concorrencia = 3

    execucao.reclassificar(cfg=cfg, conn=base, tudo=True, cliente_llm=LLMDuble(base, cfg))

    assert pedidos == [3]


def test_flag_sobrepoe_o_config(cfg, base, monkeypatch):
    """`--concorrencia` existe justamente para a rodada total pedir mais do que
    o padrao conservador do arquivo."""
    pedidos = []
    real = classificacao.rodar
    monkeypatch.setattr(
        classificacao, "rodar",
        lambda *a, **kw: (pedidos.append(kw.get("concorrencia")), real(*a, **kw))[1],
    )
    cfg.llm.concorrencia = 1

    execucao.reclassificar(
        cfg=cfg, conn=base, tudo=True, concorrencia=6, cliente_llm=LLMDuble(base, cfg)
    )

    assert pedidos == [6]
