"""Governanca do vocabulario controlado - agora em codigo, nao por convencao.

**Classificar nao cria rotulo.** O que existia disso - candidato acumulando
quorum, promocao automatica, teto de vocabulario para segura-la - saiu com
`tax_candidato`: o Estagio A registra em que eixo a grade nao serviu
(`aplicar_classificacao`, `nao_encaixes`) e quem promove e a revisao da grade,
que le essa fila. O teto de vertentes por paper continua aqui, e continua
constante - ver `MAX_VERTENTES_POR_PAPER`.

**Fusao de rotulos e manual** e exige comando explicito: vocabulario grande
demais deixa de separar qualquer coisa, e escolher qual par fundir e julgamento
humano.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from . import db
from .log import logger

log = logger("taxonomia")

# Teto de vertentes por paper. Constante, e nao chave de `config`: a spec trata
# a cardinalidade como trava - ela nao se mexe nem na correcao automatica da
# grade -, e um teto configuravel convidaria a afrouxa-la sem que ninguem
# tivesse decidido isso. `llm/schemas.py` importa daqui para declarar o mesmo
# numero no contrato: duas copias do teto seriam duas chances de divergir.
MAX_VERTENTES_POR_PAPER = 2

# Os tres eixos em que o encaixe pode falhar. A leitura de cada um e diferente
# e deliberada: area nova e evento raro e grave - uma peca de sistema que nao
# existia; sub-area nova e rotina saudavel, o campo se ramifica; vertente nova
# deveria ser quase impossivel, e e por isso que ela precisa do instrumento -
# a lista de nove verbos e a hipotese mais fragil do desenho, e nao convinha
# que fosse o unico eixo sem detector de erro. `llm/schemas.py` importa daqui
# para montar o enum do contrato, pelo mesmo motivo de `MAX_VERTENTES_POR_PAPER`.
EIXOS = ("area", "subarea", "vertente")


@dataclass
class NaoEncaixe:
    """A constatacao de que nenhuma celula da grade serve, e em que eixo.

    Nao carrega rotulo proposto, e essa ausencia e o ticket inteiro: quem
    sugeria nome era `tax_candidato`, e o que se acumulou la foram sinonimos -
    seis variantes de robotica, tres de world models. Aqui o modelo constata a
    falha; quem promove rotulo e a revisao da grade, por quorum.
    """

    eixo: str
    justificativa: str


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

    Toda raiz entra, inclusive a que ainda nao tem sub-area. Quem so pode
    oferecer celula completa filtra pela forma - e o que `areas_facetadas` faz.
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
    """A grade que o Estagio A oferece: so a raiz que tem sub-area, aninhada.

    A raiz sem filha fica de fora porque nao oferece celula nenhuma - o par que
    o modelo devolvesse com ela seria recusado por `aplicar_classificacao`, que
    exige sub-area filha da area declarada. Ate a contracao do ticket 05 esse
    filtro tambem separava a grade plana anterior, que convivia em `dim_area`;
    sobrou dele o motivo que nao depende daquela grade - a raiz incompleta, que
    aparece enquanto uma area nova esta sendo montada.
    """
    return [a for a in arvore_de_areas(conn) if a.subareas]


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
    nao_coube: Optional[NaoEncaixe] = None,
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

    `nao_coube` entra por aqui, e nao por uma chamada propria de quem
    classifica, porque **e a mesma reescrita**: tudo o que a classificacao diz
    sobre o lugar do paper na grade - os dois pares, as vertentes e a
    constatacao de que a grade nao serviu - passa a valer de uma vez ou nao
    passa. Nulo apaga o registro anterior pelo mesmo motivo que a ponte e
    reescrita: a declaracao de ontem nao pode sobreviver a uma rodada em que o
    paper encaixou.

    **O nao-encaixe nunca custa a atribuicao do paper.** Ele e registrado ao
    lado do par e da vertente, nao no lugar deles: o paper que nao coube segue
    com a melhor atribuicao possivel, senao a declaracao viraria buraco na
    base - exatamente o que ela existe para evitar.

    Sem `cfg`: o unico teto que esta funcao lia era o de topicos por paper, que
    saiu junto com o campo. O de vertentes e constante do modulo porque a spec
    trata a cardinalidade como trava.
    """
    pai_de = hierarquia(conn)
    validas_vertente = set(vertentes(conn))

    conn.execute("DELETE FROM ponte_paper_area WHERE paper_id = ?", (paper_id,))
    conn.execute("DELETE FROM ponte_paper_vertente WHERE paper_id = ?", (paper_id,))
    conn.execute("DELETE FROM tax_nao_encaixe WHERE paper_id = ?", (paper_id,))

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

    _registrar_nao_encaixe(conn, paper_id, nao_coube)


