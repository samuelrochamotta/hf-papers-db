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
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field
from typing import Optional, Sequence

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


@dataclass
class ResultadoClassificacao:
    fora: int = 0
    amplo: int = 0
    estrito: int = 0
    pulados: int = 0
    nao_classificados: int = 0
    fichas: int = 0
    candidatos_taxonomia: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    uso: Uso = field(default_factory=Uso)

    @property
    def classificados(self) -> int:
        return self.fora + self.amplo + self.estrito

    @property
    def aprovados(self) -> int:
        return self.amplo + self.estrito


# ── selecao ─────────────────────────────────────────────────────────────────


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
    )


def selecionar(
    conn: sqlite3.Connection,
    *,
    ids: Optional[Sequence[str]] = None,
    data: Optional[str] = None,
    force: bool = False,
) -> list[ea.PaperEntrada]:
    sql = "SELECT paper_id, titulo, abstract, ai_summary FROM dim_paper"
    cond, params = [], []
    if ids:
        cond.append(f"paper_id IN ({', '.join('?' for _ in ids)})")
        params.extend(ids)
    if data:
        cond.append("data_hf_daily = ?")
        params.append(data)
    if not force:
        cond.append("paper_id NOT IN (SELECT paper_id FROM fato_triagem)")
    if cond:
        sql += " WHERE " + " AND ".join(cond)
    sql += " ORDER BY data_hf_daily DESC, paper_id"
    return [_linha_para_entrada(r, conn) for r in conn.execute(sql, params)]


# ── gravacao ────────────────────────────────────────────────────────────────


