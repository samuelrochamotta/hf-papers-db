"""Concorrencia no estagio 3: paraleliza o I/O, nao a decisao.

O contrato que estes testes travam e um so, em quatro pedacos: uma rodada com
`concorrencia=4` tem de terminar com **o mesmo banco** e as mesmas contagens de
uma com `concorrencia=1`; a concorrencia tem de ser real (chamadas se
sobrepondo); `concorrencia=1` nao pode criar thread nenhuma; e uma falha num
paper nao contamina os vizinhos.

Nenhum teste fala com o OpenRouter - o duble dorme uns milissegundos para que a
sobreposicao seja observavel, e conta o pico de chamadas simultaneas.
"""

import json
import threading
import time
from types import SimpleNamespace

import pytest
from conftest import RESPOSTA_A, RESPOSTA_A_FORA, RESPOSTA_B, LLMDuble, povoar_vocabulario

from hfpapers import db
from hfpapers.estagios import classificacao
from hfpapers.llm.cliente import ClienteLLM, ErroLLM, Preco, Resposta, Uso
from hfpapers.llm.estagio_a import PaperEntrada

NAO_COUBE = {
    "eixo": "subarea",
    "justificativa": "Compilar prompt em artefato executavel nao e nenhuma das filhas de Harness.",
}


class LLMConcorrente(LLMDuble):
    """Duble com latencia, deterministico por `paper_id` e seguro em thread.

    Deterministico por id, e nao por contagem de chamadas (`um_a_cada` do
    `LLMDuble`), porque sob concorrencia a ordem das chamadas nao e estavel -
    seria o proprio duble a introduzir a nao-determinacao que o teste quer
    negar.

    Grava em `log_llm` pelo `_registrar` herdado de proposito: e o caminho que
    o buffer de `ClienteLLM.registros_adiados` intercepta, e sem ele a tabela
    ficaria vazia e a ordem dela nao seria testada.
    """

    def __init__(
        self, conn, cfg, *, fora=(), falha_b_uma_vez=(), falha_a=(), nao_couberam=(),
        atraso=0.02,
    ):
        super().__init__(conn, cfg, um_a_cada=1)
        self.fora = set(fora)
        self.falha_b_uma_vez = set(falha_b_uma_vez)
        self.falha_a = set(falha_a)
        self.nao_couberam = set(nao_couberam)
        self.atraso = atraso
        self.mutex = threading.Lock()
        self.simultaneas = 0
        self.pico = 0
        self.threads: set[str] = set()
        self._ja_falhou_b: set[str] = set()

    def chamar(self, *, etapa, modelo, prompt, validar=None, paper_id=None, **kw):
        with self.mutex:
            self.simultaneas += 1
            self.pico = max(self.pico, self.simultaneas)
            self.threads.add(threading.current_thread().name)
            self.chamadas.append((etapa, paper_id))
            if etapa == "estagio_b":
                self.tentativas_b += 1
            primeira_falha_b = (
                etapa == "estagio_b"
                and paper_id in self.falha_b_uma_vez
                and paper_id not in self._ja_falhou_b
            )
            if primeira_falha_b:
                self._ja_falhou_b.add(paper_id)
        try:
            time.sleep(self.atraso)
            if etapa == "estagio_a" and paper_id in self.falha_a:
                self._registrar(etapa, modelo, paper_id, Uso(), 1, "provedor fora do ar")
                raise ErroLLM("provedor fora do ar")
            if primeira_falha_b:
                self._registrar(etapa, modelo, paper_id, Uso(), 1, "instabilidade transitoria")
                raise ErroLLM("instabilidade transitoria")

            if etapa == "estagio_a":
                dados = dict(RESPOSTA_A_FORA if paper_id in self.fora else RESPOSTA_A)
                if paper_id in self.nao_couberam:
                    dados["nao_coube"] = NAO_COUBE
            else:
                dados = RESPOSTA_B
            if validar:
                validar(dados)
            uso = Uso(100, 50, 0.0001, 1)
            with self.mutex:
                self.uso.somar(uso)
            self._registrar(etapa, modelo, paper_id, uso, 1, None, 10)
            return Resposta(dados, uso, modelo, 1, 10)
        finally:
            with self.mutex:
                self.simultaneas -= 1


