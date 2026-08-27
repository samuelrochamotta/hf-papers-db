"""Backfill da base historica a partir de `seed/`.

Roda uma vez e e idempotente: a segunda execucao nao altera contagem nem gera
chamada de LLM.

A lista de trabalho e a **uniao de tres fontes** - `hf-digest-estado.json`,
`taxonomia.json > classificacoes` e os ids das fichas dos digests. Usar so o
estado produz 241 papers e 82 fichas, e esta errado: `2608.14577` tem ficha e
classificacao mas sumiu do estado quando a rodada de 18/08 gravou o digest. O
estado e registro historico e fica verbatim; a uniao o recupera.

Ordem real de execucao (difere da ordem narrativa do PROMPT por causa das FKs:
ponte e triagem exigem a linha de `dim_paper` ja existente):

    vocabulario -> lista de trabalho -> hidratacao -> triagem
    -> classificacoes curadas -> Estagio A nos sem classificacao
    -> Estagio B nos aprovados -> relatorio de validacao
"""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence

from . import db, digests as mod_digests, taxonomia
from .config import Config, config
from .estagios import classificacao
from .fontes.hf_client import ClienteHF, ErroHF
from .fontes.modelos import id_base, paper_para_dim, paper_para_metrica
from .llm import estagio_a as ea
from .llm import estagio_b as eb
from .llm.cliente import ClienteLLM, ErroLLM, Uso
from .log import logger

log = logger("backfill")

RUN_ID = "backfill"


@dataclass
class ResultadoBackfill:
    papers: int = 0
    hidratados: int = 0
    falhas_hidratacao: list[str] = field(default_factory=list)
    triagens: int = 0
    vereditos: dict[str, int] = field(default_factory=dict)
    classificacoes_curadas: int = 0
    estagio_a: int = 0
    fichas_geradas: int = 0
    fichas_existentes: int = 0
    uso: Uso = field(default_factory=Uso)
    avisos: list[str] = field(default_factory=list)
    relatorio: Optional[Path] = None


@dataclass
class ItemTrabalho:
    paper_id: str
    veredito: Optional[str] = None
    upvotes_dia1: Optional[int] = None
    data_publicado: Optional[dt.date] = None
    titulo: Optional[str] = None
    fontes: set[str] = field(default_factory=set)


# ── lista de trabalho ───────────────────────────────────────────────────────


def montar_lista(seed: Path) -> dict[str, ItemTrabalho]:
    estado = json.loads((seed / "hf-digest-estado.json").read_text(encoding="utf-8"))
    tax = json.loads((seed / "taxonomia.json").read_text(encoding="utf-8"))
    digests = mod_digests.carregar_digests(seed / "digests")
    fichas = mod_digests.fichas_por_id(digests)

    itens: dict[str, ItemTrabalho] = {}

    def item(pid: str) -> ItemTrabalho:
        pid = id_base(pid)
        return itens.setdefault(pid, ItemTrabalho(paper_id=pid))

    for pid, dados in estado.get("ids_vistos", {}).items():
        it = item(pid)
        it.veredito = dados.get("veredito")
        it.upvotes_dia1 = dados.get("upvotes_dia1")
        pub = dados.get("publicado")
        it.data_publicado = dt.date.fromisoformat(pub) if pub else None
        it.fontes.add("estado")

    for pid in tax.get("classificacoes", {}):
        item(pid).fontes.add("taxonomia")

    for pid, f in fichas.items():
        it = item(pid)
        it.fontes.add("digest")
        it.titulo = it.titulo or f.titulo
        if it.upvotes_dia1 is None:
            it.upvotes_dia1 = f.upvotes_dia1
        if it.data_publicado is None:
            it.data_publicado = f.data
        # o veredito de um id que so existe no digest sai da secao onde a ficha
        # esta: `## 3.` => estrito, `## 4.` => amplo
        if it.veredito is None:
            it.veredito = f.veredito

    return itens


# ── hidratacao ──────────────────────────────────────────────────────────────


def _linha_minima(it: ItemTrabalho) -> dict[str, Any]:
    """Fallback quando o HF nao devolve o paper: a linha existe mesmo assim,
    senao as FKs de triagem e ponte impedem o resto do backfill."""
    return {
        "paper_id": it.paper_id,
        "titulo": it.titulo or f"(sem titulo) {it.paper_id}",
        "data_arxiv": it.data_publicado,
        "data_hf_daily": it.data_publicado,
        "url_arxiv": f"https://arxiv.org/abs/{it.paper_id}",
        "url_hf": f"https://huggingface.co/papers/{it.paper_id}",
        "primeiro_visto_em": db.agora(),
    }