def _gravar_triagem(
    conn: sqlite3.Connection,
    *,
    paper_id: str,
    veredito: str,
    regra_fora: Optional[str],
    justificativa: str,
    run_id: str,
    b: Optional[eb.ResultadoB] = None,
    revisao: Optional[int] = None,
) -> None:
    if revisao is None:
        row = conn.execute(
            "SELECT revisao FROM fato_triagem WHERE paper_id = ?", (paper_id,)
        ).fetchone()
        revisao = (row["revisao"] + 1) if row else 1
    teste = (b.teste_portabilidade if b else None) or {}
    db.upsert_triagem(
        conn,
        {
            "paper_id": paper_id,
            "veredito": veredito,
            "regra_fora": regra_fora,
            "justificativa": justificativa,
            "tem_artefato_nomeado": int(b.tem_artefato_nomeado) if b else None,
            "portabilidade_aprovada": int(teste["aprovado"]) if "aprovado" in teste else None,
            "portab_depende_nome": (
                int(teste["depende_do_nome_proprio"]) if "depende_do_nome_proprio" in teste else None
            ),
            "portab_generalidade": (
                int(teste["colapsa_em_generalidade"]) if "colapsa_em_generalidade" in teste else None
            ),
            "decisao_fronteira": int(b.decisao_fronteira) if b else 0,
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
            veredito=b.veredito,
            regra_fora=a.regra_fora if b.veredito == "fora" else None,
            justificativa=b.justificativa_veredito or a.justificativa,
            run_id=run_id,
            b=b,
        )
        if b.aprovado and b.ficha:
            gravar_ficha(conn, paper_id, b.ficha, modelo=cfg.llm.estagio_b.modelo, run_id=run_id)
            res.fichas += 1
        elif not b.aprovado:
            conn.execute("DELETE FROM dim_ficha WHERE paper_id = ?", (paper_id,))

    if b.veredito == "fora":
        res.fora += 1
    elif b.veredito == "amplo":
        res.amplo += 1
    else:
        res.estrito += 1


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


def rodar(
    conn: sqlite3.Connection,
    cliente: ClienteLLM,
    papers: Sequence[ea.PaperEntrada],
    *,
    run_id: str,
    cfg: Optional[Config] = None,
    so_estagio_a: bool = False,
) -> ResultadoClassificacao:
    cfg = cfg or config()
    res = ResultadoClassificacao()
    if not papers:
        return res

    vocab = ea.carregar_vocabulario(conn)
    # papers cujo Estagio B falhou na primeira passada; guardamos `a` (para
    # nao repetir o Estagio A) e `entrada_b` ja montada, de onde tambem sai o
    # `paper_id` - nao ha motivo para carregar o `PaperEntrada` original.
    falhas_b: list[tuple[ea.ResultadoA, ea.PaperEntrada]] = []

    for paper in papers:
        try:
            a = ea.classificar(cliente, paper, vocab, cfg=cfg)
        except ErroLLM as e:
            log.error("estagio A falhou em %s: %s", paper.paper_id, e)
            res.avisos.append(f"estagio_a_falhou:{paper.paper_id}")
            res.pulados += 1
            continue
        res.uso.somar(a.uso)

        with db.transacao(conn):
            taxonomia.aplicar_classificacao(
                conn,
                paper.paper_id,
                area_primaria=a.area_primaria,
                areas_secundarias=a.areas_secundarias,
                topicos_paper=a.topicos,
                cfg=cfg.taxonomia,
            )
            if a.candidato_novo_rotulo:
                c = taxonomia.registrar_candidato(
                    conn,
                    rotulo=a.candidato_novo_rotulo.get("rotulo", ""),
                    tipo=a.candidato_novo_rotulo.get("tipo", "topico"),
                    definicao=a.candidato_novo_rotulo.get("definicao", ""),
                    paper_id=paper.paper_id,
                    cfg=cfg.taxonomia,
                )
                if c.rotulo:
                    res.candidatos_taxonomia.append(c.rotulo)
                if c.aviso:
                    res.avisos.append(c.aviso)

        if not a.candidato:
            with db.transacao(conn):
                _gravar_triagem(
                    conn,
                    paper_id=paper.paper_id,
                    veredito="fora",
                    regra_fora=a.regra_fora,
                    justificativa=a.justificativa,
                    run_id=run_id,
                )
            res.fora += 1
            continue

        if so_estagio_a:
            res.pulados += 1
            continue

        entrada_b = ea.PaperEntrada(
            paper_id=paper.paper_id,
            titulo=paper.titulo,
            abstract=paper.abstract,
            keywords=paper.keywords,
            ai_summary=paper.ai_summary,
            area_primaria=a.area_primaria,
            topicos=a.topicos,
        )
        try:
            b = eb.avaliar(cliente, entrada_b, cfg=cfg)
        except ErroLLM as e:
            # Infraestrutura, nao veredito (issue #1): nada e gravado agora.
            # O paper fica sem linha em `fato_triagem` - pendente - e entra na
            # segunda passada, no fim da varredura deste estagio.
            log.warning("estagio B falhou em %s (1a passada): %s", entrada_b.paper_id, e)
            falhas_b.append((a, entrada_b))
            continue

        res.uso.somar(b.uso)
        _gravar_sucesso_b(
            conn, paper_id=paper.paper_id, a=a, b=b, run_id=run_id, cfg=cfg, res=res
        )

    if falhas_b:
        espera = cfg.llm.retry.backoff_inicial_s * _MULTIPLICADOR_BACKOFF_SEGUNDA_PASSADA
        log.warning(
            "segunda passada do estagio B: %s paper(s), espera de %ss", len(falhas_b), espera
        )
        time.sleep(espera)
        for a, entrada_b in falhas_b:
            try:
                b = eb.avaliar(cliente, entrada_b, cfg=cfg)
            except ErroLLM as e:
                # Falhou de novo mesmo com a folga extra: paper continua
                # pendente (linha nova) ou intacto (linha de `--force`) - o
                # aviso e o unico rastro, para o `doutor` vigiar na proxima
                # rodada se a fila nao se resolver sozinha.
                log.error("estagio B falhou em %s (2a passada): %s", entrada_b.paper_id, e)
                res.avisos.append(f"estagio_b_falhou:{entrada_b.paper_id}")
                res.nao_classificados += 1
                continue

            res.uso.somar(b.uso)
            _gravar_sucesso_b(
                conn, paper_id=entrada_b.paper_id, a=a, b=b, run_id=run_id, cfg=cfg, res=res
            )

    log.info(
        "classificacao: %s fora, %s amplo, %s estrito, %s fichas, %s pendentes, US$ %.4f",
        res.fora, res.amplo, res.estrito, res.fichas, res.nao_classificados, res.uso.custo_usd,
    )
    return res


# ── dry-run ─────────────────────────────────────────────────────────────────


def estimar(
    conn: sqlite3.Connection,
    cliente: ClienteLLM,
    papers: Sequence[ea.PaperEntrada],
    *,
    cfg: Optional[Config] = None,
    fracao_candidatos: float = 0.30,
) -> Estimativa:
    """Estimativa de custo sem chamar modelo.

    A fracao de candidatos vem da calibracao historica (~70% do lote e FORA no
    Estagio A, entao ~30% chega ao Estagio B).
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
