"""Gera o painel HTML estatico a partir dos Parquet de marts/.

Nao e a interface de leitura do projeto - o Power BI continua sendo. Este
painel existe para distribuicao: um arquivo unico, sem dependencia de rede,
que abre em qualquer visualizador de HTML (Teams, e-mail, navegador).

O desenho e o mesmo do Artifact "Painel Daily Papers", que nasceu como
artboard da Claude Design. Aquele arquivo so roda dentro do runtime do canvas;
`scripts/painel_app.js` e o porte do mesmo layout para JS de navegador. Este
script nao desenha nada: extrai os dados, serializa em `DADOS` e embute o app.

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

3. A aba historica (`hall`) guarda, por trimestre de publicacao, os 10
   aprovados mais votados com a ficha inteira e os 10 descartados mais votados
   com a regra e a justificativa. Ela NAO preserva dado nenhum contra perda:
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
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import yaml

RAIZ = Path(__file__).resolve().parent.parent
DIR_MARTS = RAIZ / "marts"
DESTINO_PADRAO = RAIZ / "relatorios" / "painel.html"
CARIMBO = RAIZ / "marts" / ".painel_run_id"
APP_JS = Path(__file__).resolve().parent / "painel_app.js"
CONFIG = RAIZ / "config.yaml"

JANELA_PADRAO = 90
JANELA_HALL_PADRAO = 90

# Dez e dez, por decisao editorial. O custo por entrada e assimetrico e e o que
# justifica os dois tamanhos: um aprovado com a ficha inteira pesa ~2,5 KB; um
# descartado com regra + justificativa pesa ~0,7 KB. Um trimestre inteiro
# acrescenta ~32 KB ao arquivo, ~130 KB por ano.
TOPO_APROVADOS = 10
TOPO_DESCARTADOS = 10

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
    descartados), que assim nao divergem na regra.

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
body { margin: 0; background: #0d0f11; font-family: "Instrument Sans", system-ui, sans-serif; -webkit-font-smoothing: antialiased; }
a { color: #d9a441; text-decoration: none; border-bottom: 1px solid rgba(217,164,65,0.3); }
a:hover { color: #ecc478; border-bottom-color: #ecc478; }
.chip { transition: background 120ms ease, border-color 120ms ease, color 120ms ease; cursor: pointer; user-select: none; }
.chip:hover { background: #23282e !important; border-color: #414a53 !important; color: #ecebe6 !important; }
.chip-on:hover { filter: brightness(1.08); }
.aba { transition: color 120ms ease, border-color 120ms ease; cursor: pointer; user-select: none; }
.aba:hover { color: #ecebe6 !important; }
.mark { transition: opacity 120ms ease, transform 120ms ease; cursor: pointer; }
.mark:hover { opacity: 1 !important; transform: scale(1.35); }
.bar { transition: filter 120ms ease; cursor: pointer; }
.bar:hover { filter: brightness(1.22) saturate(1.1); }
/* O segmento das vistas de composicao nao usa `.bar` por dois motivos. Ele nao
   e clicavel - quem filtra area e o rotulo da linha -, entao `cursor: pointer`
   prometeria um clique que nao existe. E o realce por brilho sobe o L* em 8 a
   12 pontos, que naquela rampa e um passo e meio: no exato momento em que o
   leitor tenta casar a fatia com o verbete da legenda, a fatia passaria a ter
   a cor da vizinha. O realce aqui e um contorno, que nao mexe na cor. */
.seg { transition: box-shadow 120ms ease; }
.seg:hover { box-shadow: inset 0 0 0 1.5px #f5f3ee; }
.row { transition: background 120ms ease; cursor: pointer; }
.row:hover { background: #191d21; }
.mais { color: #d9a441; border-bottom: 1px solid rgba(217,164,65,0.3); transition: color 120ms ease, border-color 120ms ease; cursor: pointer; }
.mais:hover { color: #ecc478; border-bottom-color: #ecc478; }
.card { background: #16191c; border: 1px solid #242a30; border-radius: 5px; }
.regras-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; margin-bottom: 34px; align-items: stretch; }
.regras-grid > .card { margin-bottom: 0 !important; min-width: 0; height: 450px; box-sizing: border-box; }
.regras-scroll { overflow-y: auto; min-height: 0; padding-right: 10px; scrollbar-gutter: stable; scrollbar-color: #6b7480 #1d2226; }
.regras-scroll:focus-visible { outline: 1px solid #d9a441; outline-offset: 4px; }
.votos-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; margin-bottom: 14px; }
.voto-card { padding: 22px 24px; min-width: 0; display: flex; flex-direction: column; gap: 16px; }
.voto-titulo { font-family: Newsreader, Georgia, serif; font-size: 26px; color: #f5f3ee; line-height: 1.15; }
.voto-nota { font-size: 12px; color: #8b8f96; line-height: 1.6; }
.voto-legenda { display: flex; align-items: center; flex-wrap: wrap; gap: 7px; font-size: 11.5px; color: #a8a49b; margin-top: 7px; }
.voto-legenda > span { width: 10px; height: 8px; display: inline-block; border-radius: 2px; }
.voto-ranking { display: flex; flex-direction: column; gap: 12px; overflow-y: auto; padding-right: 10px; scrollbar-color: #6b7480 #1d2226; }
.voto-item { display: grid; grid-template-columns: minmax(0, 1fr) 66px; gap: 14px; align-items: center; border: 0; color: #ecebe6; }
.voto-item:hover { border: 0; }
.voto-item-miolo { min-width: 0; }
.voto-item-cab { font-size: 12.5px; line-height: 1.45; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.voto-item-ganho { font-family: "IBM Plex Mono", monospace; font-size: 12px; font-weight: 400; text-align: right; color: #ecebe6; }
.voto-item-detalhe { font-size: 10.5px; color: #8b8f96; }
.voto-tracao { position: relative; height: 16px; margin: 4px 6px; }
.voto-tracao-linha { position: absolute; top: 7px; height: 2px; opacity: 0.45; }
.voto-tracao-inicio, .voto-tracao-fim { position: absolute; top: 50%; transform: translate(-50%, -50%); border-radius: 50%; box-sizing: border-box; }
.voto-tracao-inicio { width: 8px; height: 8px; background: #16191c; border: 1.5px solid; }
.voto-tracao-fim { width: 10px; height: 10px; }
.voto-resumo { display: flex; gap: 20px; padding: 14px 0; border-top: 1px solid #242a30; border-bottom: 1px solid #242a30; }
.voto-resumo strong { display: block; color: #9085e9; font-family: "IBM Plex Mono", monospace; font-size: 26px; font-weight: 500; }
@media (max-width: 800px) { .votos-grid { grid-template-columns: 1fr; } .voto-card { padding: 20px 16px; } }
@media (max-width: 800px) { .regras-grid { grid-template-columns: 1fr; } }
.busca::placeholder { color: #6d7178; }
.busca:focus { border-color: #d9a441 !important; background: #1e2328 !important; }
#tip { display: none; position: fixed; width: max-content; max-width: min(350px, calc(100vw - 16px)); background: #22272c; border: 1px solid #333a41;
  padding: 10px 13px; border-radius: 5px; pointer-events: none; z-index: 90; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
#tip .tip1 { font-size: 12.5px; color: #f5f3ee; line-height: 1.4; margin-bottom: 4px; }
#tip .tip2 { font-family: "IBM Plex Mono", monospace; font-size: 11px; color: #9aa0a8; }
#tip .tipd { font-size: 12px; color: #a8a49b; line-height: 1.45; margin-bottom: 5px; text-wrap: pretty; }
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


def criterios_e_fronteira(triagem: dict, criterios: list[str]) -> dict:
    """Os dois campos que a linha do veredito da ficha precisa, para um aprovado.

    `cr` sempre sai (lista vazia inclusive: aprovado de linha antiga, anterior a
    `criterios_veredito`, existe e nao tem criterio nenhum); `fc` so quando ha
    decisao de fronteira COM contraparte gravada, senao o app imprimiria
    "fronteira: quase null". O selo generico de fronteira continua saindo pelo
    `fr`, que e independente deste par.

    Os enums nao viram rotulo aqui: o mapa enum -> portugues mora em
    `painel_app.js`, que e o unico consumidor (a ficha e o grafico "por que o
    pipeline aprova"). Um so mapa, do lado de quem desenha - traze-lo para ca
    duplicaria 16 strings dentro de `DADOS` sem ninguem em Python para le-las.
    """
    extra: dict = {"cr": criterios}
    contraparte = triagem.get("fronteira_contraparte")
    if triagem.get("decisao_fronteira") and contraparte:
        extra["fc"] = contraparte
    return extra


def por_voto(papers: list[dict]) -> list[dict]:
    """Ordena por upvotes desc, desempatando por paper_id.

    O desempate nao e capricho: `painel.html` e commitado e empurrado todo dia
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
    ultimo_voto: dict[str, str],
    criterios_por_paper: dict[str, list[str]],
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
        if v in ("estrito", "amplo"):
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

        aprov = por_voto([p for p in grupo if veredito(p["paper_id"]) in ("estrito", "amplo")])
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
                # cabecalho da decisao (issue #2): por que o veredito saiu
                # estrito/amplo, independente de a ficha ter sido escrita.
                "j": j,
                "h": h,
                "fr": 1 if t.get("decisao_fronteira") else 0,
                **criterios_e_fronteira(t, criterios_por_paper.get(pid, [])),
                "ach": f.get("achado") or "",
                "pn": f.get("padrao_nome") or "",
                "pm": f.get("padrao_mecanismo") or "",
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


def montar_dados(janela: int, dias_hall: int | None = None) -> tuple[dict, dict]:
    """Extrai de marts/ o objeto `DADOS` que o app le no navegador.

    As chaves sao curtas de proposito: sao ~300 papers e ~100 fichas embutidos
    no HTML, e nome longo repetido 300 vezes vira quilobyte de distribuicao.
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
    # So a primaria. O par secundario existe na ponte e continua no Parquet para
    # o Power BI; ele viajava tambem no payload, em `p.as`, para a matriz area
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

    # Criterios de veredito por paper. Ordenados e sem repeticao pelo mesmo
    # motivo de `por_voto` desempatar: o painel e commitado todo dia e a ordem
    # em que o Parquet devolve as linhas nao e garantida entre rodadas - sem
    # isso o commit diario ganharia um diff que nao significa nada. A ordem
    # alfabetica basta aqui: quem ordena para exibir e o app, que tem a lista
    # canonica (estrito antes de amplo) do `schemas.py`.
    criterios_brutos: dict[str, set[str]] = defaultdict(set)
    for r in ler("ponte_paper_criterio"):
        if r["paper_id"] in ids_uteis:
            criterios_brutos[r["paper_id"]].add(r["criterio"])
    criterios_por_paper = {pid: sorted(cs) for pid, cs in criterios_brutos.items()}

    # Uma passada so: a serie completa para quem esta na janela, e a data da
    # ultima medicao para quem esta no hall (o "votos em" que honra o
    # congelamento do refresh).
    serie: dict[str, list] = defaultdict(list)
    ultimo_voto: dict[str, str] = {}
    for m in sorted(ler("fato_metrica"), key=lambda r: (r["paper_id"], r["data_snapshot"])):
        pid = m["paper_id"]
        if pid in ids:
            serie[pid].append(
                [iso(m["data_snapshot"]), m.get("upvotes"), m.get("comentarios"), m.get("github_stars")]
            )
        if pid in ids_hall and m.get("upvotes") is not None:
            ultimo_voto[pid] = iso(m["data_snapshot"])   # ordenado por data: o ultimo vence

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
            # do painel em 08/09/2026. Elas continuam no banco e no Parquet, que e
            # de onde a auditoria de datas le.
            "v": veredito_p,
            "rf": t.get("regra_fora"),
            "art": t.get("tem_artefato_nomeado"),
            "a": area,
            "sa": subarea,
            "vt": vertentes_por_paper.get(pid, []),
            "oa": 1 if p.get("tem_codigo_aberto") else 0,
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
        # cabecalho da decisao (issue #2): so os aprovados o renderizam, entao
        # so eles carregam `j`/`h` - a janela tem ~2500 papers e a maioria e
        # `fora`, e essa e a restricao de peso que a issue pede para respeitar.
        # `cr`/`fc`/`fr` seguem a mesma regra e pelo mesmo motivo: criterio de
        # veredito so existe para quem foi aprovado, e o selo de fronteira e
        # desenhado pelo mesmo cabecalho - um `fr` num `fora` viajava em ~315
        # papers da janela sem ninguem para le-lo.
        if veredito_p != "fora":
            entrada["j"], entrada["h"] = justificativa_exibivel(t)
            entrada["fr"] = 1 if t.get("decisao_fronteira") else 0
            entrada.update(criterios_e_fronteira(t, criterios_por_paper.get(pid, [])))
        lista.append(entrada)

    hall = montar_hall(
        papers, triagem, fichas, par_primario, vertentes_por_paper, ultimo_voto,
        criterios_por_paper,
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
        "gerado": manifest.get("gerado_em") or dt.datetime.now().replace(microsecond=0).isoformat(),
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
        "papers": lista,
        "fichas": [
            {
                "p": pid,
                "ach": f.get("achado") or "",
                "pn": f.get("padrao_nome") or "",
                "pm": f.get("padrao_mecanismo") or "",
                "imp": f.get("implicacao_pratica") or "",
                "ex": f.get("exemplo_concreto") or "",
                "res": f.get("ressalva") or "",
            }
            for pid, f in fichas.items() if pid in ids
        ],
        "serie": dict(serie),
        "hall": hall,
    }
    return dados, manifest


def montar(janela: int, dias_hall: int | None = None) -> tuple[str, dict]:
    dados, manifest = montar_dados(janela, dias_hall)
    app = APP_JS.read_text(encoding="utf-8")

    # `</` escapado: um titulo de paper com "</script>" fecharia a tag e o
    # painel viraria texto solto no meio da pagina.
    blob = json.dumps(dados, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

    doc = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Painel Daily Papers</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,300;0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,300;1,6..72,400&family=Instrument+Serif:ital@0;1&family=Instrument+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>{CSS}</style></head>
<body>
<div id="painel"></div>
<div id="tip"></div>
<script>var DADOS={blob};</script>
<script>{app}</script>
</body></html>"""
    return doc, manifest


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Gera o painel HTML estatico de marts/.")
    ap.add_argument("--dias", type=int, default=JANELA_PADRAO,
                    help=f"Janela em dias da aba viva (padrao {JANELA_PADRAO}). Segura o tamanho "
                         "do arquivo. Nao afeta a aba historica, que segue refresh.janela_morna_dias.")
    ap.add_argument("--destino", type=Path, default=DESTINO_PADRAO,
                    help=f"Arquivo de saida (padrao {DESTINO_PADRAO}).")
    ap.add_argument("--dias-hall", type=int, default=None, dest="dias_hall",
                    help="Sobrescreve o corte da aba historica, que por padrao vem de "
                         "refresh.janela_morna_dias. Existe para inspecionar a aba antes de o "
                         "primeiro trimestre fechar - nao use na geracao diaria: abaixo da janela "
                         "do refresh os votos do hall ainda estao se mexendo. Aceita valor "
                         "negativo de proposito: --dias-hall=-30 joga o corte para o futuro e e a "
                         "unica forma de ver um trimestre ja consolidado enquanto o corrente nao "
                         "terminou (com valor positivo o corte nunca passa de hoje, entao "
                         "`fim >= corte` mantem o trimestre marcado como em consolidacao).")
    ap.add_argument("--force", action="store_true",
                    help="Regera mesmo se o run_id nao mudou.")
    return ap


def main() -> int:
    args = _parser().parse_args()

    manifest_path = DIR_MARTS / "_manifest.json"
    if not manifest_path.exists():
        print("ERRO: marts/_manifest.json nao existe - o export ainda nao rodou.", file=sys.stderr)
        return 2

    run_id = json.loads(manifest_path.read_text(encoding="utf-8")).get("run_id")
    anterior = CARIMBO.read_text(encoding="utf-8").strip() if CARIMBO.exists() else None

    # A trava que torna o disparo repetido do WatchPaths inofensivo.
    if run_id and run_id == anterior and not args.force:
        print(f"sem novidade: painel ja gerado para {run_id} (use --force para regerar)")
        return 0

    doc, _ = montar(args.dias, args.dias_hall)

    args.destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.destino.with_suffix(".html.tmp")
    tmp.write_text(doc, encoding="utf-8")
    os.replace(tmp, args.destino)   # atomico: ninguem le um arquivo pela metade

    # So carimba quando escreveu o painel publicado. Um `--destino /tmp/x.html`
    # que carimbasse faria a geracao seguinte do painel de verdade sair em no-op
    # - a rede de seguranca das 08:30 e o redisparo do WatchPaths se calariam, e
    # o painel do dia nao seria gerado.
    if run_id and args.destino == DESTINO_PADRAO:
        CARIMBO.write_text(run_id, encoding="utf-8")

    kb = len(doc.encode("utf-8")) / 1024
    print(f"painel: {args.destino} ({kb:.0f} KB, janela {args.dias}d, run_id {run_id})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
