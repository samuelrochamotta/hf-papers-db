"""Estagio 3 - CLASSIFICACAO: Estagio A em todos, Estagio B nos sobreviventes.

Idempotencia: paper que ja tem linha em `fato_triagem` nao volta para a LLM.
Reprocessar exige `--force` ou o comando `reclassificar`, que incrementa
`revisao`.

Falha no Estagio B nao aborta a rodada nem fabrica veredito: infraestrutura
nao e decisao. O paper falho fica sem linha em `fato_triagem` - pendente,
repescado por `selecionar` (sem `force`) na proxima rodada, exatamente como um
paper novo. Ao fim da varredura do estagio, quem falhou e retentado **uma vez**
com um backoff maior que o de `llm.retry` (ver `_MULTIPLICADOR_BACKOFF_SEGUNDA_PASSADA`),
na tentativa de resolver na propria rodada a instabilidade transitoria que e a
totalidade dos casos observados (issue #1: 404 de roteamento, 429, timeout).
Quem passa nessa segunda chance segue o caminho normal de gravacao. Quem falha
de novo gera o aviso `estagio_b_falhou:<paper_id>` e permanece pendente - se o
paper ja tinha linha (`reclassificar --force`), essa linha e mantida intacta,
porque nada e apagado nem sobrescrito no caminho de falha.

Nao ha teto de retentativas entre rodadas: um paper que falhe sempre volta
para a fila do dia seguinte. E o `doutor` que vigia o pendente que atravessou
uma rodada sem se resolver (`aviso`, nao `erro`) - ver `doutor.py`.

Concorrencia (`concorrencia > 1`): o que roda em thread e **so** a chamada ao
OpenRouter. Toda escrita no banco continua na thread principal e na ordem
original dos papers - ver `_varrer_paralelo`. Com `concorrencia == 1` nem
existe thread: o caminho e o sequencial de sempre, letra por letra, que e o da
rodada diaria.
"""

from __future__ import annotations

import sqlite3
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Optional, Sequence, Union

from .. import db, taxonomia
from ..config import Config, config
from ..llm import estagio_a as ea
from ..llm import estagio_b as eb
from ..llm.cliente import ClienteLLM, ErroLLM, Estimativa, Uso, estimar_tokens
from ..log import logger

log = logger("classificacao")

# Multiplicador do backoff da segunda passada sobre `llm.retry.backoff_inicial_s`.
# O retry interno de `ClienteLLM.chamar` ja dobrou a espera a cada tentativa
# (issue #1: 404/429/timeout observados em rajada); esperar mais um multiplo
# antes de retentar no fim do estagio da tempo do rate limit ou do roteamento
# se recuperarem, em vez de bater na mesma janela de instabilidade.
_MULTIPLICADOR_BACKOFF_SEGUNDA_PASSADA = 4

# Teto de chamadas simultaneas ao OpenRouter. Oito porque o modo de falha real
# do provedor e a rajada, nao o volume: a issue #1 registra 404 de roteamento,
# 429 e timeout em sequencia curta, e cada uma dessas custa o retry interno de
# `ClienteLLM.chamar` mais, no Estagio B, uma segunda passada inteira. Acima
# disso o tempo devolvido pelo paralelismo comeca a voltar como retentativa, e
# a unica operacao que precisa de concorrencia - a reclassificacao total - ja
# cai de uma noite para menos de duas horas com 8 (ver o ADR 001). Nada acima
# disso valeria o risco. Valor fora da faixa nao derruba a
# rodada: `normalizar_concorrencia` corta com aviso, porque abortar uma
# varredura de horas por causa de um digito e pior que roda-la mais devagar.
CONCORRENCIA_MAXIMA = 8


def normalizar_concorrencia(valor: int) -> int:
    """Prende o pedido na faixa [1, CONCORRENCIA_MAXIMA], avisando se cortou."""
    n = int(valor)
    if n < 1:
        log.warning("concorrencia %s invalida; usando 1 (sequencial)", valor)
        return 1
    if n > CONCORRENCIA_MAXIMA:
        log.warning(
            "concorrencia %s acima do teto; usando %s", valor, CONCORRENCIA_MAXIMA
        )
        return CONCORRENCIA_MAXIMA
    return n