def hidratar(
    conn: sqlite3.Connection,
    cliente: ClienteHF,
    itens: dict[str, ItemTrabalho],
    res: ResultadoBackfill,
    *,
    hoje: Optional[dt.date] = None,
    force: bool = False,
) -> None:
    hoje = hoje or db.hoje()
    ja = {
        r["paper_id"]
        for r in conn.execute("SELECT paper_id FROM dim_paper WHERE enriquecido_em IS NOT NULL")
    }
    agora = db.agora()

    for pid, it in itens.items():
        if pid in ja and not force:
            continue
        try:
            paper = cliente.paper(pid)
        except ErroHF as e:
            log.warning("hidratacao falhou em %s: %s", pid, e)
            res.falhas_hidratacao.append(pid)
            with db.transacao(conn):
                db.upsert_paper(conn, _linha_minima(it))
            continue

        with db.transacao(conn):
            db.upsert_paper(
                conn,
                paper_para_dim(paper, primeiro_visto_em=agora, enriquecido_em=agora),
            )
            # snapshot de hoje, com as metricas atuais
            db.upsert_metrica(
                conn, paper_para_metrica(paper, data_snapshot=hoje, origem="backfill")
            )
            # e um snapshot historico com o upvote do dia 1: a serie comeca com
            # dois pontos reais em vez de um
            data_dia1 = paper.submittedOnDailyAt or it.data_publicado
            if data_dia1 and it.upvotes_dia1 is not None:
                db.upsert_metrica(
                    conn,
                    {
                        "paper_id": paper.paper_id,
                        "data_snapshot": data_dia1,
                        "upvotes": it.upvotes_dia1,
                        "origem": "backfill",
                    },
                )
            for ordem, autor in enumerate(paper.authors, start=1):
                if autor.name:
                    db.upsert(
                        conn,
                        "ponte_paper_autor",
                        {
                            "paper_id": paper.paper_id,
                            "ordem": ordem,
                            "autor": autor.name,
                            "hf_user": autor.hf_user,
                            "verificado": int(autor.verificado),
                        },
                        chave=["paper_id", "ordem"],
                    )
            for kw in paper.ai_keywords:
                if kw:
                    db.inserir_ignorando(
                        conn,
                        "ponte_paper_keyword",
                        {"paper_id": paper.paper_id, "keyword": kw},
                    )
        res.hidratados += 1

    if res.falhas_hidratacao:
        res.avisos.append(f"hidratacao_falhou:{len(res.falhas_hidratacao)}")


# ── triagem historica ───────────────────────────────────────────────────────


def importar_triagem(
    conn: sqlite3.Connection, itens: dict[str, ItemTrabalho], res: ResultadoBackfill
) -> None:
    """Veredito historico -> `fato_triagem`, com `revisao = 0`.

    Os campos de portabilidade ficam NULL: nao foram registrados na epoca.
    `INSERT OR IGNORE` protege uma reclassificacao posterior de ser sobrescrita
    por um segundo backfill.
    """
    agora = db.agora()
    with db.transacao(conn):
        for pid, it in itens.items():
            if not it.veredito:
                continue
            db.inserir_ignorando(
                conn,
                "fato_triagem",
                {
                    "paper_id": pid,
                    "veredito": it.veredito,
                    "regra_fora": None,
                    "justificativa": "Importado do historico (" + ", ".join(sorted(it.fontes)) + ")",
                    "decisao_fronteira": 0,
                    "classificado_em": agora,
                    "run_id": RUN_ID,
                    "revisao": 0,
                },
            )
    res.triagens = db.contar(conn, "fato_triagem")
    res.vereditos = {
        r["veredito"]: r["n"]
        for r in conn.execute(
            "SELECT veredito, COUNT(*) AS n FROM fato_triagem GROUP BY veredito"
        )
    }


# ── classificacoes curadas ──────────────────────────────────────────────────


def importar_classificacoes(
    conn: sqlite3.Connection, seed: Path, res: ResultadoBackfill, cfg: Config
) -> None:
    """As 83 classificacoes a mao sao autoritativas - nao sao regeneradas."""
    tax = json.loads((seed / "taxonomia.json").read_text(encoding="utf-8"))
    existentes = {r["paper_id"] for r in conn.execute("SELECT paper_id FROM dim_paper")}
    n = 0
    with db.transacao(conn):
        for pid, c in tax.get("classificacoes", {}).items():
            pid = id_base(pid)
            if pid not in existentes:
                continue
            taxonomia.aplicar_classificacao(
                conn,
                pid,
                area_primaria=c.get("area", ""),
                areas_secundarias=c.get("areas_secundarias", []),
                topicos_paper=c.get("topicos", []),
                cfg=cfg.taxonomia,
            )
            n += 1
    res.classificacoes_curadas = n