@pytest.fixture()
def base(conn):
    with db.transacao(conn):
        povoar_vocabulario(conn)
        for i in range(1, 9):
            db.upsert_paper(
                conn,
                {"paper_id": f"2608.0000{i}", "titulo": f"P{i}", "primeiro_visto_em": db.agora()},
            )
    return conn


def _lote() -> list[PaperEntrada]:
    return [
        PaperEntrada(paper_id=f"2608.0000{i}", titulo=f"P{i}", abstract="um abstract", keywords=[])
        for i in range(1, 9)
    ]


# Um lote que mistura os tres caminhos do estagio: `fora` no A, aprovado no B, e
# falha no B recuperada na segunda passada. Sem essa mistura o teste de
# equivalencia so provaria que o caminho feliz e deterministico.
FORA = ("2608.00002", "2608.00005")
FALHA_B = ("2608.00003", "2608.00007")
NAO_COUBERAM = ("2608.00001", "2608.00006")  # dois: o nao-encaixe entra na fila por paper

# Colunas de relogio: mudam entre duas rodadas por definicao, e nao e delas que
# o teste de equivalencia trata.
_VOLATEIS = {"latencia_ms"}


def _estado(conn) -> dict[str, list[tuple]]:
    """O banco inteiro, tabela a tabela, na ordem fisica das linhas.

    Na ordem fisica (sem ORDER BY) de proposito: a ordem de gravacao e parte do
    contrato, nao so o conteudo. `log_llm` tem `id` AUTOINCREMENT, entao drenar
    o buffer fora de ordem apareceria aqui.
    """
    saida = {}
    for tabela in db.TABELAS_ESPERADAS:
        cols = [
            c for c in db.colunas(conn, tabela)
            if not c.endswith("_em") and c not in _VOLATEIS
        ]
        saida[tabela] = [
            tuple(r) for r in conn.execute(f"SELECT {', '.join(cols)} FROM {tabela}")
        ]
    return saida


def _rodar(conn, cfg, concorrencia: int):
    llm = LLMConcorrente(
        conn, cfg, fora=FORA, falha_b_uma_vez=FALHA_B, nao_couberam=NAO_COUBERAM
    )
    res = classificacao.rodar(
        conn, llm, _lote(), run_id="run-1", cfg=cfg, concorrencia=concorrencia
    )
    return res, llm


def test_concorrencia_4_produz_o_mesmo_banco_que_1(cfg, tmp_path, base):
    """O teste central: paralelizar o I/O nao pode mudar o resultado.

    Duas bases identicas, o mesmo lote, so a concorrencia muda. Compara o banco
    inteiro - inclusive a ordem fisica das linhas, que e onde a ordem de
    gravacao vira dado - e as contagens.
    """
    outra = db.conectar(tmp_path / "paralela.db")
    try:
        with db.transacao(outra):
            povoar_vocabulario(outra)
            for i in range(1, 9):
                db.upsert_paper(
                    outra,
                    {"paper_id": f"2608.0000{i}", "titulo": f"P{i}", "primeiro_visto_em": db.agora()},
                )

        seq, llm_seq = _rodar(base, cfg, 1)
        par, llm_par = _rodar(outra, cfg, 4)

        assert _estado(outra) == _estado(base)
        assert (par.fora, par.amplo, par.estrito) == (seq.fora, seq.amplo, seq.estrito)
        assert (par.fichas, par.nao_classificados, par.pulados) == (
            seq.fichas, seq.nao_classificados, seq.pulados
        )
        assert par.avisos == seq.avisos
        assert par.uso.chamadas == seq.uso.chamadas
        assert par.uso.custo_usd == pytest.approx(seq.uso.custo_usd)
        # o lote de fato exercitou os tres caminhos
        assert seq.fora == 2 and seq.estrito == 6 and seq.nao_classificados == 0
        assert llm_seq.tentativas_b == llm_par.tentativas_b == 8  # 6 + as 2 da 2a passada
    finally:
        outra.close()