@dataclass
class ResultadoClassificacao:
    fora: int = 0
    aprovados: int = 0
    pulados: int = 0
    nao_classificados: int = 0
    fichas: int = 0
    # Aprovados por degrau de pre-requisito: vai para `log_execucao`, o unico
    # historico da distribuicao (fato_triagem e sobrescrita a cada rodada).
    por_prerequisito: dict[str, int] = field(default_factory=dict)
    avisos: list[str] = field(default_factory=list)
    uso: Uso = field(default_factory=Uso)

    @property
    def classificados(self) -> int:
        return self.fora + self.aprovados


# ── selecao ─────────────────────────────────────────────────────────────────


def _links_artefato(r: sqlite3.Row) -> list[str]:
    links = []
    if r["github_repo"]:
        links.append(r["github_repo"])
    if r["links_abstract"]:
        links.append("link no abstract")
    return links


def _linha_para_entrada(r: sqlite3.Row, conn: sqlite3.Connection) -> ea.PaperEntrada:
    kws = [
        x["keyword"]
        for x in conn.execute(
            "SELECT keyword FROM ponte_paper_keyword WHERE paper_id = ? ORDER BY keyword",
            (r["paper_id"],),
        )
    ]
    return ea.PaperEntrada(
        paper_id=r["paper_id"],
        titulo=r["titulo"],
        abstract=r["abstract"] or r["ai_summary"] or "",
        keywords=kws,
        ai_summary=r["ai_summary"],
        evidencia_artefato=bool(r["evidencia"]),
        links_artefato=_links_artefato(r),
    )


def selecionar(
    conn: sqlite3.Connection,
    *,
    ids: Optional[Sequence[str]] = None,
    data: Optional[str] = None,
    force: bool = False,
    exceto_run_id: Optional[str] = None,
) -> list[ea.PaperEntrada]:
    # A evidencia de artefato vem da view, e nao de uma copia da regra aqui:
    # `vw_artefato` e a unica fonte (ver db.VIEWS_SQL).
    sql = (
        "SELECT p.paper_id, p.titulo, p.abstract, p.ai_summary, "
        "a.evidencia, a.github_repo, a.links_abstract "
        "FROM dim_paper p JOIN vw_artefato a ON a.paper_id = p.paper_id"
    )
    cond, params = [], []
    if ids:
        cond.append(f"p.paper_id IN ({', '.join('?' for _ in ids)})")
        params.extend(ids)
    if data:
        cond.append("p.data_hf_daily = ?")
        params.append(data)
    if not force:
        cond.append("p.paper_id NOT IN (SELECT paper_id FROM fato_triagem)")
    if exceto_run_id:
        # `reclassificar --retomar`: quem ja tem triagem desta rodada fica.
        cond.append("p.paper_id NOT IN (SELECT paper_id FROM fato_triagem WHERE run_id = ?)")
        params.append(exceto_run_id)
    if cond:
        sql += " WHERE " + " AND ".join(cond)
    sql += " ORDER BY p.data_hf_daily DESC, p.paper_id"
    return [_linha_para_entrada(r, conn) for r in conn.execute(sql, params)]


# ── gravacao ────────────────────────────────────────────────────────────────


def _gravar_triagem(
    conn: sqlite3.Connection,
    *,
    paper_id: str,
    regra_fora: Optional[str],
    justificativa: str,
    run_id: str,
    b: Optional[eb.ResultadoB] = None,
    revisao: Optional[int] = None,
) -> None:
    """Grava a linha do paper. `fora` vem do Estagio A (sem `b`) ou do B; o
    aprovado so vem do B, que e quem atribui natureza e pre-requisito."""
    if revisao is None:
        row = conn.execute(
            "SELECT revisao FROM fato_triagem WHERE paper_id = ?", (paper_id,)
        ).fetchone()
        revisao = (row["revisao"] + 1) if row else 1
    aprovado = b is not None and b.aprovado
    db.upsert_triagem(
        conn,
        {
            "paper_id": paper_id,
            "veredito": "aprovado" if aprovado else "fora",
            "regra_fora": None if aprovado else regra_fora,
            "justificativa": justificativa,
            "natureza": b.natureza if aprovado else None,
            "prerequisito": b.prerequisito if aprovado else None,
            "pratica_contradita": b.pratica_contradita if aprovado else None,
            "falta_o_como": b.falta_o_como if aprovado else None,
            "artefato_status": b.artefato_status if aprovado else None,
            "classificado_em": db.agora(),
            "run_id": run_id,
            "revisao": revisao,
        },
    )


