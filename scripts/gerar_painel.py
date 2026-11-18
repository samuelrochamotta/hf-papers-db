"""Gera o painel HTML estatico a partir dos Parquet de marts/.

E a interface de leitura do projeto: nao ha outro dashboard. O painel e um
site estatico publico (GitHub Pages), sem servidor: uma pasta com
`index.html`, o app, o ECharts e os dados em JSON a parte.

O desenho e o mesmo do Artifact "Painel Daily Papers", que nasceu como
artboard da Claude Design. `scripts/painel_app.js` e o app de navegador e os
graficos sao Apache ECharts, num build com so os modulos usados
(`scripts/echarts/`, saida versionada em `scripts/vendor/`). Este script nao
desenha nada: extrai os dados, pre-agrega o que da e escreve os arquivos.

Duas saidas:

- **Pasta** (padrao, `relatorios/painel/`): `index.html` leve, `dados.json`
  com o que a primeira pintura precisa e `fichas.json`, o texto das fichas,
  que o app busca depois de desenhar. Separar as fichas e o que deixa o
  primeiro carregamento leve num site publico: elas sao a maior parte do peso.
- **Arquivo unico** (`--destino algo.html`): tudo embutido, inclusive o
  ECharts, para abrir offline ou mandar por e-mail. E o formato das previas.

Quatro decisoes que valem explicacao:

1. Le `marts/_manifest.json` e nao roda de novo se o `run_id` for o mesmo da
   ultima geracao. O gatilho do launchd e `WatchPaths`, que pode disparar mais
   de uma vez para a mesma escrita; a trava de `run_id` torna o disparo extra
   um no-op em vez de trabalho repetido.

2. Recorta uma janela de dias (padrao 90) para a aba viva. Sem isso o arquivo
   cresce para sempre: sao ~28 papers/dia entrando na base. A serie historica
   completa continua nos Parquet - o painel e a vitrine, nao o arquivo morto.
   O peso vem do texto das fichas embutido em `DADOS`, nao de HTML por card.
   Se ficar pesado para distribuir, `--dias` e o botao para girar.

3. A aba historica (`hall`) guarda, por trimestre de publicacao, os 15
   aprovados mais votados com a ficha inteira e os 5 descartados mais votados
   com a regra e a justificativa, como auditoria. Ela NAO preserva dado nenhum contra perda:
   nada e apagado, nem do banco nem dos Parquet. O que ela resolve e
   visibilidade - impedir que o recorte de 90 dias esconda para sempre o que a
   comunidade mais votou. Por isso e derivada a cada geracao, sem tabela nova,
   sem estado em disco e sem estagio novo no pipeline.

   Nao ha deduplicacao a fazer: `data_hf_daily` e imutavel, entao cada paper
   pertence a exatamente um trimestre, para sempre.

4. Nada de pandas nem jinja2. O env `digest-hf` nao tem os dois, e um painel de
   distribuicao nao justifica dependencia nova - pyarrow e pyyaml ja estao la.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import yaml

RAIZ = Path(__file__).resolve().parent.parent
DIR_MARTS = RAIZ / "marts"
DESTINO_PADRAO = RAIZ / "relatorios" / "painel"
CARIMBO = RAIZ / "marts" / ".painel_run_id"
APP_JS = Path(__file__).resolve().parent / "painel_app.js"
ECHARTS_JS = Path(__file__).resolve().parent / "vendor" / "echarts.painel.min.js"
# URL publica do painel, para as tags de compartilhamento (og:url).
URL_PUBLICA = os.environ.get("PAINEL_URL_PUBLICA", "")
CONFIG = RAIZ / "config.yaml"

JANELA_PADRAO = 90
JANELA_HALL_PADRAO = 90

# Quinze e cinco, por decisao editorial (ADR 004): o registro historico e
# leitura, e os descartados ficam so como auditoria do corte. Ranking unico por
# voto desde que o perfil de leitura saiu do painel (21/10/2026).
TOPO_APROVADOS = 15
TOPO_DESCARTADOS = 5


ORDINAL = {1: "1", 2: "2", 3: "3", 4: "4"}

# Enquanto uma linha antiga sobreviver com esse prefixo (estagios/classificacao.py),
# a justificativa dela e sobre a infraestrutura ter falhado, nao sobre o paper -
# apresentar isso sob o rotulo "POR QUE AMPLO" seria fingir raciocinio de
# classificacao onde so houve fallback. A causa e corrigida na issue #1; isto e
# rede para o que ja foi gravado.
#
# A issue #1 remove o fallback inteiro de estagios/classificacao.py - depois
# dela, nada mais escreve este literal, e um grep por quem produz este texto
# nao vai encontrar ninguem. Isso NAO torna esta constante codigo morto: ela
# existe para as linhas ja gravadas no banco antes da mudanca, que carregam
# esse prefixo para sempre. Nao remova so porque o produtor sumiu.
PREFIXO_FALLBACK = "Estagio B falhou;"

# Segunda rede pelo texto, mesmo espirito da primeira e pelo mesmo motivo:
# linhas ja gravadas. A carga historica escrevia como `justificativa` um
# carimbo de PROCEDENCIA ("Importado do historico (estado)"), nao um motivo -
# em 2026-09-05 sao ~160 linhas assim no banco. Quem escrevia esse texto ja nao
# existe no codigo, mas as linhas ficaram, e o painel e regenerado a cada rodada
# diaria: sem esta rede o carimbo sairia sob "POR QUE ESTRITO" e o painel
# mentiria sobre o que o pipeline avaliou.
#
# Rede para dado legado, e so isso: depois da reclassificacao total (secao 3 da
# spec) toda linha tem `revisao >= 2` e justificativa escrita pelo pipeline,
# e esta constante pode ser removida - conferir antes com
# `SELECT COUNT(*) FROM fato_triagem WHERE justificativa LIKE 'Importado do historico%'`.
PREFIXO_IMPORTADO = "Importado do historico"


def justificativa_exibivel(triagem: dict) -> tuple[str, int]:
    """Decide o que o app pode mostrar como motivo da decisao.

    Retorna (texto, codigo): codigo 0 e o texto normal, 2 e justificativa de
    fallback do Estagio B (texto descartado, o app troca por aviso), 3 e
    ausencia de texto exibivel - `justificativa` vazia, ou um carimbo de
    procedencia legado no lugar do motivo. Sem o 3 esses casos sairiam como
    cabecalho oco (rotulo "POR QUE ESTRITO"/"POR QUE AMPLO" sem corpo) ou,
    pior, como frase que finge ser um motivo. Os dois codigos residuais sao a
    mesma nota de honestidade da issue #2 para as duas listas (aprovados e
    descartados), que assim nao divergem na regra. O rotulo do cabecalho e
    "POR QUE ESTE DEGRAU" desde o ADR 004.

    O codigo 1 (paper sem justificativa propria, porque o veredito nao vinha do
    pipeline) nao existe mais: hoje todo veredito sai do pipeline. Os codigos
    nao foram renumerados de proposito - `painel_app.js` le o mesmo contrato e
    um 2 que virasse 1 mudaria o aviso de papers ja publicados.
    """
    texto = triagem.get("justificativa") or ""
    if texto.startswith(PREFIXO_FALLBACK):
        return "", 2
    if not texto or texto.startswith(PREFIXO_IMPORTADO):
        return "", 3
    return texto, 0


# O que o artboard trazia no <helmet>. O resto do desenho vive em style inline
# dentro de painel_app.js - e assim que o canvas escreve, e manter igual e o
# que permite comparar os dois lado a lado sem traduzir nada.
CSS = """
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body { margin: 0; background: #0d0f11; color: #ecebe6; font-family: "Instrument Sans", system-ui, sans-serif; -webkit-font-smoothing: antialiased; }
a { color: #d9a441; text-decoration: none; border-bottom: 1px solid rgba(217,164,65,0.3); }
a:hover { color: #ecc478; border-bottom-color: #ecc478; }
:focus-visible { outline: 2px solid #d9a441; outline-offset: 2px; }
.carregando { max-width: 760px; margin: 0 auto; padding: 60px 20px; color: #a8a49b; font-size: 15px; line-height: 1.6; }
.carregando h1 { font-family: Newsreader, Georgia, serif; font-weight: 300; font-size: 44px; color: #f5f3ee; margin: 0 0 14px; }
.chip { transition: background 120ms ease, border-color 120ms ease, color 120ms ease; cursor: pointer; user-select: none; }
.chip:hover { background: #23282e !important; border-color: #414a53 !important; color: #ecebe6 !important; }
.chip-on:hover { filter: brightness(1.08); }
.aba { transition: color 120ms ease, border-color 120ms ease; cursor: pointer; user-select: none; white-space: nowrap; }
.aba:hover { color: #ecebe6 !important; }
.seg { transition: box-shadow 120ms ease; }
.seg:hover { box-shadow: inset 0 0 0 1.5px #f5f3ee; }
.row { transition: background 120ms ease; cursor: pointer; }
.row:hover { background: #191d21; }
.mais { color: #d9a441; border-bottom: 1px solid rgba(217,164,65,0.3); transition: color 120ms ease, border-color 120ms ease; cursor: pointer; }
.mais:hover { color: #ecc478; border-bottom-color: #ecc478; }
.card { background: #16191c; border: 1px solid #242a30; border-radius: 5px; }
/* Cards de grafico (ECharts). O titulo e h3 e o resumo em texto vem antes
   do grafico: e o que um leitor de tela ou um buscador leem. */
.card-grafico { padding: 22px 24px 20px; margin-bottom: 34px; display: flex; flex-direction: column; gap: 14px; min-width: 0; }
.card-cab { display: flex; justify-content: space-between; align-items: flex-start; gap: 14px 18px; flex-wrap: wrap; }
.card-tit { display: flex; flex-direction: column; gap: 5px; flex: 1 1 380px; min-width: 0; max-width: 760px; }
.titulo-card { margin: 0; font-family: Newsreader, Georgia, serif; font-size: 26px; font-weight: 400; line-height: 1.1; color: #f5f3ee; }
.subtitulo-card { margin: 0; font-size: 13.5px; font-weight: 400; color: #ecebe6; }
.descr { font-size: 12.5px; color: #8b8f96; line-height: 1.5; text-wrap: pretty; }
.resumo-grafico { margin: 0; font-family: Newsreader, Georgia, serif; font-size: 15px; font-weight: 300; line-height: 1.55; color: #c9c5bb; text-wrap: pretty; }
.grafico { width: 100%; min-width: 0; }
.rolagem { overflow-x: auto; -webkit-overflow-scrolling: touch; }
.vazio { padding: 44px 0; text-align: center; font-size: 12.5px; color: #6d7178; }
.legenda { display: flex; flex-wrap: wrap; gap: 6px 14px; font-size: 11.5px; color: #a8a49b; align-items: center; }
.legenda > span { display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; }
.legenda i { display: inline-block; width: 9px; height: 9px; border-radius: 2px; flex: none; }
.legenda i.traco { width: 16px; height: 0; border-radius: 0; border-top: 2px solid; }
.legenda i.tracejado { border-top-style: dashed; }
.legenda-linha { display: flex; flex-wrap: wrap; gap: 8px 18px; align-items: center; }
.tabela-dados { font-size: 12px; color: #a8a49b; }
.tabela-dados summary { cursor: pointer; color: #8b8f96; font-size: 11.5px; letter-spacing: 0.04em; width: max-content; }
.tabela-dados summary:hover { color: #ecebe6; }
.tabela-dados table { border-collapse: collapse; margin-top: 10px; width: 100%; font-variant-numeric: tabular-nums; }
.tabela-dados th, .tabela-dados td { padding: 6px 10px; border-bottom: 1px solid #1d2226; text-align: right; white-space: nowrap; }
.tabela-dados th:first-child { text-align: left; white-space: normal; min-width: 160px; font-weight: 400; color: #ecebe6; }
.tabela-dados thead th { color: #8b8f96; font-weight: 600; font-size: 10.5px; letter-spacing: 0.1em; text-transform: uppercase; }
.votos-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; margin-bottom: 34px; }
.votos-grid > .card-grafico { margin-bottom: 0; }
.voto-nota { font-size: 12px; color: #8b8f96; line-height: 1.6; }
.voto-resumo { display: flex; gap: 20px; padding: 14px 0; border-top: 1px solid #242a30; border-bottom: 1px solid #242a30; }
.voto-resumo strong { display: block; color: #9085e9; font-family: "IBM Plex Mono", monospace; font-size: 26px; font-weight: 500; }
.busca::placeholder { color: #6d7178; }
.busca:focus { border-color: #d9a441 !important; background: #1e2328 !important; }
#tip { display: none; position: fixed; width: max-content; max-width: min(350px, calc(100vw - 16px)); background: #22272c; border: 1px solid #333a41;
  padding: 10px 13px; border-radius: 5px; pointer-events: none; z-index: 90; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
.tip1 { font-size: 12.5px; color: #f5f3ee; line-height: 1.4; margin-bottom: 4px; }
.tip2 { font-family: "IBM Plex Mono", monospace; font-size: 11px; color: #9aa0a8; }
.so-celular { display: none !important; }
.tipd { font-size: 12px; color: #a8a49b; line-height: 1.45; margin-bottom: 5px; text-wrap: pretty; }

/* Celular e tablet estreito. O desenho e escrito em style inline (ver
   painel_app.js), por isso o !important: e a unica forma de uma regra de
   folha vencer um atributo style. */
@media (max-width: 1000px) {
  .tiles { grid-template-columns: repeat(2, minmax(0, 1fr)) !important; }
  .votos-grid { grid-template-columns: 1fr; }
}
@media (max-width: 760px) {
  .pagina { padding: 22px 16px 44px !important; }
  .cab { flex-direction: column; align-items: flex-start !important; gap: 18px !important; }
  .titulo-grande { font-size: 42px !important; }
  .cab-meta { text-align: left !important; gap: 20px !important; flex-wrap: wrap; }
  .abas { gap: 20px !important; overflow-x: auto; }
  .linha-filtro { grid-template-columns: 1fr !important; gap: 6px !important; }
  .linha-filtro > div:first-child { padding-top: 0 !important; }
  .filtros { padding: 16px 14px 18px !important; }
  .so-celular { display: inline-flex !important; }
  .filtros.recolhido .linha-filtro, .filtros.recolhido .filtros-sep { display: none !important; }
  .filtros-acoes, .busca-caixa { width: 100%; }
  .busca-caixa input { width: 100% !important; }
  .tile-valor { font-size: 36px !important; }
  .card-grafico { padding: 18px 14px 16px; }
  .titulo-card { font-size: 22px; }
  .card-cab-lista { padding: 18px 14px 14px !important; }
  .tab-cab { display: none !important; }
  .tab-ap { grid-template-columns: minmax(0, 1fr) auto !important; gap: 8px 12px !important; padding: 14px !important; }
  .tab-ap .c-nat { grid-column: 1 / -1; }
  .tab-ap .c-marcas { grid-column: 1 / -1; order: 3; }
  .tab-ap .c-area, .tab-ap .c-vert { display: none; }
  .tab-hall { grid-template-columns: 22px minmax(0, 1fr) auto !important; gap: 8px 12px !important; padding: 14px !important; }
  .tab-hall .c-nat { grid-column: 2 / -1; order: -1; }
  .tab-hall .c-area, .tab-hall .c-vert, .tab-hall .c-dia { display: none; }
  .corpo-aberto { padding: 8px 14px 24px !important; }
  .ficha-grid { grid-template-columns: 1fr !important; gap: 20px !important; }
  .texto2 { grid-template-columns: 1fr !important; gap: 4px !important; }
  .rodape { flex-direction: column; gap: 10px !important; }
  .secao { margin-top: 6px !important; }
}
"""


def ler(nome: str) -> list[dict]:
    caminho = DIR_MARTS / f"{nome}.parquet"
    if not caminho.exists():
        raise SystemExit(f"ERRO: {caminho} nao existe - rode `python -m hfpapers export` antes.")
    return pq.read_table(caminho).to_pylist()


def iso(d: Any) -> str | None:
    return d.isoformat() if isinstance(d, (dt.date, dt.datetime)) else (d or None)


def _config() -> dict:
    try:
        return yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
    except OSError:
        return {}


def modelos() -> tuple[str, str]:
    """Rodape do painel. Vem do config para nao envelhecer quando o modelo trocar."""
    llm = _config().get("llm", {})
    return (llm.get("estagio_a", {}).get("modelo", "?"),
            llm.get("estagio_b", {}).get("modelo", "?"))


def janela_hall() -> int:
    """Idade, em dias, a partir da qual um paper entra no registro historico.

    Nao e `--dias` e nao e um numero solto: vem de `refresh.janela_morna_dias`,
    o ponto em que o pipeline para de re-consultar as metricas do paper
    (`estagios/refresh.py`). Dali para tras o numero de votos nao muda mais -
    entao e exatamente ali que um ranking pode ser congelado sem mentir.

    Amarrar o hall a essa configuracao, e nao a `--dias`, tem duas consequencias
    boas: `--dias` continua sendo a valvula para encolher o arquivo (baixar o
    valor nao empurra papers para o hall, so mostra menos), e se um dia a janela
    do refresh mudar, o hall segue junto sem ninguem lembrar de mexer aqui.
    """
    valor = _config().get("refresh", {}).get("janela_morna_dias", JANELA_HALL_PADRAO)
    try:
        return max(1, int(valor))
    except (TypeError, ValueError):
        return JANELA_HALL_PADRAO


def periodo(d: dt.date) -> tuple[str, str, dt.date, dt.date]:
    """Trimestre civil de uma data: chave ordenavel, rotulo, primeiro e ultimo dia."""
    t = (d.month - 1) // 3 + 1
    ini = dt.date(d.year, 3 * t - 2, 1)
    proximo = dt.date(d.year + 1, 1, 1) if t == 4 else dt.date(d.year, 3 * t + 1, 1)
    return (f"{d.year}-T{t}", f"{ORDINAL[t]}º trimestre de {d.year}",
            ini, proximo - dt.timedelta(days=1))


def classificacao(triagem: dict, paper: dict) -> dict:
    """Os campos que um aprovado leva para o card e para o filtro.

    `nt` sai sempre - `None` quando o aprovado ainda e do regime anterior -,
    porque o app filtra e conta por ela. Os textos e os links so saem quando
    existem: a janela tem centenas de aprovados, e chave vazia repetida vira
    quilobyte. O rotulo da natureza nao viaja aqui: vem uma vez so, em
    `DADOS.naturezas`, lido de `dim_natureza`. O pre-requisito nao viaja: saiu
    do painel em 21/10/2026 e fica no banco.
    """
    extra: dict = {
        "nt": triagem.get("natureza"),
        "ao": 1 if triagem.get("artefato_aberto") else 0,
    }
    for chave, campo in (("pc", "pratica_contradita"), ("fo", "falta_o_como")):
        if triagem.get(campo):
            extra[chave] = triagem[campo]
    for chave, campo in (("gh", "github_repo"), ("pg", "project_page")):
        if url_segura(paper.get(campo)):
            extra[chave] = paper[campo]
    return extra


def url_segura(url: Any) -> bool:
    """So `http(s)://` vira link. Repositorio e pagina do projeto vem de dado
    externo (HF, abstract), e o painel e publico: um `javascript:` ali seria
    executado no clique."""
    return isinstance(url, str) and re.match(r"https?://", url.strip(), re.IGNORECASE) is not None


def por_voto(papers: list[dict]) -> list[dict]:
    """Ordena por upvotes desc, desempatando por paper_id.

    O desempate nao e capricho: o painel e commitado e empurrado todo dia
    (`gerar_painel.sh`). Sem criterio estavel, dois papers com o mesmo numero de
    votos trocariam de lugar entre rodadas e o commit diario ganharia um diff
    que nao significa nada.
    """
    return sorted(papers, key=lambda p: (-(p.get("upvotes_atual") or 0), p["paper_id"]))


def montar_hall(
    papers: list[dict],
    triagem: dict[str, dict],
    fichas: dict[str, dict],
    par_primario: dict[str, tuple[str, str]],
    vertentes_por_paper: dict[str, list[str]],
    ultimo_voto: dict[str, str | None],
    *,
    corte: dt.date,
) -> list[dict]:
    """Ranking por trimestre entre os papers que ja sairam da janela viva.

    Funcao pura dos Parquet: nao le disco, nao guarda estado. O ranking de um
    trimestre se estabiliza sozinho quando o ultimo dia dele cruza `corte` -
    dali em diante nem entram papers novos no grupo nem os votos se mexem, entao
    nao ha nada a "selar". Enquanto isso nao acontece o trimestre e marcado como
    em consolidacao, porque o top-10 dele ainda muda a cada dia que passa.
    """
    def veredito(pid: str) -> str | None:
        """None = nunca classificado, e isso NAO e o mesmo que `fora`.

        A aba viva pode tratar os dois como um chip cinza; aqui nao da: a lista
        de descartados promete em prosa "a regra e a justificativa que o
        tiraram", e um paper que o Estagio A nunca julgou nao tem nem uma nem
        outra. Ele ficaria no podio com um paragrafo em branco. Entao ele fica
        de fora das duas listas e das duas contagens, e aparece so em `nx`.
        """
        return triagem.get(pid, {}).get("veredito")

    # Contagem sobre TODOS os papers do trimestre, inclusive os que ainda estao
    # na janela viva: senao "10 de 41 aprovados" mentiria enquanto o trimestre
    # esta saindo aos poucos.
    total: Counter[str] = Counter()
    aprovados: Counter[str] = Counter()
    descartados: Counter[str] = Counter()
    rotulos: dict[str, tuple[str, dt.date, dt.date]] = {}
    for p in papers:
        d = p.get("data_hf_daily")
        if not d:
            continue
        chave, rotulo, ini, fim = periodo(d)
        rotulos[chave] = (rotulo, ini, fim)
        total[chave] += 1
        v = veredito(p["paper_id"])
        if v == "aprovado":
            aprovados[chave] += 1
        elif v == "fora":
            descartados[chave] += 1

    saidos: dict[str, list[dict]] = defaultdict(list)
    for p in papers:
        d = p.get("data_hf_daily")
        if d and d < corte:
            saidos[periodo(d)[0]].append(p)

    hall = []
    for chave in sorted(saidos, reverse=True):     # trimestre mais recente primeiro
        rotulo, ini, fim = rotulos[chave]
        grupo = saidos[chave]

        aprov = por_voto([p for p in grupo if veredito(p["paper_id"]) == "aprovado"])
        desc = por_voto([p for p in grupo if veredito(p["paper_id"]) == "fora"])

        entradas_aprov = []
        for p in aprov[:TOPO_APROVADOS]:
            pid = p["paper_id"]
            f = fichas.get(pid, {})
            t = triagem.get(pid, {})
            j, h = justificativa_exibivel(t)
            area, subarea = par_primario.get(pid, (None, None))
            entradas_aprov.append({
                "id": pid,
                "t": p.get("titulo") or "",
                "d": iso(p.get("data_hf_daily")),
                "v": veredito(pid),
                "a": area,
                "sa": subarea,
                "vt": vertentes_por_paper.get(pid, []),
                "u": p.get("upvotes_atual") or 0,
                "uq": ultimo_voto.get(pid),
                "org": p.get("organizacao"),
                "url": p.get("url_hf"),
                # Um aprovado sem ficha e raro mas existe (o Estagio B falhou
                # depois do veredito). Ele fica no ranking - tira-lo faria o
                # top-10 mentir sobre quem foi mais votado - e a linha so nao
                # abre. `f` e o que o app usa para decidir isso.
                "f": 1 if f else 0,
                # cabecalho da decisao (issue #2): por que esta classificacao,
                # independente de a ficha ter sido escrita.
                "j": j,
                "h": h,
                **classificacao(t, p),
                "ach": f.get("achado") or "",
                "imp": f.get("implicacao_pratica") or "",
                "ex": f.get("exemplo_concreto") or "",
                "res": f.get("ressalva") or "",
            })

        entradas_desc = []
        for p in desc[:TOPO_DESCARTADOS]:
            pid = p["paper_id"]
            t = triagem.get(pid, {})
            j, h = justificativa_exibivel(t)
            entradas_desc.append({
                "id": pid,
                "t": p.get("titulo") or "",
                "d": iso(p.get("data_hf_daily")),
                "u": p.get("upvotes_atual") or 0,
                "uq": ultimo_voto.get(pid),
                "org": p.get("organizacao"),
                "url": p.get("url_hf"),
                "rf": t.get("regra_fora"),
                # a justificativa e o contraponto do `achado`: por que o
                # pipeline descartou o que a comunidade votou.
                "j": j,
                "h": h,
            })

        hall.append({
            "per": chave,
            "rot": rotulo,
            "ini": ini.isoformat(),
            "fim": fim.isoformat(),
            "n": total[chave],
            "na": aprovados[chave],
            "nd": descartados[chave],
            "nx": total[chave] - aprovados[chave] - descartados[chave],
            "cons": 1 if fim >= corte else 0,
            "ap": entradas_aprov,
            "de": entradas_desc,
        })
    return hall


# A curva de maturacao so usa idades ate aqui, e cada idade precisa de pelo
# menos MIN_VOTO papers medidos (o corte do minimo fica no app, que recorta).
HORIZONTE_VOTO = 30
JANELA_GANHO = 7


def atencao(medidas: list[tuple[dt.date, int]], dia_hf: Any, fim: dt.date
            ) -> tuple[list | None, list | None]:
    """Pre-agrega as duas leituras de voto do Panorama para um paper.

    `vg` e o ganho na ultima semana: `[dia_ini, votos_ini, dia_fim, votos_fim]`,
    a primeira e a ultima medicao dentro de `fim - 7 .. fim`, so quando ha duas
    medicoes em dias distintos e o total cresceu. Ausencia de snapshot nao vira
    zero, e nada e extrapolado.

    `vm` e a trajetoria normalizada, plana - `[idade, pct, idade, pct, ...]`,
    sem os colchetes de cada par, que eram um terco do peso: o percentual do
    ultimo total observado em cada idade (dias desde o HF Daily) ate o
    horizonte. So sai para quem tem historico elegivel: a primeira medicao no
    dia 0 ou 1, a ultima aos 14 dias ou depois, e total final positivo. Backfill
    tardio nao conta como evidencia de amadurecimento.

    As duas regras sao as que o app aplicava sobre a serie bruta; mudaram de
    lugar para a serie nao precisar viajar.
    """
    ms = sorted(m for m in medidas if m[0] <= fim)
    vg = None
    semana = [m for m in ms if m[0] >= fim - dt.timedelta(days=JANELA_GANHO)]
    if len(semana) >= 2:
        a, b = semana[0], semana[-1]
        if b[1] > a[1] and b[0] != a[0]:
            vg = [a[0].isoformat(), a[1], b[0].isoformat(), b[1]]

    vm = None
    if isinstance(dia_hf, dt.date):
        desde = [m for m in ms if m[0] >= dia_hf]
        if len(desde) >= 2 and (desde[0][0] - dia_hf).days <= 1:
            ultimo = desde[-1]
            if (ultimo[0] - dia_hf).days >= 14 and ultimo[1] > 0:
                vm = []
                for d, u in desde:
                    if (d - dia_hf).days <= HORIZONTE_VOTO:
                        pct = round(u / ultimo[1] * 100, 1)
                        vm += [(d - dia_hf).days, int(pct) if pct == int(pct) else pct]
    return vg, vm


def montar_dados(janela: int, dias_hall: int | None = None) -> tuple[dict, dict]:
    """Extrai de marts/ o objeto `DADOS` que o app le no navegador.

    As chaves sao curtas de proposito: sao milhares de papers e centenas de
    fichas embutidos no HTML, e nome longo repetido vira quilobyte.
    """
    manifest = json.loads((DIR_MARTS / "_manifest.json").read_text(encoding="utf-8"))

    papers = ler("dim_paper")
    triagem = {t["paper_id"]: t for t in ler("fato_triagem")}
    fichas = {f["paper_id"]: f for f in ler("dim_ficha")}

    hoje = dt.date.today()
    corte = hoje - dt.timedelta(days=janela)
    dias_hall = dias_hall if dias_hall is not None else janela_hall()
    corte_hall = hoje - dt.timedelta(days=dias_hall)

    # A janela usa data_hf_daily (a data da operacao diaria), nao data_arxiv.
    #
    # Paper sem triagem fica de FORA da lista, pelo mesmo motivo que o hall ja
    # o deixa de fora das duas listas dele (ver `montar_hall.veredito`): nunca
    # classificado nao e `fora`. A aba viva chegou a dobrar os dois no mesmo
    # chip cinza, e o preco disso aparece no Pareto - um pendente nao tem regra
    # de descarte, entao caia na categoria "regra nao registrada", que existe
    # para medir cobertura que falta nos vereditos LEGADOS. Depois da
    # reclassificacao total essa categoria zera; com pendente dentro ela nunca
    # zeraria, e o sinal que ela carrega (o dia em que voltar a subir) morria.
    #
    # Pendente na janela e rotina, nao falha: o refresh grava paper novo depois
    # que o estagio 3 ja passou, e ele so e classificado na rodada seguinte.
    # Por isso a contagem viaja em `pendentes` e o app a exibe - some da conta
    # de veredito, nao da pagina.
    na_janela_todos = [p for p in papers if p.get("data_hf_daily") and p["data_hf_daily"] >= corte]
    na_janela = [p for p in na_janela_todos if p["paper_id"] in triagem]
    pendentes = len(na_janela_todos) - len(na_janela)
    ids = {p["paper_id"] for p in na_janela}
    ids_hall = {p["paper_id"] for p in papers
                if p.get("data_hf_daily") and p["data_hf_daily"] < corte_hall}
    ids_uteis = ids | ids_hall

    # O par inteiro, e nao so a area: os dois niveis viajam juntos porque
    # sub-area solta nao diz de quem e filha - o mesmo motivo de `taxonomia`
    # aninhar a sub-area sob a area em vez de listar as duas lado a lado.
    # So a primaria. O par secundario existe na ponte e continua no Parquet; ele
    # viajava tambem no payload, em `p.as`, para a matriz area
    # primaria x secundaria - que saiu do painel em 08/09/2026. Sem consumidor,
    # eram 13 KB de nome de area repetido num arquivo distribuido por e-mail.
    par_primario: dict[str, tuple[str, str]] = {}
    for r in ler("ponte_paper_area"):
        if r["paper_id"] in ids_uteis and r.get("is_primaria"):
            par_primario[r["paper_id"]] = (r["area"], r["subarea"])

    # Ordenada pela `ordem`: a dominante e a primeira que o card exibe, e sem a
    # ordenacao aqui a ordem em que o Parquet devolve as linhas decidiria isso.
    vertentes_por_paper: dict[str, list[str]] = defaultdict(list)
    for r in sorted(ler("ponte_paper_vertente"), key=lambda x: (x["paper_id"], x["ordem"])):
        if r["paper_id"] in ids_uteis:
            vertentes_por_paper[r["paper_id"]].append(r["vertente"])

    # Uma passada so: as medicoes de voto de quem esta na janela, e a data da
    # ultima medicao para quem esta no hall (o "votos em" que honra o
    # congelamento do refresh).
    serie: dict[str, list[tuple[dt.date, int]]] = defaultdict(list)
    ultimo_voto: dict[str, str | None] = {}
    for m in sorted(ler("fato_metrica"), key=lambda r: (r["paper_id"], r["data_snapshot"])):
        pid = m["paper_id"]
        u = m.get("upvotes")
        if pid in ids and isinstance(u, int) and u >= 0 and isinstance(m.get("data_snapshot"), dt.date):
            serie[pid].append((m["data_snapshot"], u))
        if pid in ids_hall and u is not None:
            ultimo_voto[pid] = iso(m["data_snapshot"])   # ordenado por data: o ultimo vence

    gerado = manifest.get("gerado_em") or dt.datetime.now().replace(microsecond=0).isoformat()
    try:
        fim_voto = dt.date.fromisoformat(str(gerado)[:10])
    except ValueError:
        fim_voto = hoje

    lista = []
    for p in sorted(na_janela, key=lambda x: (x["data_hf_daily"], x["paper_id"])):
        pid = p["paper_id"]
        t = triagem[pid]
        veredito_p = t["veredito"]
        area, subarea = par_primario.get(pid, (None, None))
        entrada = {
            "id": pid,
            "t": p.get("titulo") or "",
            "d": iso(p.get("data_hf_daily")),
            # As datas do arXiv (`data_arxiv_v1` e `data_arxiv_informada_hf`) nao
            # viajam mais: o unico consumidor era o grafico de defasagem, que saiu
            # do painel em 08/09/2026. Elas continuam no banco, que e
            # de onde a auditoria de datas le.
            "v": veredito_p,
            "rf": t.get("regra_fora"),
            "a": area,
            "sa": subarea,
            "vt": vertentes_por_paper.get(pid, []),
            # Repositorio no HF, e nao "artefato aberto": e a coordenada da
            # dispersao upvotes x stars, que vale tambem para os descartados.
            # O artefato aberto do ADR 004 (evidencia + `liberado`) e `ao`.
            "oa": 1 if p.get("github_repo") else 0,
            "pp": 1 if p.get("tem_project_page") else 0,
            "u": p.get("upvotes_atual") or 0,
            "c": p.get("comentarios_atual") or 0,
            "gs": p.get("github_stars_atual") or 0,
            "org": p.get("organizacao"),
            "na": p.get("qtd_autores") or 0,
            "nv": p.get("qtd_autores_verificados") or 0,
            "url": p.get("url_hf"),
            "f": 1 if pid in fichas else 0,
        }
        # As duas medidas de voto do Panorama, ja pre-agregadas: a serie
        # inteira de snapshots era 1,7 MB do payload e o app so lia dela o
        # ganho da ultima semana e a curva de maturacao.
        vg, vm = atencao(serie.get(pid, []), p.get("data_hf_daily"), fim_voto)
        if vg:
            entrada["vg"] = vg
        if vm:
            entrada["vm"] = vm
        # cabecalho da decisao (issue #2) e classificacao do ADR 004: so os
        # aprovados os renderizam, entao so eles carregam `j`/`h`,
        # natureza, textos e links - um `fora` com essas chaves vazias viajaria
        # em centenas de papers da janela sem ninguem para le-las.
        if veredito_p == "aprovado":
            entrada["j"], entrada["h"] = justificativa_exibivel(t)
            entrada.update(classificacao(t, p))
        lista.append(entrada)

    hall = montar_hall(
        papers, triagem, fichas, par_primario, vertentes_por_paper, ultimo_voto,
        corte=corte_hall,
    )

    # Ordenado aqui porque o export faz `SELECT * FROM dim_area` sem ORDER BY:
    # a ordem que o Parquet devolve nao e garantida entre rodadas, e o painel e
    # commitado e empurrado todo dia. Sem isto, uma fusao de rotulo bastaria
    # para o commit diario ganhar um bloco reordenado que nao significa nada.
    areas_todas = sorted(ler("dim_area"), key=lambda a: a["area"])
    areas_raiz = [a for a in areas_todas if not a.get("area_pai")]

    modelo_a, modelo_b = modelos()
    dados = {
        "gerado": gerado,
        "modeloA": modelo_a,
        "modeloB": modelo_b,
        "janela": janela,
        "pendentes": pendentes,
        "diasHall": dias_hall,
        # o corte efetivo pode vir de --dias-hall, mas a frase que explica o
        # congelamento fala do refresh - e o refresh nao muda por flag de CLI
        "diasRefresh": janela_hall(),
        # So a raiz: `DADOS.areas` alimenta o filtro ÁREA, e o filtro compara
        # com `p.a`, que e sempre area raiz. Desde que `dim_area` ganhou dois
        # niveis (ticket 02) mandar a tabela inteira punha 64 sub-areas no menu,
        # todas filtrando para o vazio. A sub-area continua sem faceta propria -
        # ela acompanha o paper em `p.sa` e agora tambem tem vista propria no
        # card "Área primária", que a agrega no navegador.
        "areas": [
            {"a": a["area"], "def": a.get("definicao") or ""}
            for a in areas_raiz
        ],
        # Sub-areas para o filtro SUB-ÁREA e os tooltips da vista "Sub-áreas".
        # Mapa plano porque a chave basta: os 64 nomes sao unicos entre si na
        # `dim_area` inteira (ela e uma tabela so, `area` e a PK), entao nao ha
        # como duas areas terem sub-area homonima. As 64 viajam, e nao so as do
        # recorte, para o arquivo diario nao mudar de tamanho conforme o dia -
        # sao 9,1 KB num arquivo de ~2,5 MB.
        "subdef": {
            a["area"]: a.get("definicao") or ""
            for a in areas_todas if a.get("area_pai")
        },
        # As 10 vertentes com a definicao, para o filtro VERTENTE e para o
        # tooltip da vista "Vertentes". Alfabetica, como tudo que e ordenado
        # aqui e nao no app: a ordem de exibicao e decisao de desenho e mora em
        # `painel_app.js`; esta aqui so precisa ser estavel entre rodadas.
        "vertentes": [
            {"v": v["vertente"], "def": v.get("definicao") or ""}
            for v in sorted(ler("dim_vertente"), key=lambda x: x["vertente"])
        ],
        # A natureza do ADR 004, na ordem do banco. Rotulo e definicao viajam
        # uma vez, aqui.
        "naturezas": [
            {"k": n["natureza"], "r": n.get("rotulo") or n["natureza"],
             "def": n.get("definicao") or ""}
            for n in sorted(ler("dim_natureza"), key=lambda x: (x.get("ordem") or 0, x["natureza"]))
        ],
        "papers": lista,
        "fichas": [
            {
                "p": pid,
                "ach": f.get("achado") or "",
                "imp": f.get("implicacao_pratica") or "",
                "ex": f.get("exemplo_concreto") or "",
                "res": f.get("ressalva") or "",
            }
            for pid, f in fichas.items() if pid in ids
        ],
        "hall": hall,
    }
    return dados, manifest


def _json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def _embutivel(texto: str, *, codigo: bool = False) -> str:
    """Escapa o que fecharia (ou desviaria) a tag <script> no meio do texto.

    JSON: todo `<` vira `\\u003c`, que e valido em JSON e em JS. Cobre o
    `</script>` de um titulo e tambem `<!--` seguido de `<script`, que poe o
    tokenizador do HTML em "script data double escaped" e engoliria o resto da
    pagina. Codigo: so `</script`, porque um `<` generico aparece em
    comparacao e em regex literal (`/</g`) e o escape os quebraria.
    """
    if codigo:
        return re.sub(r"</(script)", r"<\\/\1", texto, flags=re.IGNORECASE)
    return texto.replace("<", "\\u003c")


def resumo_texto(dados: dict) -> str:
    """Uma frase com os numeros do dia, para a meta description e o <noscript>.

    E o que um buscador ou a previa de um link compartilhado mostram - o
    painel em si so existe depois do JavaScript.
    """
    papers = dados["papers"]
    aprovados = sum(1 for p in papers if p["v"] == "aprovado")
    return (f"{len(papers)} papers do Hugging Face Daily Papers dos últimos {dados['janela']} dias, "
            f"triados por LLM: {aprovados} aprovados, com ficha de leitura, natureza da afirmação, "
            f"área e vertente. Atualizado em {str(dados['gerado'])[:10]}.")


def versao(conteudo: str) -> str:
    """Hash curto do conteudo, para o `?v=` furar o cache do navegador e do
    CDN do Pages exatamente quando o arquivo muda - inclusive num `--force`
    do mesmo run depois de uma mudanca no formato dos dados."""
    return hashlib.sha256(conteudo.encode("utf-8")).hexdigest()[:10]


def documento(dados: dict, *, embutido: bool, versoes: dict[str, str] | None = None) -> str:
    """O `index.html`. Embutido leva dados, fichas e ECharts dentro dele;
    senao aponta para os arquivos irmaos, cada um com o `?v=` do proprio
    conteudo (`versoes`, nome -> hash)."""
    app = APP_JS.read_text(encoding="utf-8")
    resumo = resumo_texto(dados)
    def esc(t: str) -> str:
        return (t.replace("&", "&amp;").replace('"', "&quot;")
                .replace("<", "&lt;").replace(">", "&gt;"))
    og_url = f'<meta property="og:url" content="{esc(URL_PUBLICA)}">\n' if URL_PUBLICA else ""

    if embutido:
        fichas = dados["fichas"]
        leve = {k: v for k, v in dados.items() if k != "fichas"}
        carga = (f"<script>{_embutivel(ECHARTS_JS.read_text(encoding='utf-8'), codigo=True)}</script>\n"
                 f"<script>var DADOS={_embutivel(_json(leve))};"
                 f"var FICHAS={_embutivel(_json(fichas))};</script>")
    else:
        v = {k: esc(x) for k, x in (versoes or {}).items()}
        carga = (f'<script>var PAINEL_ARQUIVOS={{dados:"dados.json?v={v.get("dados.json", "")}",'
                 f'fichas:"fichas.json?v={v.get("fichas.json", "")}"}};</script>\n'
                 f'<script src="echarts.painel.min.js?v={v.get("echarts.painel.min.js", "")}"></script>')

    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Daily Papers, triados · painel</title>
<meta name="description" content="{esc(resumo)}">
<meta property="og:type" content="website">
<meta property="og:title" content="Daily Papers, triados">
<meta property="og:description" content="{esc(resumo)}">
{og_url}<meta name="theme-color" content="#0d0f11">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,300;0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,300;1,6..72,400&family=Instrument+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>{CSS}</style></head>
<body>
<main id="painel" aria-live="polite"><div class="carregando">
<h1>Daily Papers, triados</h1>
<p>{esc(resumo)}</p>
<noscript><p>O painel interativo precisa de JavaScript.</p></noscript>
</div></main>
<div id="tip" role="tooltip"></div>
{carga}
<script>{_embutivel(app, codigo=True)}</script>
</body></html>"""


def montar(janela: int, dias_hall: int | None = None, *, embutido: bool = False
           ) -> tuple[dict[str, str], dict]:
    """Os arquivos do painel, nome -> conteudo.

    Embutido e um so, `index.html`. Em pasta sao quatro: a pagina, os dados da
    primeira pintura, as fichas (buscadas depois) e o ECharts.
    """
    dados, manifest = montar_dados(janela, dias_hall)
    if embutido:
        return {"index.html": documento(dados, embutido=True)}, manifest
    return arquivos_da_pasta(dados), manifest


def arquivos_da_pasta(dados: dict) -> dict[str, str]:
    """A pasta do site; o `index.html` aponta para os irmaos pelo hash deles."""
    leve = {k: v for k, v in dados.items() if k != "fichas"}
    irmaos = {
        "dados.json": _json(leve),
        "fichas.json": _json(dados["fichas"]),
        "echarts.painel.min.js": ECHARTS_JS.read_text(encoding="utf-8"),
    }
    versoes = {nome: versao(conteudo) for nome, conteudo in irmaos.items()}
    return {"index.html": documento(dados, embutido=False, versoes=versoes), **irmaos}


def escrever(arquivos: dict[str, str], destino: Path) -> int:
    """Grava atomicamente, arquivo a arquivo. `destino` terminado em .html e o
    arquivo unico; qualquer outro e a pasta. Devolve o total em bytes."""
    total = 0
    if destino.suffix == ".html":
        alvos = {destino: arquivos["index.html"]}
    else:
        alvos = {destino / nome: conteudo for nome, conteudo in arquivos.items()}
    for caminho, conteudo in alvos.items():
        caminho.parent.mkdir(parents=True, exist_ok=True)
        tmp = caminho.with_name(caminho.name + ".tmp")
        tmp.write_text(conteudo, encoding="utf-8")
        os.replace(tmp, caminho)   # atomico: ninguem le um arquivo pela metade
        total += len(conteudo.encode("utf-8"))
    return total


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Gera o painel HTML estatico de marts/.")
    ap.add_argument("--dias", type=int, default=JANELA_PADRAO,
                    help=f"Janela em dias da aba viva (padrao {JANELA_PADRAO}). Segura o tamanho "
                         "do arquivo. Nao afeta a aba historica, que segue refresh.janela_morna_dias.")
    ap.add_argument("--destino", type=Path, default=DESTINO_PADRAO,
                    help=f"Pasta de saida (padrao {DESTINO_PADRAO}). Terminado em .html gera um "
                         "arquivo unico com dados e ECharts embutidos, que abre offline - e o "
                         "formato das previas.")
    ap.add_argument("--dias-hall", type=int, default=None, dest="dias_hall",
                    help="Sobrescreve o corte da aba historica, que por padrao vem de "
                         "refresh.janela_morna_dias. Existe para inspecionar a aba antes de o "
                         "primeiro trimestre fechar - nao use na geracao diaria: abaixo da janela "
                         "do refresh os votos do hall ainda estao se mexendo. Aceita valor "
                         "negativo de proposito: --dias-hall=-30 joga o corte para o futuro e e a "
                         "unica forma de ver um trimestre ja consolidado enquanto o corrente nao "
                         "terminou (com valor positivo o corte nunca passa de hoje, entao "
                         "`fim >= corte` mantem o trimestre marcado como em consolidacao).")
    ap.add_argument("--marts", type=Path, default=None,
                    help="Le os Parquet de outro diretorio (previa sobre a copia do piloto). "
                         "So vale junto com --destino: o carimbo de run_id e do marts/ do repo.")
    ap.add_argument("--force", action="store_true",
                    help="Regera mesmo se o run_id nao mudou.")
    return ap


def main() -> int:
    global DIR_MARTS
    args = _parser().parse_args()
    if args.marts is not None:
        if args.destino == DESTINO_PADRAO:
            print("ERRO: --marts so com --destino: a previa nao publica.", file=sys.stderr)
            return 2
        DIR_MARTS = args.marts

    manifest_path = DIR_MARTS / "_manifest.json"
    if not manifest_path.exists():
        print("ERRO: marts/_manifest.json nao existe - o export ainda nao rodou.", file=sys.stderr)
        return 2

    run_id = json.loads(manifest_path.read_text(encoding="utf-8")).get("run_id")
    anterior = CARIMBO.read_text(encoding="utf-8").strip() if CARIMBO.exists() else None

    # A trava que torna o disparo repetido do WatchPaths inofensivo.
    if run_id and run_id == anterior and not args.force and args.marts is None:
        print(f"sem novidade: painel ja gerado para {run_id} (use --force para regerar)")
        return 0

    embutido = args.destino.suffix == ".html"
    arquivos, _ = montar(args.dias, args.dias_hall, embutido=embutido)
    total = escrever(arquivos, args.destino)

    # So carimba quando escreveu o painel publicado. Um `--destino /tmp/x.html`
    # que carimbasse faria a geracao seguinte do painel de verdade sair em no-op
    # - a rede de seguranca das 08:30 e o redisparo do WatchPaths se calariam, e
    # o painel do dia nao seria gerado.
    if run_id and args.destino == DESTINO_PADRAO:
        CARIMBO.write_text(run_id, encoding="utf-8")

    kb = total / 1024
    print(f"painel: {args.destino} ({kb:.0f} KB em {len(arquivos)} arquivo(s), "
          f"janela {args.dias}d, run_id {run_id})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