def test_concorrencia_4_chama_em_paralelo_de_verdade(cfg, base):
    """Sem isto o teste de equivalencia passaria com uma implementacao que so
    finge paralelizar. O pico de chamadas simultaneas tem de passar de 1, e
    mais de uma thread tem de ter chamado."""
    res, llm = _rodar(base, cfg, 4)

    assert llm.pico > 1
    assert len(llm.threads) > 1
    assert threading.main_thread().name not in llm.threads  # nenhuma chamada na principal
    assert res.classificados == 8


def test_concorrencia_1_nao_cria_thread_nenhuma(cfg, base):
    """`concorrencia=1` e o caminho da rodada diaria: sequencial, sem pool.

    Nao basta o resultado bater - o requisito e nao haver thread. Aqui isso e
    observavel duas vezes: toda chamada saiu da thread principal, e a contagem
    de threads vivas nao mudou.
    """
    vivas_antes = threading.active_count()
    res, llm = _rodar(base, cfg, 1)

    assert llm.threads == {threading.main_thread().name}
    assert llm.pico == 1
    assert threading.active_count() == vivas_antes
    assert res.classificados == 8


def test_falha_de_um_paper_nao_contamina_os_outros(cfg, base):
    """Concorrencia nao pode transformar falha isolada em falha de lote: o
    paper cujo Estagio A cai vira aviso e `pulados`, e os outros sete seguem
    classificados normalmente."""
    llm = LLMConcorrente(base, cfg, fora=FORA, falha_a=("2608.00004",))
    res = classificacao.rodar(
        base, llm, _lote(), run_id="run-1", cfg=cfg, concorrencia=4
    )

    assert res.avisos == ["estagio_a_falhou:2608.00004"]
    assert res.pulados == 1
    assert res.classificados == 7
    assert db.contar(base, "fato_triagem") == 7
    ids = {r["paper_id"] for r in base.execute("SELECT paper_id FROM fato_triagem")}
    assert "2608.00004" not in ids


def test_ordem_de_gravacao_segue_a_ordem_do_lote(cfg, base):
    """A ordem das gravacoes e contrato, nao acaso: e ela que faz `revisao` de
    `fato_triagem` e o `id` de `log_llm` sairem sempre iguais.

    Quem a torna observavel e `log_llm`, cujo `id` e AUTOINCREMENT: o duble
    dorme e as threads terminam fora de ordem, mas as linhas tem de sair na
    ordem do lote - e, dentro de um paper, na ordem das chamadas. Os dois que
    cairam no Estagio B aparecem duas vezes: a falha na varredura e a
    recuperacao no fim, na segunda passada.
    """
    _rodar(base, cfg, 4)

    linhas = [
        (r["paper_id"], r["etapa"], bool(r["erro"]))
        for r in base.execute("SELECT paper_id, etapa, erro FROM log_llm ORDER BY id")
    ]
    esperado = []
    for p in _lote():
        esperado.append((p.paper_id, "estagio_a", False))
        if p.paper_id in FORA:
            continue
        esperado.append((p.paper_id, "estagio_b", p.paper_id in FALHA_B))
    esperado += [(pid, "estagio_b", False) for pid in FALHA_B]  # a segunda passada

    assert linhas == esperado