def _gravar_sucesso_b(
    conn: sqlite3.Connection,
    *,
    paper_id: str,
    a: ea.ResultadoA,
    b: eb.ResultadoB,
    run_id: str,
    cfg: Config,
    res: ResultadoClassificacao,
) -> None:
    """Caminho normal de gravacao do Estagio B: usado na varredura principal e,
    identico, para quem passa na segunda passada apos falhar na primeira."""
    with db.transacao(conn):
        _gravar_triagem(
            conn,
            paper_id=paper_id,
            # O Estagio A deixou passar (`candidato`, sem regra); se o B
            # descarta, a regra e a dele - a mesma lista, como rede de seguranca.
            regra_fora=b.regra_fora,
            justificativa=b.justificativa or a.justificativa,
            run_id=run_id,
            b=b,
        )
        if b.aprovado and b.ficha:
            gravar_ficha(conn, paper_id, b.ficha, modelo=cfg.llm.estagio_b.modelo, run_id=run_id)
            res.fichas += 1
        elif not b.aprovado:
            conn.execute("DELETE FROM dim_ficha WHERE paper_id = ?", (paper_id,))

    # Avisos de coerencia nao tornam a rodada parcial: a classificacao foi
    # gravada; o aviso so aponta a combinacao suspeita.
    res.avisos.extend(f"{aviso}:{paper_id}" for aviso in b.avisos)

    if b.aprovado:
        res.aprovados += 1
        degrau = b.prerequisito or ""
        res.por_prerequisito[degrau] = res.por_prerequisito.get(degrau, 0) + 1
    else:
        res.fora += 1


def gravar_ficha(
    conn: sqlite3.Connection, paper_id: str, ficha: eb.Ficha, *, modelo: str, run_id: str
) -> None:
    db.upsert_ficha(
        conn,
        {
            "paper_id": paper_id,
            "achado": ficha.achado,
            "padrao_nome": ficha.padrao_nome,
            "padrao_mecanismo": ficha.padrao_mecanismo,
            "implicacao_pratica": ficha.implicacao_pratica,
            "exemplo_concreto": ficha.exemplo_concreto,
            "ressalva": ficha.ressalva,
            "gerada_em": db.agora(),
            "modelo_usado": modelo,
            "run_id": run_id,
        },
    )


# ── estagio ─────────────────────────────────────────────────────────────────


def _entrada_b(paper: ea.PaperEntrada, a: ea.ResultadoA) -> ea.PaperEntrada:
    """A entrada do Estagio B: o paper mais o que o Estagio A decidiu. Funcao
    pura - por isso a thread trabalhadora pode monta-la sozinha."""
    return ea.PaperEntrada(
        paper_id=paper.paper_id,
        titulo=paper.titulo,
        abstract=paper.abstract,
        keywords=paper.keywords,
        ai_summary=paper.ai_summary,
        area_primaria=a.area_primaria,
        vertentes=a.vertentes,
        evidencia_artefato=paper.evidencia_artefato,
        links_artefato=paper.links_artefato,
    )


