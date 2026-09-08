"""Governanca do vocabulario controlado - agora em codigo, nao por convencao.

Tetos (config `taxonomia`): 10 areas, 24 topicos, e 2 papers distintos para
promover um candidato. O teto de vertentes por paper nao e configuravel - ver
`MAX_VERTENTES_POR_PAPER`.

Promocao e automatica. **Fusao de rotulos e manual** e exige comando explicito:
vocabulario grande demais deixa de separar qualquer coisa, e escolher qual par
fundir e julgamento humano.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional, Sequence

from . import db
from .config import Taxonomia as ConfigTaxonomia
from .log import logger

log = logger("taxonomia")

# Teto de vertentes por paper. Constante, e nao chave de `config`: a spec trata
# a cardinalidade como trava - ela nao se mexe nem na correcao automatica da
# grade -, e um teto configuravel convidaria a afrouxa-la sem que ninguem
# tivesse decidido isso. `llm/schemas.py` importa daqui para declarar o mesmo
# numero no contrato: duas copias do teto seriam duas chances de divergir.
MAX_VERTENTES_POR_PAPER = 2


@dataclass
class ResultadoCandidato:
    rotulo: str
    tipo: str
    papers: list[str]
    promovido: bool = False
    aviso: Optional[str] = None


@dataclass
class Area:
    """Uma area da grade com as sub-areas sob ela.

    A sub-area e uma `Area` de `subareas` vazia, e nao um tipo proprio, porque
    e o mesmo tipo de coisa - a razao de as duas morarem em `dim_area`.
    """

    rotulo: str
    definicao: str
    subareas: list["Area"] = field(default_factory=list)


# ── leitura ─────────────────────────────────────────────────────────────────


def hierarquia(conn: sqlite3.Connection) -> dict[str, Optional[str]]:
    """Cada rotulo de `dim_area` com o pai dele; a area raiz aponta para None.

    E o que responde "esta sub-area e filha desta area?" numa consulta so. O
    enum do Estagio A e plano - JSON Schema nao expressa sub-area valida *dado*
    que a area e X -, entao o parentesco e cobrado na persistencia.
    """
    return {
        r["area"]: r["area_pai"]
        for r in conn.execute("SELECT area, area_pai FROM dim_area")
    }


def arvore_de_areas(conn: sqlite3.Connection) -> list[Area]:
    """`dim_area` inteira em dois niveis: toda raiz, com as filhas sob ela.

    A raiz da grade plana anterior vem junto, de `subareas` vazia. Quem quer so
    uma das duas grades filtra pela forma - `areas_facetadas` e
    `areas_grade_antiga` sao os dois lados desse filtro.
    """
    filhas: dict[str, list[Area]] = {}
    for r in conn.execute(
        "SELECT area, definicao, area_pai FROM dim_area "
        "WHERE area_pai IS NOT NULL ORDER BY area"
    ):
        filhas.setdefault(r["area_pai"], []).append(Area(r["area"], r["definicao"] or ""))
    return [
        Area(r["area"], r["definicao"] or "", filhas.get(r["area"], []))
        for r in conn.execute(
            "SELECT area, definicao FROM dim_area WHERE area_pai IS NULL ORDER BY area"
        )
    ]


def areas_facetadas(conn: sqlite3.Connection) -> list[Area]:
    """A grade facetada: so a raiz que tem sub-area, aninhada.

    E o que o prompt e o enum do Estagio A oferecem. A raiz sem filha fica de
    fora porque e da grade plana anterior, que ainda convive em `dim_area` ate a
    contracao do ticket 05.
    """
    return [a for a in arvore_de_areas(conn) if a.subareas]


def areas_grade_antiga(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """A grade plana anterior - area sem pai e sem filha -, com a definicao.

    As duas grades convivem em `dim_area` desde o passo de expand, e nada as
    distingue alem da forma: por isso a hierarquia e o filtro. Desde o ticket 02
    a classificacao roda na grade facetada (`areas_facetadas`) e esta funcao
    sobrou para o teto de vocabulario, que continua contando so a grade plana
    para nao congelar a promocao de rotulo. A plana sai do banco no ticket 05.
    """
    return [
        (r["area"], r["definicao"])
        for r in conn.execute(
            "SELECT area, definicao FROM dim_area WHERE area_pai IS NULL "
            "  AND area NOT IN (SELECT area_pai FROM dim_area WHERE area_pai IS NOT NULL) "
            "ORDER BY area"
        )
    ]


def topicos(conn: sqlite3.Connection) -> list[str]:
    return [r["topico"] for r in conn.execute("SELECT topico FROM dim_topico ORDER BY topico")]


def vertentes(conn: sqlite3.Connection) -> list[str]:
    return [
        r["vertente"]
        for r in conn.execute("SELECT vertente FROM dim_vertente ORDER BY vertente")
    ]


def vertente_dominante(conn: sqlite3.Connection, paper_id: str) -> Optional[str]:
    """A vertente de ordem 1 do paper - a resposta unica que ranking e
    agregacao precisam quando o paper tem duas (user story 10)."""
    row = conn.execute(
        "SELECT vertente FROM ponte_paper_vertente WHERE paper_id = ? AND ordem = 1",
        (paper_id,),
    ).fetchone()
    return row["vertente"] if row else None


def _tabela(tipo: str) -> tuple[str, str]:
    return ("dim_area", "area") if tipo == "area" else ("dim_topico", "topico")


def _teto(tipo: str, cfg: ConfigTaxonomia) -> int:
    return cfg.max_areas if tipo == "area" else cfg.max_topicos


def _quantidade(conn: sqlite3.Connection, tipo: str) -> int:
    # a area conta so a grade plana: somar as duas grades bateria no teto e
    # congelaria a promocao de rotulo sem que ninguem tivesse pedido isso
    if tipo == "area":
        return len(areas_grade_antiga(conn))
    tabela, _ = _tabela(tipo)
    return db.contar(conn, tabela)


# ── classificacao de um paper ───────────────────────────────────────────────


def aplicar_classificacao(
    conn: sqlite3.Connection,
    paper_id: str,
    *,
    area_primaria: str,
    subarea_primaria: str,
    area_secundaria: Optional[str] = None,
    subarea_secundaria: Optional[str] = None,
    vertentes_paper: Sequence[str] = (),
) -> None:
    """Reescreve as pontes de um paper: os pares (area > sub-area) e as vertentes.

    Par invalido e ignorado com aviso, e o paper segue classificado: e o mesmo
    tratamento que o rotulo desconhecido sempre teve aqui - a LLM nao cria
    vocabulario, e derrubar a classificacao por causa de um rotulo custaria a
    triagem inteira do paper.

    Duas coisas tornam um par invalido, e a segunda e a que o enum nao pega:
    rotulo fora de `dim_area`, e sub-area que nao e filha da area declarada. O
    schema do Estagio A oferece a sub-area num enum plano - JSON Schema nao
    expressa "sub-area valida *dado* que a area e X" sem um `oneOf` de dez ramos
    que nem todo provedor trata -, entao o parentesco so pode ser cobrado aqui.

    `vertentes_paper` chega ordenada, a dominante primeiro, e e a ordem que a
    ponte grava. **O teto de duas e aplicado aqui, e nao so pedido no prompt**
    (user story 29): `maxItems` sob `strict: true` nao e cumprido por todo
    provedor, e uma terceira vertente aceita em silencio faria a dominante
    perder o sentido - se tudo cabe, nada e dominante.

    A ponte de topico e apagada e nao reescrita: o topico saiu do contrato do
    Estagio A neste ticket, e deixar o antigo de pe daria ao paper uma vertente
    da grade nova ao lado de um topico da grade que deixou de existir. A tabela
    inteira sai no ticket 05, e com ela esta linha.

    Sem `cfg`: o unico teto que esta funcao lia era o de topicos por paper, que
    saiu junto com o campo. O de vertentes e constante do modulo porque a spec
    trata a cardinalidade como trava.
    """
    pai_de = hierarquia(conn)
    validas_vertente = set(vertentes(conn))

    conn.execute("DELETE FROM ponte_paper_area WHERE paper_id = ?", (paper_id,))
    conn.execute("DELETE FROM ponte_paper_topico WHERE paper_id = ?", (paper_id,))
    conn.execute("DELETE FROM ponte_paper_vertente WHERE paper_id = ?", (paper_id,))

    def _par(area: Optional[str], subarea: Optional[str], *, primaria: bool) -> None:
        if not area and not subarea:
            return                       # par secundario nulo e a resposta comum
        if not subarea or pai_de.get(subarea) != area:
            log.warning(
                "par (area > sub-area) ignorado em %s: %s > %s", paper_id, area, subarea
            )
            return
        db.inserir_ignorando(
            conn,
            "ponte_paper_area",
            {
                "paper_id": paper_id,
                "area": area,
                "subarea": subarea,
                "is_primaria": int(primaria),
            },
        )

    _par(area_primaria, subarea_primaria, primaria=True)
    if (area_secundaria, subarea_secundaria) != (area_primaria, subarea_primaria):
        _par(area_secundaria, subarea_secundaria, primaria=False)

    # A ordem sai da posicao na lista *depois* de descartar o desconhecido: uma
    # vertente inventada em primeiro lugar nao pode deixar a valida seguinte
    # como secundaria de ninguem.
    ordem = 0
    for v in dict.fromkeys(vertentes_paper):
        if v not in validas_vertente:
            if v:
                log.warning("vertente desconhecida ignorada em %s: %s", paper_id, v)
            continue
        ordem += 1
        if ordem > MAX_VERTENTES_POR_PAPER:
            log.warning(
                "vertente alem do teto de %d ignorada em %s: %s",
                MAX_VERTENTES_POR_PAPER, paper_id, v,
            )
            break
        db.inserir_ignorando(
            conn,
            "ponte_paper_vertente",
            {"paper_id": paper_id, "vertente": v, "ordem": ordem},
        )


# ── candidatos ──────────────────────────────────────────────────────────────


def registrar_candidato(
    conn: sqlite3.Connection,
    *,
    rotulo: str,
    tipo: str,
    definicao: str,
    paper_id: str,
    cfg: Optional[ConfigTaxonomia] = None,
    promover: bool = True,
) -> ResultadoCandidato:
    """Acrescenta o paper ao candidato e promove quando houver quorum e folga.

    `promover=False` grava o candidato e a associacao com o paper, mas nao
    promove nem com quorum e folga. E o modo da reclassificacao total
    (`reclassificar --tudo`): promover no meio de uma rodada que varre a base
    inteira deixaria os papers ja classificados sem o rotulo novo - eles
    passaram pelo Estagio A com um vocabulario menor e ninguem volta para
    reavalia-los. Com o vocabulario congelado, a promocao vira decisao manual
    depois da rodada (`taxonomia listar`, `taxonomia promover`).
    """
    cfg = cfg or ConfigTaxonomia()
    rotulo = (rotulo or "").strip()
    if not rotulo or tipo not in ("area", "topico"):
        return ResultadoCandidato(rotulo, tipo, [], aviso="candidato_invalido")

    tabela, coluna = _tabela(tipo)
    ja_existe = conn.execute(
        f"SELECT 1 FROM {tabela} WHERE {coluna} = ?", (rotulo,)
    ).fetchone()
    if ja_existe:
        return ResultadoCandidato(rotulo, tipo, [], aviso=None)

    row = conn.execute(
        "SELECT papers, promovido FROM tax_candidato WHERE rotulo = ? AND tipo = ?",
        (rotulo, tipo),
    ).fetchone()
    papers = json.loads(row["papers"]) if row else []
    if paper_id not in papers:
        papers.append(paper_id)

    db.upsert_candidato(
        conn,
        {
            "rotulo": rotulo,
            "tipo": tipo,
            "definicao": definicao,
            "papers": json.dumps(papers, ensure_ascii=False),
            "promovido": int(bool(row["promovido"])) if row else 0,
            "criado_em": db.agora(),
        },
    )

    res = ResultadoCandidato(rotulo, tipo, papers)
    if not promover or len(papers) < cfg.min_papers_novo_rotulo:
        return res

    if _quantidade(conn, tipo) >= _teto(tipo, cfg):
        res.aviso = f"teto_vocabulario:{tipo}:{rotulo}"
        log.warning(
            "candidato '%s' com quorum mas teto de %s atingido - fusao manual necessaria",
            rotulo, tipo,
        )
        return res

    _promover(conn, rotulo=rotulo, tipo=tipo, definicao=definicao)
    res.promovido = True
    log.info("candidato promovido a %s: %s", tipo, rotulo)
    return res


def _promover(
    conn: sqlite3.Connection, *, rotulo: str, tipo: str, definicao: str
) -> None:
    """Grava o rotulo no vocabulario. Privada: quem promove entra por
    `registrar_candidato` (automatico) ou `promover_candidato` (a mao), que sao
    os dois que sabem checar quorum, teto e duplicata."""
    tabela, coluna = _tabela(tipo)
    db.upsert(
        conn,
        tabela,
        {coluna: rotulo, "definicao": definicao, "desde": db.hoje().isoformat()},
        chave=[coluna],
    )
    conn.execute(
        "UPDATE tax_candidato SET promovido = 1 WHERE rotulo = ? AND tipo = ?",
        (rotulo, tipo),
    )


def promover_candidato(
    conn: sqlite3.Connection,
    *,
    rotulo: str,
    tipo: str = "topico",
    cfg: Optional[ConfigTaxonomia] = None,
) -> dict[str, Any]:
    """Promove a mao um candidato de `tax_candidato`, com a definicao dele.

    Existe para o passo manual depois da reclassificacao total, onde a promocao
    automatica fica desligada: o operador le `taxonomia listar` e decide, um a
    um, quem vira vocabulario e quem devia ter sido fusao. Recusa - com
    ValueError, como `fundir` - o rotulo que nao e candidato, o que ja e
    vocabulario e o que esbarra no teto, porque nenhum dos tres tem conserto
    dentro deste comando.
    """
    cfg = cfg or ConfigTaxonomia()
    rotulo = (rotulo or "").strip()
    if tipo not in ("area", "topico"):
        raise ValueError(f"tipo invalido: {tipo} (use 'area' ou 'topico')")

    tabela, coluna = _tabela(tipo)
    if conn.execute(f"SELECT 1 FROM {tabela} WHERE {coluna} = ?", (rotulo,)).fetchone():
        raise ValueError(f"'{rotulo}' ja e {tipo} do vocabulario - nada a promover")

    row = conn.execute(
        "SELECT definicao, papers FROM tax_candidato WHERE rotulo = ? AND tipo = ?",
        (rotulo, tipo),
    ).fetchone()
    if not row:
        raise ValueError(f"nao ha candidato a {tipo} com o rotulo '{rotulo}'")

    quantidade, teto = _quantidade(conn, tipo), _teto(tipo, cfg)
    if quantidade >= teto:
        raise ValueError(
            f"teto de {tipo} atingido ({quantidade}/{teto}) - funda dois rotulos "
            "antes (`hfpapers taxonomia fundir`)"
        )

    definicao = row["definicao"] or ""
    with db.transacao(conn):
        _promover(conn, rotulo=rotulo, tipo=tipo, definicao=definicao)
    papers = json.loads(row["papers"] or "[]")
    log.info("candidato promovido a mao a %s: %s (%s papers)", tipo, rotulo, len(papers))
    return {"rotulo": rotulo, "tipo": tipo, "definicao": definicao, "papers": len(papers)}


# ── fusao (manual) ──────────────────────────────────────────────────────────


def fundir(conn: sqlite3.Connection, *, de: str, para: str, tipo: str) -> dict[str, int]:
    """Reescreve as pontes de `de` para `para` e apaga o rotulo `de`."""
    tabela, coluna = _tabela(tipo)
    ponte = "ponte_paper_area" if tipo == "area" else "ponte_paper_topico"

    for rotulo in (de, para):
        if not conn.execute(f"SELECT 1 FROM {tabela} WHERE {coluna} = ?", (rotulo,)).fetchone():
            raise ValueError(f"{tipo} inexistente: {rotulo}")

    with db.transacao(conn):
        if tipo == "area":
            # o paper pode ja ter a area de destino: nesse caso a primaria vence
            conn.execute(
                "UPDATE OR IGNORE ponte_paper_area SET area = ? WHERE area = ?", (para, de)
            )
            conn.execute("DELETE FROM ponte_paper_area WHERE area = ?", (de,))
        else:
            conn.execute(
                "UPDATE OR IGNORE ponte_paper_topico SET topico = ? WHERE topico = ?",
                (para, de),
            )
            conn.execute("DELETE FROM ponte_paper_topico WHERE topico = ?", (de,))
        movidos = conn.execute(
            f"SELECT COUNT(*) AS n FROM {ponte} WHERE {coluna} = ?", (para,)
        ).fetchone()["n"]
        conn.execute(f"DELETE FROM {tabela} WHERE {coluna} = ?", (de,))

    log.info("fusao %s: '%s' -> '%s' (%s papers no destino)", tipo, de, para, movidos)
    return {"papers_no_destino": int(movidos)}


# ── bootstrap do vocabulario ────────────────────────────────────────────────
#
# O vocabulario vivo mora no banco, e o banco nao esta versionado. `exportar` o
# retrata num JSON que entra no git (`config/taxonomia_inicial.json`) e
# `carregar` o repoe num banco novo - e so isso: nao e migracao nem sincronia.
# Candidato nao entra no arquivo porque candidato e fila de promocao, estado de
# uma base especifica, e nao vocabulario vigente.


def exportar(conn: sqlite3.Connection) -> dict[str, Any]:
    """dim_area / dim_topico / dim_vertente -> dicionario serializavel.

    `desde` fica de fora de proposito: num banco novo a data em que o rotulo
    passou a valer e a da carga, nao a do banco de origem.

    A sub-area viaja aninhada sob a area, e nao com o nome do pai num campo ao
    lado: aninhada, ela nao consegue declarar dois pais, e e a forma de que
    `carregar` precisa para gravar o pai antes da filha.
    """
    return {
        "areas": [
            {
                "rotulo": a.rotulo,
                "definicao": a.definicao,
                "subareas": [
                    {"rotulo": s.rotulo, "definicao": s.definicao} for s in a.subareas
                ],
            }
            for a in arvore_de_areas(conn)
        ],
        "topicos": [
            {"rotulo": r["topico"], "definicao": r["definicao"] or ""}
            for r in conn.execute("SELECT topico, definicao FROM dim_topico ORDER BY topico")
        ],
        "vertentes": [
            {"rotulo": r["vertente"], "definicao": r["definicao"] or ""}
            for r in conn.execute(
                "SELECT vertente, definicao FROM dim_vertente ORDER BY vertente"
            )
        ],
    }


def carregar(conn: sqlite3.Connection, dados: dict[str, Any]) -> dict[str, int]:
    """Inverso de `exportar`, para banco sem vocabulario. Idempotente.

    Rotulo que ja existe nao e tocado: a definicao viva do banco ganha da do
    arquivo, que e um retrato de outro momento. Por isso `INSERT OR IGNORE` e
    nao upsert - rodar duas vezes nao muda nada e nao desfaz fusao nenhuma.
    """
    desde = db.hoje().isoformat()
    contagem = {"areas": 0, "subareas": 0, "topicos": 0, "vertentes": 0, "ja_existiam": 0}

    def _inserir(chave: str, tabela: str, coluna: str, item: dict, **extra: Any) -> str:
        """Grava um rotulo e devolve o que foi gravado - '' se nao havia rotulo."""
        rotulo = (item.get("rotulo") or "").strip()
        if not rotulo:
            log.warning("entrada sem rotulo ignorada em %s", chave)
            return ""
        entrou = db.inserir_ignorando(
            conn,
            tabela,
            {coluna: rotulo, "definicao": item.get("definicao") or "", "desde": desde, **extra},
        )
        contagem[chave if entrou else "ja_existiam"] += 1
        return rotulo

    for item in dados.get("areas") or []:
        pai = _inserir("areas", "dim_area", "area", item)
        if not pai:
            continue   # sem pai gravado a FK da auto-referencia recusaria as filhas
        for sub in item.get("subareas") or []:
            _inserir("subareas", "dim_area", "area", sub, area_pai=pai)
    for item in dados.get("topicos") or []:
        _inserir("topicos", "dim_topico", "topico", item)
    for item in dados.get("vertentes") or []:
        _inserir("vertentes", "dim_vertente", "vertente", item)
    return contagem


def listar(conn: sqlite3.Connection, cfg: Optional[ConfigTaxonomia] = None) -> dict[str, Any]:
    """O vocabulario vigente com quantos papers cada rotulo carrega.

    A sub-area vem aninhada sob a area, como no arquivo: quem lista quer ver a
    grade, e uma sub-area solta na lista de areas nao diz de quem e filha.

    A vertente conta paper distinto, e nao linha da ponte, pelo mesmo motivo da
    area - e essa contagem que o ticket 08 le para decidir qual vertente e ruido
    de um mes e qual sobrevive. `dominantes` a parte porque uma vertente pode
    viver so como segunda escolha, e uma que nunca e dominante nao esta
    dizendo o mesmo que uma que e.

    A contagem procura o rotulo nas duas colunas da ponte porque cada um so
    aparece na sua: a raiz em `area`, a filha em `subarea`. E conta paper
    distinto, e nao linha: desde que o par secundario pode repetir a area do
    primario, um paper so chega a ter duas linhas na mesma area.
    """
    cfg = cfg or ConfigTaxonomia()
    por_pai: dict[Optional[str], list[dict]] = {}
    for r in conn.execute(
        "SELECT d.area AS rotulo, d.definicao, d.desde, d.area_pai, "
        "       (SELECT COUNT(DISTINCT p.paper_id) FROM ponte_paper_area p "
        "         WHERE p.area = d.area OR p.subarea = d.area) AS papers "
        "FROM dim_area d ORDER BY papers DESC, rotulo"
    ):
        linha = dict(r)
        por_pai.setdefault(linha.pop("area_pai"), []).append(linha)

    return {
        "areas": [
            {**a, "subareas": por_pai.get(a["rotulo"], [])} for a in por_pai.get(None, [])
        ],
        "topicos": [
            dict(r)
            for r in conn.execute(
                "SELECT d.topico AS rotulo, d.definicao, d.desde, "
                "       (SELECT COUNT(*) FROM ponte_paper_topico p WHERE p.topico = d.topico) AS papers "
                "FROM dim_topico d ORDER BY papers DESC, rotulo"
            )
        ],
        "vertentes": [
            dict(r)
            for r in conn.execute(
                "SELECT d.vertente AS rotulo, d.definicao, d.desde, "
                "       (SELECT COUNT(*) FROM ponte_paper_vertente p "
                "         WHERE p.vertente = d.vertente) AS papers, "
                "       (SELECT COUNT(*) FROM ponte_paper_vertente p "
                "         WHERE p.vertente = d.vertente AND p.ordem = 1) AS dominantes "
                "FROM dim_vertente d ORDER BY papers DESC, rotulo"
            )
        ],
        "candidatos": [
            {**dict(r), "papers": json.loads(r["papers"])}
            for r in conn.execute(
                "SELECT rotulo, tipo, definicao, papers, promovido FROM tax_candidato "
                "ORDER BY promovido, rotulo"
            )
        ],
        "tetos": {"areas": cfg.max_areas, "topicos": cfg.max_topicos},
    }