def test_segunda_passada_tambem_e_paralela(cfg, base):
    """A segunda passada e o resto da rodada: paraleliza-la e o que evita que
    um lote com muitas falhas transitorias volte ao ritmo sequencial."""
    llm = LLMConcorrente(base, cfg, falha_b_uma_vez=[f"2608.0000{i}" for i in range(1, 9)])
    res = classificacao.rodar(
        base, llm, _lote(), run_id="run-1", cfg=cfg, concorrencia=4
    )

    assert res.estrito == 8          # todos recuperados na segunda passada
    assert res.nao_classificados == 0
    assert llm.tentativas_b == 16    # 8 falhas + 8 recuperacoes
    assert llm.pico > 1


# ── teto de seguranca ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "pedido, esperado",
    [(1, 1), (4, 4), (8, 8), (9, 8), (400, 8), (0, 1), (-3, 1)],
)
def test_teto_e_piso_da_concorrencia(pedido, esperado):
    """Valor absurdo nao derruba a rodada: e cortado com aviso. Abortar uma
    varredura de horas por causa de um digito seria pior que roda-la mais
    devagar - e o rate limit do OpenRouter e o motivo do teto existir."""
    assert classificacao.normalizar_concorrencia(pedido) == esperado


def test_concorrencia_absurda_ainda_classifica(cfg, base):
    """O corte e de verdade: com 400 pedidos a rodada roda (com 8) em vez de
    estourar."""
    llm = LLMConcorrente(base, cfg, fora=FORA)
    res = classificacao.rodar(
        base, llm, _lote(), run_id="run-1", cfg=cfg, concorrencia=400
    )
    assert res.classificados == 8
    assert len(llm.threads) <= classificacao.CONCORRENCIA_MAXIMA


# ── prazo estourando sob concorrencia ───────────────────────────────────────
#
# O `llm.prazo_total_s` roda a chamada numa thread daemon e a **abandona** no
# prazo. A thread orfa continua presa no I/O, e o que segura o desenho e uma
# propriedade so: `_criar` nao toca estado do cliente - nao chama
# `_contabilizar`, nao chama `_registrar`, nao toma `_TRAVA`. Se ela pudesse,
# uma orfa que voltasse depois somaria uso de uma chamada descartada, ou
# gravaria uma linha de `log_llm` fora de ordem.
#
# Essa propriedade nao aparece em teste nenhum: ela e frágil a qualquer edicao
# futura de `_criar`, e cai em silencio. Os testes daqui para baixo usam o
# `ClienteLLM` de verdade, com um transporte falso no lugar do `openai` - e a
# unica forma de `_com_prazo` rodar de verdade: o `LLMConcorrente` sobrescreve
# `chamar` inteiro e nunca chega la.

TITULOS_LENTOS = ("TITULO-02", "TITULO-05", "TITULO-07")


class TransporteLento:
    """Imita `client.chat.completions.create`, e dorme nos papers escolhidos.

    Deterministico pelo titulo, que e o que chega ao prompt: sob concorrencia a
    ordem das chamadas nao e estavel, e um duble que respondesse por contagem
    seria ele proprio a fonte da nao-determinacao que o teste quer negar.

    O atraso e muito maior que o prazo de proposito: a thread orfa fica viva
    depois de a chamada ter sido abandonada, que e a situacao sob teste.
    """

    def __init__(self, lentos=TITULOS_LENTOS, atraso=0.4):
        self.lentos = set(lentos)
        self.atraso = atraso
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, *, model, messages, **kw):
        texto = " ".join(m["content"] for m in messages)
        if model.endswith("-a") and any(t in texto for t in self.lentos):
            time.sleep(self.atraso)
        dados = RESPOSTA_B if model.endswith("-b") else RESPOSTA_A
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=json.dumps(dados)),
                    finish_reason="stop",
                )
            ],
            usage=SimpleNamespace(prompt_tokens=100, completion_tokens=50),
        )