def _aplicar_estagio_a(
    conn: sqlite3.Connection,
    paper: ea.PaperEntrada,
    a: ea.ResultadoA,
    *,
    run_id: str,
    so_estagio_a: bool,
    res: ResultadoClassificacao,
) -> bool:
    """Grava o que o Estagio A decidiu; devolve se o paper segue para o B.

    Sai do laco porque as duas varreduras (sequencial e paralela) precisam
    gravar exatamente a mesma coisa, na mesma ordem: e o que faz uma rodada com
    `concorrencia=4` terminar com o banco identico ao de `concorrencia=1`. **So
    a thread principal chama.**

    Uma chamada so para toda a taxonomia do paper, inclusive o nao-encaixe: a
    classificacao nao promove rotulo nenhum, e por isso nao ha aqui nem quorum
    a acumular nem vocabulario a congelar - o que existia disso saiu com
    `tax_candidato`.
    """
    with db.transacao(conn):
        taxonomia.aplicar_classificacao(
            conn,
            paper.paper_id,
            area_primaria=a.area_primaria,
            subarea_primaria=a.subarea_primaria,
            area_secundaria=a.area_secundaria,
            subarea_secundaria=a.subarea_secundaria,
            vertentes_paper=a.vertentes,
            nao_coube=a.nao_coube,
        )

    if not a.candidato:
        with db.transacao(conn):
            _gravar_triagem(
                conn,
                paper_id=paper.paper_id,
                regra_fora=a.regra_fora,
                justificativa=a.justificativa,
                run_id=run_id,
            )
            # `--force` sobre um paper que era aprovado: a ficha antiga nao pode
            # sobreviver ao descarte.
            conn.execute("DELETE FROM dim_ficha WHERE paper_id = ?", (paper.paper_id,))
        res.fora += 1
        return False

    if so_estagio_a:
        res.pulados += 1
        return False

    return True


def _falhou_estagio_a(res: ResultadoClassificacao, paper_id: str, e: Exception) -> None:
    log.error("estagio A falhou em %s: %s", paper_id, e)
    res.avisos.append(f"estagio_a_falhou:{paper_id}")
    res.pulados += 1


def _adiar_estagio_b(
    falhas_b: list[tuple[ea.ResultadoA, ea.PaperEntrada]],
    a: ea.ResultadoA,
    entrada_b: ea.PaperEntrada,
    e: Exception,
) -> None:
    """Infraestrutura, nao veredito (issue #1): nada e gravado agora. O paper
    fica sem linha em `fato_triagem` - pendente - e entra na segunda passada,
    no fim da varredura deste estagio."""
    log.warning("estagio B falhou em %s (1a passada): %s", entrada_b.paper_id, e)
    falhas_b.append((a, entrada_b))


def _varrer_sequencial(
    conn: sqlite3.Connection,
    cliente: ClienteLLM,
    papers: Sequence[ea.PaperEntrada],
    vocab: ea.Vocabulario,
    *,
    run_id: str,
    cfg: Config,
    so_estagio_a: bool,
    res: ResultadoClassificacao,
    falhas_b: list[tuple[ea.ResultadoA, ea.PaperEntrada]],
) -> None:
    """O caminho de sempre, e o da rodada diaria: um paper por vez, A e B
    intercalados com as gravacoes dele. Nenhuma thread, nenhum buffer - e o que
    garante que ligar a concorrencia nao mexeu em quem nao a pediu."""
    for paper in papers:
        try:
            a = ea.classificar(cliente, paper, vocab, cfg=cfg)
        except ErroLLM as e:
            _falhou_estagio_a(res, paper.paper_id, e)
            continue
        res.uso.somar(a.uso)

        if not _aplicar_estagio_a(
            conn, paper, a, run_id=run_id, so_estagio_a=so_estagio_a, res=res
        ):
            continue

        entrada_b = _entrada_b(paper, a)
        try:
            b = eb.avaliar(cliente, entrada_b, cfg=cfg)
        except ErroLLM as e:
            _adiar_estagio_b(falhas_b, a, entrada_b, e)
            continue

        res.uso.somar(b.uso)
        _gravar_sucesso_b(
            conn, paper_id=paper.paper_id, a=a, b=b, run_id=run_id, cfg=cfg, res=res
        )


# Devolvido por `_tarefa_paper`: o Estagio A, a entrada do B (None quando o
# paper nao chega la) e o resultado do B - ou o `ErroLLM` dele **como valor**,
# porque quem decide o que fazer com a falha e a thread principal, na ordem.
_Tarefa = tuple[ea.ResultadoA, Optional[ea.PaperEntrada], Union[eb.ResultadoB, ErroLLM, None]]