# ── nao-encaixe ─────────────────────────────────────────────────────────────


def _registrar_nao_encaixe(
    conn: sqlite3.Connection, paper_id: str, nao_coube: Optional[NaoEncaixe]
) -> None:
    """Grava a declaracao de nao-encaixe do paper, se houver uma utilizavel.

    Declaracao malformada e ignorada com aviso, como o rotulo desconhecido do
    par: eixo fora dos tres nao tem fila em que entrar, e justificativa em
    branco nao e legivel como fila de revisao - a grade so se corrige a partir
    do *porque*. Nenhum dos dois derruba a classificacao, que ja esta gravada
    quando esta funcao roda.
    """
    if nao_coube is None:
        return
    justificativa = (nao_coube.justificativa or "").strip()
    if nao_coube.eixo not in EIXOS or not justificativa:
        log.warning(
            "nao-encaixe ignorado em %s: eixo '%s', %d caracteres de justificativa",
            paper_id, nao_coube.eixo, len(justificativa),
        )
        return
    db.inserir_ignorando(
        conn,
        "tax_nao_encaixe",
        {
            "paper_id": paper_id,
            "eixo": nao_coube.eixo,
            "justificativa": justificativa,
            "registrado_em": db.agora(),
        },
    )


def nao_encaixes(
    conn: sqlite3.Connection, *, eixo: Optional[str] = None
) -> list[dict[str, Any]]:
    """A fila de revisao da grade, opcionalmente de um eixo so.

    Sai na ordem do `paper_id` para que duas leituras da mesma base deem a
    mesma fila - quem le isto e a revisao da grade, que precisa contar familias
    e nao pode depender da ordem fisica das linhas.
    """
    sql = "SELECT paper_id, eixo, justificativa FROM tax_nao_encaixe"
    params: list[Any] = []
    if eixo:
        sql += " WHERE eixo = ?"
        params.append(eixo)
    return [dict(r) for r in conn.execute(sql + " ORDER BY paper_id", params)]


# ── fusao (manual) ──────────────────────────────────────────────────────────


def fundir(conn: sqlite3.Connection, *, de: str, para: str) -> dict[str, int]:
    """Reescreve a ponte de area de `de` para `para` e apaga o rotulo `de`.

    Sem parametro de tipo: a fusao aceitava area ou topico, e o topico saiu do
    banco na contracao. Um parametro de um valor so nao escolhe nada.
    """
    for rotulo in (de, para):
        if not conn.execute("SELECT 1 FROM dim_area WHERE area = ?", (rotulo,)).fetchone():
            raise ValueError(f"area inexistente: {rotulo}")

    with db.transacao(conn):
        # o paper pode ja ter a area de destino: nesse caso a primaria vence
        conn.execute(
            "UPDATE OR IGNORE ponte_paper_area SET area = ? WHERE area = ?", (para, de)
        )
        conn.execute("DELETE FROM ponte_paper_area WHERE area = ?", (de,))
        movidos = conn.execute(
            "SELECT COUNT(*) AS n FROM ponte_paper_area WHERE area = ?", (para,)
        ).fetchone()["n"]
        conn.execute("DELETE FROM dim_area WHERE area = ?", (de,))

    log.info("fusao de area: '%s' -> '%s' (%s papers no destino)", de, para, movidos)
    return {"papers_no_destino": int(movidos)}


# ── bootstrap do vocabulario ────────────────────────────────────────────────
#
# O vocabulario vivo mora no banco, e o banco nao esta versionado. `exportar` o
# retrata num JSON que entra no git (`config/taxonomia_inicial.json`) e
# `carregar` o repoe num banco novo - e so isso: nao e migracao nem sincronia.
# Nao-encaixe nao entra no arquivo porque e fila de revisao, estado de uma base
# especifica, e nao vocabulario vigente.


def exportar(conn: sqlite3.Connection) -> dict[str, Any]:
    """dim_area / dim_vertente -> dicionario serializavel.

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
    contagem = {"areas": 0, "subareas": 0, "vertentes": 0, "ja_existiam": 0}

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
    for item in dados.get("vertentes") or []:
        _inserir("vertentes", "dim_vertente", "vertente", item)
    return contagem


def listar(conn: sqlite3.Connection) -> dict[str, Any]:
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
        # Contagem, e nao a fila inteira: `listar` e o retrato do vocabulario
        # vigente, e o nao-encaixe so entra nele para dizer quanto a grade esta
        # devendo por eixo. Quem quer a fila chama `nao_encaixes`.
        "nao_encaixes": {
            r["eixo"]: r["papers"]
            for r in conn.execute(
                "SELECT eixo, COUNT(*) AS papers FROM tax_nao_encaixe "
                "GROUP BY eixo ORDER BY eixo"
            )
        },
    }