def _lote_titulado() -> list[PaperEntrada]:
    return [
        PaperEntrada(
            paper_id=f"2608.0000{i}",
            titulo=f"TITULO-0{i}",
            abstract="um abstract",
            keywords=[],
        )
        for i in range(1, 9)
    ]


def _base_titulada(conn):
    with db.transacao(conn):
        povoar_vocabulario(conn)
        for i in range(1, 9):
            db.upsert_paper(
                conn,
                {
                    "paper_id": f"2608.0000{i}",
                    "titulo": f"TITULO-0{i}",
                    "primeiro_visto_em": db.agora(),
                },
            )
    return conn


def _cliente_real(conn, cfg):
    return ClienteLLM(
        cfg,
        conn=conn,
        run_id="run-1",
        cliente=TransporteLento(),
        precos={"modelo/teste-a": Preco(1e-6, 2e-6), "modelo/teste-b": Preco(2e-6, 1e-5)},
        parametros={},
    )


def _rodar_com_prazo(conn, cfg, concorrencia: int):
    cfg.llm.prazo_total_s = 0.05
    return classificacao.rodar(
        conn,
        _cliente_real(conn, cfg),
        _lote_titulado(),
        run_id="run-1",
        cfg=cfg,
        concorrencia=concorrencia,
    )


def test_prazo_estourando_em_concorrencia_4_da_o_mesmo_banco_que_em_1(
    cfg, tmp_path, conn
):
    """Tres dos oito papers estouram o prazo em todas as tentativas, e as
    threads orfas continuam vivas enquanto a rodada segue. O banco tem de sair
    identico ao da rodada sequencial - linha a linha e na ordem fisica.

    E o teste que trava a propriedade "`_criar` nao toca estado do cliente".
    Se um dia ele passar a contabilizar uso ou a gravar em `log_llm`, a orfa
    que volta depois do abandono escreve numa rodada que ja seguiu adiante, e a
    igualdade aqui quebra - com quatro threads o momento em que cada orfa volta
    nao coincide com o da rodada sequencial.
    """
    sequencial = _base_titulada(conn)
    paralela = db.conectar(tmp_path / "paralela.db")
    try:
        _base_titulada(paralela)

        seq = _rodar_com_prazo(sequencial, cfg, 1)
        par = _rodar_com_prazo(paralela, cfg, 4)

        assert _estado(paralela) == _estado(sequencial)
        assert (par.fora, par.amplo, par.estrito) == (seq.fora, seq.amplo, seq.estrito)
        assert par.avisos == seq.avisos
        # o lote de fato exercitou o corte: os tres lentos caem no Estagio A
        assert seq.avisos == [f"estagio_a_falhou:2608.0000{i}" for i in (2, 5, 7)]
        assert seq.pulados == 3 and seq.classificados == 5
    finally:
        paralela.close()


def test_a_orfa_do_prazo_nao_acrescenta_linha_em_log_llm(cfg, conn):
    """A thread abandonada volta com uma resposta que ninguem leu. Se ela
    gravasse, `log_llm` ganharia linhas depois do fim da rodada - e a
    conferencia da fatura passaria a depender de quando o processo terminou.

    O `sleep` no fim e o teste: ele da a todas as orfas tempo de voltar. A
    contagem tem de ser a mesma antes e depois.
    """
    _rodar_com_prazo(_base_titulada(conn), cfg, 4)
    antes = db.contar(conn, "log_llm")

    # tempo de sobra para as 9 orfas (3 papers x 3 tentativas) voltarem do
    # `sleep` de 0,4 s do transporte
    time.sleep(1.0)

    assert db.contar(conn, "log_llm") == antes
    # 3 tentativas por paper lento, todas com ErroPrazo, e nada alem disso
    prazos = [
        r["paper_id"]
        for r in conn.execute("SELECT paper_id FROM log_llm WHERE erro LIKE 'ErroPrazo%'")
    ]
    assert sorted(prazos) == sorted([f"2608.0000{i}" for i in (2, 5, 7)] * 3)