def _tarefa_paper(
    cliente: ClienteLLM,
    paper: ea.PaperEntrada,
    vocab: ea.Vocabulario,
    cfg: Config,
    so_estagio_a: bool,
) -> _Tarefa:
    """O que roda na thread trabalhadora: as chamadas ao OpenRouter, e nada
    mais. Nao toca o banco - nem para gravar `log_llm`, que o cliente esta
    empilhando em buffer (ver `ClienteLLM.registros_adiados`).

    `ErroLLM` do Estagio A sobe pelo `Future`, porque sem `a` nao ha tupla a
    devolver; o do Estagio B volta como valor, junto do `a` que ja custou uma
    chamada e nao pode ser jogado fora.
    """
    a = ea.classificar(cliente, paper, vocab, cfg=cfg)
    if not a.candidato or so_estagio_a:
        return a, None, None
    entrada_b = _entrada_b(paper, a)
    try:
        return a, entrada_b, eb.avaliar(cliente, entrada_b, cfg=cfg)
    except ErroLLM as e:
        return a, entrada_b, e


def _varrer_paralelo(
    conn: sqlite3.Connection,
    cliente: ClienteLLM,
    papers: Sequence[ea.PaperEntrada],
    vocab: ea.Vocabulario,
    *,
    run_id: str,
    cfg: Config,
    so_estagio_a: bool,
    concorrencia: int,
    res: ResultadoClassificacao,
    falhas_b: list[tuple[ea.ResultadoA, ea.PaperEntrada]],
) -> None:
    """Mesma varredura, com ate `concorrencia` chamadas no ar.

    O paralelismo e do paper inteiro (A e depois B, na mesma thread), e nao de
    um estagio por vez: o Estagio B e o caro (~127 s contra ~65 s) e so ~30% do
    lote chega la, entao paralelizar A e B em lotes separados deixaria a maior
    parte do tempo com quase todas as threads ociosas.

    **A ordem e a mesma de `_varrer_sequencial`** porque os `Future` sao
    drenados na ordem em que foram submetidos - a de `papers` - e toda gravacao
    acontece aqui, na thread principal. Isso nao e enfeite: `revisao` de
    `fato_triagem` e lida-e-incrementada, e `log_llm` tem `id` AUTOINCREMENT,
    entao drenar por ordem de chegada daria um banco diferente a cada rodada.
    A taxonomia deixou de depender disso quando a promocao saiu da
    classificacao - o nao-encaixe e por paper e nao acumula quorum -, mas a
    ordem continua sendo contrato pelos outros dois. `log_llm` e drenado paper
    a paper (ver `drenar_registros`).
    """
    with cliente.registros_adiados():
        pool = ThreadPoolExecutor(max_workers=concorrencia, thread_name_prefix="estagio3")
        try:
            futuros: list[Future[_Tarefa]] = [
                pool.submit(_tarefa_paper, cliente, p, vocab, cfg, so_estagio_a)
                for p in papers
            ]
            for paper, futuro in zip(papers, futuros):
                try:
                    a, entrada_b, b = futuro.result()
                except ErroLLM as e:
                    _falhou_estagio_a(res, paper.paper_id, e)
                    continue
                finally:
                    cliente.drenar_registros(paper.paper_id)

                res.uso.somar(a.uso)
                if not _aplicar_estagio_a(
                    conn, paper, a, run_id=run_id, so_estagio_a=so_estagio_a, res=res
                ):
                    continue
                assert entrada_b is not None  # `_aplicar_estagio_a` so aprova quem tem B
                if isinstance(b, ErroLLM):
                    _adiar_estagio_b(falhas_b, a, entrada_b, b)
                    continue

                res.uso.somar(b.uso)
                _gravar_sucesso_b(
                    conn, paper_id=paper.paper_id, a=a, b=b, run_id=run_id, cfg=cfg, res=res
                )
        finally:
            # `cancel_futures` porque, se a varredura estourou no meio, esperar
            # as centenas de tarefas ainda na fila custaria as horas que a
            # concorrencia veio economizar. `wait=True` porque as que ja estao
            # no ar (no maximo `concorrencia`, cada uma limitada por
            # `llm.timeout_s`) precisam terminar antes de o buffer fechar: com
            # ele fechado, `_registrar` gravaria no banco a partir de uma thread
            # que nao e a dona da conexao.
            #
            # Consequencia para quem opera: um Ctrl+C no meio de uma rodada
            # longa nao devolve o terminal na hora - ele espera as chamadas em
            # voo, no pior caso `llm.retry.tentativas` x `llm.prazo_total_s`
            # mais o backoff. Com o config vigente (3 x 90 s + 2 s + 4 s) sao
            # ~4,6 min por estagio, e ~9,2 min se o paper ja estiver no Estagio
            # B - a thread faz A e depois B, entao o pior caso e o dobro.
            #
            # Quem manda no numero e `prazo_total_s`, e nao `timeout_s`: o
            # prazo e o teto de ponta a ponta por chamada. Com
            # `prazo_total_s: 0` (teto desligado) volta a valer `timeout_s`, e
            # a espera dobra para ~9,1 min por estagio, ~18 min no Estagio B.
            #
            # E inerente ao `concurrent.futures`; matar o processo no lugar de
            # esperar arrisca interromper uma gravacao. O help do
            # `--concorrencia` avisa.
            pool.shutdown(wait=True, cancel_futures=True)