# ── LLM ─────────────────────────────────────────────────────────────────────


def _entradas(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[ea.PaperEntrada]:
    linhas = conn.execute(sql, params).fetchall()
    entradas = []
    for r in linhas:
        kws = [
            x["keyword"]
            for x in conn.execute(
                "SELECT keyword FROM ponte_paper_keyword WHERE paper_id = ?", (r["paper_id"],)
            )
        ]
        entradas.append(
            ea.PaperEntrada(
                paper_id=r["paper_id"],
                titulo=r["titulo"],
                abstract=r["abstract"] or r["ai_summary"] or "",
                keywords=kws,
                ai_summary=r["ai_summary"],
            )
        )
    return entradas


def classificar_sem_taxonomia(
    conn: sqlite3.Connection,
    cliente: ClienteLLM,
    res: ResultadoBackfill,
    cfg: Config,
    ids: Sequence[str],
) -> None:
    """Estagio A nos papers sem classificacao curada - em geral os FORA.

    So para ganhar area e topico. Estes nao passam pelo Estagio B: o veredito
    historico ja esta gravado e nao e reaberto aqui.

    Restrito aos ids da lista de trabalho: sem isso o backfill classificaria de
    quebra os papers do dia corrente, que sao trabalho do `run`.
    """
    if not ids:
        return
    marca = ", ".join("?" for _ in ids)
    pendentes = _entradas(
        conn,
        "SELECT paper_id, titulo, abstract, ai_summary FROM dim_paper "
        f"WHERE paper_id IN ({marca}) "
        "  AND paper_id NOT IN (SELECT paper_id FROM ponte_paper_area) "
        "ORDER BY paper_id",
        tuple(ids),
    )
    if not pendentes:
        return
    vocab = ea.carregar_vocabulario(conn)
    log.info("estagio A em %s papers sem classificacao", len(pendentes))

    for paper in pendentes:
        try:
            a = ea.classificar(cliente, paper, vocab, cfg=cfg)
        except ErroLLM as e:
            log.error("estagio A falhou em %s: %s", paper.paper_id, e)
            res.avisos.append(f"estagio_a_falhou:{paper.paper_id}")
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
                if c.aviso:
                    res.avisos.append(c.aviso)
        res.estagio_a += 1


def _arquivo_vereditos(cfg: Config) -> Path:
    return cfg.dir_relatorios / "vereditos_estagio_b.json"


def registrar_veredito_regenerado(cfg: Config, paper_id: str, veredito: str) -> None:
    """Guarda o veredito que o Estagio B devolveu, sem tocar em `fato_triagem`.

    O veredito historico e autoritativo no backfill - ele nao e reaberto. Mas
    sem guardar o veredito novo em algum lugar, o relatorio de validacao
    compararia o historico contra ele mesmo e daria 100% de concordancia sempre.
    """
    caminho = _arquivo_vereditos(cfg)
    cfg.dir_relatorios.mkdir(parents=True, exist_ok=True)
    dados = {}
    if caminho.exists():
        try:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            dados = {}
    dados[paper_id] = veredito
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def vereditos_regenerados(cfg: Config) -> dict[str, str]:
    caminho = _arquivo_vereditos(cfg)
    if not caminho.exists():
        return {}
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def gerar_fichas(
    conn: sqlite3.Connection,
    cliente: ClienteLLM,
    res: ResultadoBackfill,
    cfg: Config,
    ids: Sequence[str],
) -> None:
    """Estagio B nos aprovados sem ficha. Unico gasto significativo do backfill.

    Restrito aos ids da lista de trabalho, pelo mesmo motivo do Estagio A: ficha
    de paper do dia corrente e trabalho do `run`, nao do backfill.
    """
    if not ids:
        return
    marca = ", ".join("?" for _ in ids)
    pendentes = _entradas(
        conn,
        "SELECT p.paper_id, p.titulo, p.abstract, p.ai_summary FROM dim_paper p "
        "JOIN fato_triagem t ON t.paper_id = p.paper_id "
        f"WHERE p.paper_id IN ({marca}) "
        "  AND t.veredito IN ('amplo','estrito') "
        "  AND p.paper_id NOT IN (SELECT paper_id FROM dim_ficha) "
        "ORDER BY p.paper_id",
        tuple(ids),
    )
    if not pendentes:
        return
    log.info("estagio B em %s aprovados sem ficha", len(pendentes))

    for paper in pendentes:
        area = conn.execute(
            "SELECT area FROM ponte_paper_area WHERE paper_id = ? AND is_primaria = 1",
            (paper.paper_id,),
        ).fetchone()
        topicos = [
            r["topico"]
            for r in conn.execute(
                "SELECT topico FROM ponte_paper_topico WHERE paper_id = ?", (paper.paper_id,)
            )
        ]
        paper.area_primaria = area["area"] if area else None
        paper.topicos = topicos
        try:
            b = eb.avaliar(cliente, paper, cfg=cfg)
        except ErroLLM as e:
            log.error("estagio B falhou em %s: %s", paper.paper_id, e)
            res.avisos.append(f"estagio_b_falhou:{paper.paper_id}")
            continue
        res.uso.somar(b.uso)
        registrar_veredito_regenerado(cfg, paper.paper_id, b.veredito)
        if not b.ficha:
            # o veredito historico manda no backfill; a ficha ausente vira aviso
            res.avisos.append(f"ficha_ausente:{paper.paper_id}:{b.veredito}")
            continue
        with db.transacao(conn):
            classificacao.gravar_ficha(
                conn, paper.paper_id, b.ficha, modelo=cfg.llm.estagio_b.modelo, run_id=RUN_ID
            )
        res.fichas_geradas += 1


# ── validacao contra o historico ────────────────────────────────────────────


def relatorio_validacao(
    conn: sqlite3.Connection, seed: Path, cfg: Config, res: ResultadoBackfill
) -> Path:
    """Compara as fichas regeneradas com as 83 do pipeline antigo.

    Nao corrige nada: e o instrumento para julgar se o prompt novo reproduz a
    qualidade do antigo. Divergencia grande aponta o prompt do Estagio B, nao as
    fichas antigas.
    """
    historicas = mod_digests.fichas_por_id(mod_digests.carregar_digests(seed / "digests"))
    novos_vereditos = vereditos_regenerados(cfg)
    linhas_md: list[str] = []
    iguais_veredito = divergentes_veredito = 0
    iguais_padrao = divergentes_padrao = 0
    nomes_iguais = 0
    sem_regenerada = 0
    reprovados_agora = 0

    detalhes: list[str] = []
    for pid, h in sorted(historicas.items()):
        veredito_novo = novos_vereditos.get(pid)
        if veredito_novo is None:
            sem_regenerada += 1
            detalhes.append(f"| {pid} | {h.veredito} | (nao regenerada) | — | — |")
            continue

        # 'aprovado' e o registro parcial de uma ficha gerada antes de o veredito
        # passar a ser guardado: sabe-se que passou, nao se foi amplo ou estrito.
        concorda = veredito_novo == h.veredito or (
            veredito_novo == "aprovado" and h.veredito in ("amplo", "estrito")
        )
        if concorda:
            iguais_veredito += 1
        else:
            divergentes_veredito += 1
            if veredito_novo == "fora":
                reprovados_agora += 1

        nova = conn.execute(
            "SELECT padrao_nome, padrao_mecanismo FROM dim_ficha WHERE paper_id = ?",
            (pid,),
        ).fetchone()
        nova = nova or {"padrao_nome": None, "padrao_mecanismo": None}
        tem_padrao_novo = bool(nova["padrao_nome"])
        if tem_padrao_novo == h.tem_padrao:
            iguais_padrao += 1
        else:
            divergentes_padrao += 1

        nome_igual = (
            h.tem_padrao
            and tem_padrao_novo
            and (h.padrao_nome or "").strip().lower() == (nova["padrao_nome"] or "").strip().lower()
        )
        if nome_igual:
            nomes_iguais += 1

        if not concorda or tem_padrao_novo != h.tem_padrao:
            detalhes.append(
                f"| {pid} | {h.veredito} | {veredito_novo} | "
                f"{'sim' if h.tem_padrao else 'nao'} | {'sim' if tem_padrao_novo else 'nao'} |"
            )

    total = len(historicas)
    linhas_md.append("# Validação do backfill — fichas regeneradas vs. históricas\n")
    linhas_md.append(f"Gerado em {db.agora()}  ")
    linhas_md.append(f"Modelo do Estágio B: `{cfg.llm.estagio_b.modelo}`\n")
    linhas_md.append("## Resumo\n")
    linhas_md.append("| Métrica | Valor |")
    linhas_md.append("|---|---|")
    linhas_md.append(f"| Fichas históricas | {total} |")
    linhas_md.append(f"| Regeneradas | {total - sem_regenerada} |")
    linhas_md.append(f"| Mesmo veredito | {iguais_veredito} |")
    linhas_md.append(f"| Veredito divergente | {divergentes_veredito} |")
    linhas_md.append(f"| Aprovado antes, FORA agora | {reprovados_agora} |")
    linhas_md.append(f"| Mesma presença/ausência de Padrão Extraído | {iguais_padrao} |")
    linhas_md.append(f"| Presença de Padrão divergente | {divergentes_padrao} |")
    linhas_md.append(f"| Nome do padrão idêntico | {nomes_iguais} |")
    linhas_md.append("")
    linhas_md.append("## Divergências\n")
    if detalhes:
        linhas_md.append("| paper_id | veredito histórico | veredito novo | padrão histórico | padrão novo |")
        linhas_md.append("|---|---|---|---|---|")
        linhas_md.extend(detalhes)
    else:
        linhas_md.append("Nenhuma divergência de veredito ou de presença de Padrão Extraído.")
    linhas_md.append("")
    linhas_md.append(
        "> Este relatório não corrige nada. Divergência alta significa que o prompt do "
        "Estágio B precisa de ajuste — as fichas históricas já foram revisadas."
    )
    linhas_md.append("")
    linhas_md.append(
        "> O veredito histórico é o que está gravado em `fato_triagem` (o backfill não o "
        "reabre). O veredito novo é o que o Estágio B devolveu nesta regeneração, "
        "registrado em `relatorios/vereditos_estagio_b.json` só para efeito de comparação. "
        "Papers marcados `(nao regenerada)` ainda não passaram pelo Estágio B nesta versão."
    )

    cfg.dir_relatorios.mkdir(parents=True, exist_ok=True)
    caminho = cfg.dir_relatorios / "validacao_backfill.md"
    caminho.write_text("\n".join(linhas_md), encoding="utf-8")
    res.relatorio = caminho
    return caminho


# ── entrada ─────────────────────────────────────────────────────────────────


def rodar(
    seed: Path,
    *,
    cfg: Optional[Config] = None,
    conn: Optional[sqlite3.Connection] = None,
    cliente_hf: Optional[ClienteHF] = None,
    cliente_llm: Optional[ClienteLLM] = None,
    pular_llm: bool = False,
    force: bool = False,
    hoje: Optional[dt.date] = None,
) -> ResultadoBackfill:
    cfg = cfg or config()
    hoje = hoje or db.hoje()
    fechar_conn = conn is None
    conn = conn or db.abrir(cfg)
    hf = cliente_hf or ClienteHF(cfg)
    res = ResultadoBackfill()

    try:
        # 1. vocabulario primeiro - os limites e definicoes vem do seed
        tax = json.loads((seed / "taxonomia.json").read_text(encoding="utf-8"))
        with db.transacao(conn):
            taxonomia.carregar_seed(conn, tax)

        # 2. lista de trabalho: uniao das tres fontes
        itens = montar_lista(seed)
        res.papers = len(itens)
        log.info("lista de trabalho: %s papers", len(itens))

        # 3. hidratacao
        hidratar(conn, hf, itens, res, hoje=hoje, force=force)

        # 4. triagem historica
        importar_triagem(conn, itens, res)

        # 5. classificacoes curadas (autoritativas)
        importar_classificacoes(conn, seed, res, cfg)

        with db.transacao(conn):
            db.garantir_calendario(conn)

        res.fichas_existentes = db.contar(conn, "dim_ficha")

        # 6/7. LLM
        if not pular_llm:
            llm = cliente_llm or ClienteLLM(cfg, conn=conn, run_id=RUN_ID)
            classificar_sem_taxonomia(conn, llm, res, cfg, list(itens))
            gerar_fichas(conn, llm, res, cfg, list(itens))

        # 8. validacao contra o historico
        relatorio_validacao(conn, seed, cfg, res)

        db.upsert_execucao(
            conn,
            {
                "run_id": RUN_ID,
                "iniciado_em": db.agora(),
                "finalizado_em": db.agora(),
                "status": "ok" if not res.avisos else "parcial",
                "dias_cobertos": json.dumps([]),
                "qtd_coletados": res.papers,
                "qtd_novos": res.hidratados,
                "qtd_fora": res.vereditos.get("fora", 0),
                "qtd_amplo": res.vereditos.get("amplo", 0),
                "qtd_estrito": res.vereditos.get("estrito", 0),
                "tokens_entrada": res.uso.tokens_entrada,
                "tokens_saida": res.uso.tokens_saida,
                "custo_usd": res.uso.custo_usd,
                "avisos": json.dumps(res.avisos, ensure_ascii=False),
            },
        )
    finally:
        if cliente_hf is None:
            hf.fechar()
        if fechar_conn:
            conn.close()

    return res