def _segunda_passada(
    conn: sqlite3.Connection,
    cliente: ClienteLLM,
    falhas_b: Sequence[tuple[ea.ResultadoA, ea.PaperEntrada]],
    *,
    run_id: str,
    cfg: Config,
    concorrencia: int,
    res: ResultadoClassificacao,
) -> None:
    """A segunda chance do Estagio B, com o backoff maior do cabecalho do
    modulo. Uma espera para o lote inteiro, nao uma por paper - e depois dela o
    lote e retentado com a mesma concorrencia da varredura."""
    espera = cfg.llm.retry.backoff_inicial_s * _MULTIPLICADOR_BACKOFF_SEGUNDA_PASSADA
    log.warning(
        "segunda passada do estagio B: %s paper(s), espera de %ss", len(falhas_b), espera
    )
    time.sleep(espera)

    if concorrencia == 1:
        for a, entrada_b in falhas_b:
            try:
                b = eb.avaliar(cliente, entrada_b, cfg=cfg)
            except ErroLLM as e:
                _falhou_de_vez_estagio_b(res, entrada_b.paper_id, e)
                continue
            res.uso.somar(b.uso)
            _gravar_sucesso_b(
                conn, paper_id=entrada_b.paper_id, a=a, b=b, run_id=run_id, cfg=cfg, res=res
            )
        return

    with cliente.registros_adiados():
        pool = ThreadPoolExecutor(max_workers=concorrencia, thread_name_prefix="estagio3b")
        try:
            futuros = [
                pool.submit(eb.avaliar, cliente, entrada_b, cfg=cfg)
                for _, entrada_b in falhas_b
            ]
            for (a, entrada_b), futuro in zip(falhas_b, futuros):
                try:
                    b = futuro.result()
                except ErroLLM as e:
                    _falhou_de_vez_estagio_b(res, entrada_b.paper_id, e)
                    continue
                finally:
                    cliente.drenar_registros(entrada_b.paper_id)

                res.uso.somar(b.uso)
                _gravar_sucesso_b(
                    conn, paper_id=entrada_b.paper_id, a=a, b=b, run_id=run_id, cfg=cfg, res=res
                )
        finally:
            pool.shutdown(wait=True, cancel_futures=True)


def _falhou_de_vez_estagio_b(
    res: ResultadoClassificacao, paper_id: str, e: Exception
) -> None:
    """Falhou de novo mesmo com a folga extra: paper continua pendente (linha
    nova) ou intacto (linha de `--force`) - o aviso e o unico rastro, para o
    `doutor` vigiar na proxima rodada se a fila nao se resolver sozinha."""
    log.error("estagio B falhou em %s (2a passada): %s", paper_id, e)
    res.avisos.append(f"estagio_b_falhou:{paper_id}")
    res.nao_classificados += 1


def rodar(
    conn: sqlite3.Connection,
    cliente: ClienteLLM,
    papers: Sequence[ea.PaperEntrada],
    *,
    run_id: str,
    cfg: Optional[Config] = None,
    so_estagio_a: bool = False,
    concorrencia: int = 1,
    res: Optional[ResultadoClassificacao] = None,
) -> ResultadoClassificacao:
    """`concorrencia` e quantas chamadas ao OpenRouter podem estar no ar. Com 1 -
    o padrao, e o que a rodada diaria usa - o caminho e o sequencial de sempre.
    Acima disso, so o I/O e paralelo; ver `_varrer_paralelo`.

    `res` deixa quem chama **ser dono do acumulador**. Sem isso as contagens so
    existiriam no retorno, e uma varredura que estourasse no meio - depois de
    ja ter gravado centenas de triagens - devolveria zeros para `log_execucao`,
    fazendo a rodada parecer que nao classificou ninguem (e o `doutor`
    recusa-la como corte de pendencias). Passando o objeto, o que foi contado
    ate o estouro fica com quem chamou, porque e a mesma referencia.
    """
    cfg = cfg or config()
    res = res if res is not None else ResultadoClassificacao()
    if not papers:
        return res

    concorrencia = normalizar_concorrencia(concorrencia)
    vocab = ea.carregar_vocabulario(conn)
    # papers cujo Estagio B falhou na primeira passada; guardamos `a` (para
    # nao repetir o Estagio A) e `entrada_b` ja montada, de onde tambem sai o
    # `paper_id` - nao ha motivo para carregar o `PaperEntrada` original.
    falhas_b: list[tuple[ea.ResultadoA, ea.PaperEntrada]] = []

    if concorrencia == 1:
        _varrer_sequencial(
            conn, cliente, papers, vocab, run_id=run_id, cfg=cfg,
            so_estagio_a=so_estagio_a,
            res=res, falhas_b=falhas_b,
        )
    else:
        _varrer_paralelo(
            conn, cliente, papers, vocab, run_id=run_id, cfg=cfg,
            so_estagio_a=so_estagio_a,
            concorrencia=concorrencia, res=res, falhas_b=falhas_b,
        )

    if falhas_b:
        _segunda_passada(
            conn, cliente, falhas_b, run_id=run_id, cfg=cfg,
            concorrencia=concorrencia, res=res,
        )

    log.info(
        "classificacao: %s fora, %s aprovados %s, %s fichas, %s pendentes, US$ %.4f",
        res.fora, res.aprovados, res.por_prerequisito, res.fichas, res.nao_classificados,
        res.uso.custo_usd,
    )
    return res


# ── dry-run ─────────────────────────────────────────────────────────────────


def estimar(
    conn: sqlite3.Connection,
    cliente: ClienteLLM,
    papers: Sequence[ea.PaperEntrada],
    *,
    cfg: Optional[Config] = None,
    fracao_candidatos: float = 0.70,
) -> Estimativa:
    """Estimativa de custo sem chamar modelo.

    A fracao de candidatos e a do escopo do ADR 004: sem as regras de treino e
    de relatorio tecnico, ~70% do lote passa pelo Estagio A (era ~30%).
    Recalibrar com a distribuicao da reclassificacao total.
    """
    cfg = cfg or config()
    est = Estimativa()
    if not papers:
        return est

    vocab = ea.carregar_vocabulario(conn)
    amostra = papers[: min(len(papers), 5)]
    tok_a = sum(estimar_tokens(ea.montar_prompt(p, vocab, cfg)) for p in amostra) // len(amostra)
    tok_b = sum(estimar_tokens(eb.montar_prompt(p, cfg)) for p in amostra) // len(amostra)

    est.acrescentar(
        "estagio_a",
        cfg.llm.estagio_a.modelo,
        len(papers),
        tok_a,
        cfg.llm.estagio_a.max_tokens // 2,
        cliente.preco(cfg.llm.estagio_a.modelo),
    )
    est.acrescentar(
        "estagio_b",
        cfg.llm.estagio_b.modelo,
        max(1, round(len(papers) * fracao_candidatos)),
        tok_b,
        cfg.llm.estagio_b.max_tokens // 2,
        cliente.preco(cfg.llm.estagio_b.modelo),
    )
    return est
