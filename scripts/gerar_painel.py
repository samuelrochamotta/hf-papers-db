"""Gera o painel HTML estatico a partir dos Parquet de marts/.

Nao e a interface de leitura do projeto - o Power BI continua sendo. Este
painel existe para distribuicao: um arquivo unico, sem dependencia de rede,
que abre em qualquer visualizador de HTML (Teams, e-mail, navegador).

Tres decisoes que valem explicacao:

1. Le `marts/_manifest.json` e nao roda de novo se o `run_id` for o mesmo da
   ultima geracao. O gatilho do launchd e `WatchPaths`, que pode disparar mais
   de uma vez para a mesma escrita; a trava de `run_id` torna o disparo extra
   um no-op em vez de trabalho repetido.

2. Recorta uma janela de dias (padrao 90). Sem isso o arquivo cresce para
   sempre: sao ~28 papers/dia entrando na base. A serie historica completa
   continua nos Parquet - o painel e a vitrine, nao o arquivo morto.
   Ordem de grandeza medida: ~3,8 KB por card aprovado. Com a janela cheia de
   90 dias isso projeta ~1.000 cards / ~4 MB. Se ficar pesado para distribuir,
   `--dias` e o botao para girar.

3. So pyarrow. O env `digest-hf` nao tem pandas nem jinja2, e um painel de
   distribuicao nao justifica dependencia nova.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

RAIZ = Path(__file__).resolve().parent.parent
DIR_MARTS = RAIZ / "marts"
DESTINO_PADRAO = RAIZ / "relatorios" / "painel.html"
CARIMBO = RAIZ / "marts" / ".painel_run_id"

JANELA_PADRAO = 90

# Mesma paleta do painel que ja foi aprovado como Artifact - continuidade
# visual para quem ja viu aquele.
CSS = """
*{box-sizing:border-box}
body{margin:0;background:#0d0f11;color:#ecebe6;
  font-family:"Instrument Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;
  -webkit-font-smoothing:antialiased;line-height:1.5}
a{color:#d9a441;text-decoration:none;border-bottom:1px solid rgba(217,164,65,.3)}
a:hover{color:#ecc478;border-bottom-color:#ecc478}
.wrap{max-width:1080px;margin:0 auto;padding:40px 28px 72px}
h1{font-family:"Newsreader",Georgia,serif;font-weight:400;font-size:30px;margin:0 0 4px;letter-spacing:-.01em}
.sub{color:#8b9199;font-size:13px;margin:0 0 30px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:14px}
.kpi{background:#16191c;border:1px solid #242a30;border-radius:5px;padding:14px 16px}
.kpi .n{font-family:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
  font-size:26px;font-weight:500;letter-spacing:-.02em}
.kpi .r{color:#8b9199;font-size:11px;text-transform:uppercase;letter-spacing:.07em;margin-top:3px}
.barra{display:flex;align-items:flex-end;gap:2px;height:52px;background:#16191c;
  border:1px solid #242a30;border-radius:5px;padding:8px 10px;margin-bottom:26px}
.barra i{flex:1;background:#3a4650;border-radius:1px;min-height:2px;display:block}
.barra i.tem{background:#d9a441}
.ctrl{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:18px}
.busca{flex:1;min-width:200px;background:#16191c;border:1px solid #242a30;border-radius:5px;
  color:#ecebe6;padding:9px 12px;font-size:13px;font-family:inherit}
.busca:focus{outline:none;border-color:#d9a441;background:#1e2328}
.busca::placeholder{color:#6d7178}
.chip{background:#16191c;border:1px solid #242a30;border-radius:20px;color:#8b9199;
  padding:7px 14px;font-size:12px;cursor:pointer;user-select:none;font-family:inherit;
  transition:background 120ms,border-color 120ms,color 120ms}
.chip:hover{background:#23282e;border-color:#414a53;color:#ecebe6}
.chip[aria-pressed="true"]{background:#d9a441;border-color:#d9a441;color:#0d0f11;font-weight:600}
.dia{color:#6d7178;font-size:11px;text-transform:uppercase;letter-spacing:.09em;
  margin:26px 0 10px;padding-bottom:6px;border-bottom:1px solid #1e2328}
.card{background:#16191c;border:1px solid #242a30;border-radius:5px;padding:16px 18px;margin-bottom:9px}
.card h2{font-size:15px;font-weight:600;margin:0 0 8px;line-height:1.35}
.meta{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:9px;font-size:11px}
.tag{border-radius:3px;padding:2px 7px;font-weight:600;text-transform:uppercase;letter-spacing:.05em;font-size:10px}
.estrito{background:#d9a441;color:#0d0f11}
.amplo{background:#2f4858;color:#9dc3d8}
.up{color:#8b9199;font-family:"IBM Plex Mono",ui-monospace,Menlo,monospace}
.fronteira{color:#b8763a;border:1px solid #4a3520;border-radius:3px;padding:1px 6px;font-size:10px}
.padrao{background:#12161a;border-left:2px solid #d9a441;padding:8px 12px;margin:9px 0;border-radius:0 3px 3px 0}
.padrao b{color:#d9a441;font-size:12px;display:block;margin-bottom:3px}
.padrao span{color:#b4bac1;font-size:12.5px}
.campo{margin:7px 0;font-size:13px;color:#c8cdd3}
.campo em{color:#6d7178;font-style:normal;font-size:11px;text-transform:uppercase;
  letter-spacing:.06em;display:block;margin-bottom:2px}
.links{margin-top:10px;font-size:12px;display:flex;gap:14px;flex-wrap:wrap}
.vazio{color:#6d7178;text-align:center;padding:44px;font-size:14px}
.rodape{color:#565c64;font-size:11px;margin-top:40px;padding-top:14px;border-top:1px solid #1e2328;
  font-family:"IBM Plex Mono",ui-monospace,Menlo,monospace}
"""

JS = """
(function(){
  var busca=document.getElementById('busca'),
      chips=[].slice.call(document.querySelectorAll('.chip')),
      cards=[].slice.call(document.querySelectorAll('.card')),
      dias=[].slice.call(document.querySelectorAll('.dia')),
      vazio=document.getElementById('vazio');
  function filtrar(){
    var t=busca.value.toLowerCase().trim(),
        ativos=chips.filter(function(c){return c.getAttribute('aria-pressed')==='true'})
                    .map(function(c){return c.dataset.v}),
        visiveis=0;
    cards.forEach(function(c){
      var okV=!ativos.length||ativos.indexOf(c.dataset.veredito)>-1,
          okT=!t||c.dataset.busca.indexOf(t)>-1,
          ok=okV&&okT;
      c.hidden=!ok; if(ok)visiveis++;
    });
    dias.forEach(function(d){
      var n=d.nextElementSibling,algum=false;
      while(n&&n.classList.contains('card')){ if(!n.hidden)algum=true; n=n.nextElementSibling; }
      d.hidden=!algum;
    });
    vazio.hidden=visiveis>0;
  }
  busca.addEventListener('input',filtrar);
  chips.forEach(function(c){
    c.addEventListener('click',function(){
      c.setAttribute('aria-pressed',c.getAttribute('aria-pressed')==='true'?'false':'true');
      filtrar();
    });
  });
})();
"""

MESES = "jan fev mar abr mai jun jul ago set out nov dez".split()
SEMANA = "seg ter qua qui sex sab dom".split()


def e(v: Any) -> str:
    """Escapa para HTML. Texto de LLM pode conter < e &."""
    return html.escape(str(v)) if v is not None else ""


def ler(nome: str) -> list[dict]:
    caminho = DIR_MARTS / f"{nome}.parquet"
    if not caminho.exists():
        raise SystemExit(f"ERRO: {caminho} nao existe - rode `python -m hfpapers export` antes.")
    return pq.read_table(caminho).to_pylist()


def data_br(d: dt.date) -> str:
    return f"{SEMANA[d.weekday()]}, {d.day:02d} {MESES[d.month - 1]}"


def montar(janela: int) -> tuple[str, dict]:
    manifest = json.loads((DIR_MARTS / "_manifest.json").read_text(encoding="utf-8"))

    papers = {p["paper_id"]: p for p in ler("dim_paper")}
    triagem = {t["paper_id"]: t for t in ler("fato_triagem")}
    fichas = {f["paper_id"]: f for f in ler("dim_ficha")}

    hoje = dt.date.today()
    corte = hoje - dt.timedelta(days=janela)

    # A janela usa data_hf_daily (a data da operacao diaria), nao data_arxiv.
    na_janela = [
        p for p in papers.values()
        if p.get("data_hf_daily") and p["data_hf_daily"] >= corte
    ]

    vereditos = Counter(
        triagem.get(p["paper_id"], {}).get("veredito", "sem_triagem") for p in na_janela
    )
    aprovados = [
        p for p in na_janela
        if triagem.get(p["paper_id"], {}).get("veredito") in ("amplo", "estrito")
    ]

    # Volume por dia: alimenta a barra do topo e mostra buraco de coleta.
    por_dia_total: Counter = Counter(p["data_hf_daily"] for p in na_janela)
    por_dia_aprov = defaultdict(list)
    for p in aprovados:
        por_dia_aprov[p["data_hf_daily"]].append(p)

    dias_seq = [corte + dt.timedelta(days=i) for i in range((hoje - corte).days + 1)]
    pico = max(por_dia_total.values(), default=1)
    barras = "".join(
        f'<i class="{"tem" if por_dia_total.get(d) else ""}" '
        f'style="height:{round(100 * por_dia_total.get(d, 0) / pico)}%" '
        f'title="{d.isoformat()}: {por_dia_total.get(d, 0)}"></i>'
        for d in dias_seq
    )

    total = len(na_janela)
    n_estrito, n_amplo = vereditos["estrito"], vereditos["amplo"]
    taxa = round(100 * (n_estrito + n_amplo) / total) if total else 0

    corpo = []
    for dia in sorted(por_dia_aprov, reverse=True):
        do_dia = sorted(
            por_dia_aprov[dia],
            key=lambda p: (
                triagem[p["paper_id"]]["veredito"] != "estrito",
                -(p.get("upvotes_atual") or 0),
            ),
        )
        corpo.append(f'<div class="dia">{data_br(dia)} · {len(do_dia)} aprovados</div>')
        for p in do_dia:
            t, f = triagem[p["paper_id"]], fichas.get(p["paper_id"], {})
            ver = t["veredito"]

            meta = [f'<span class="tag {ver}">{ver}</span>']
            if p.get("upvotes_atual"):
                meta.append(f'<span class="up">▲ {p["upvotes_atual"]}</span>')
            if p.get("github_stars_atual"):
                meta.append(f'<span class="up">★ {p["github_stars_atual"]}</span>')
            if t.get("decisao_fronteira"):
                meta.append('<span class="fronteira">fronteira</span>')

            bloco = []
            if f.get("padrao_nome"):
                bloco.append(
                    f'<div class="padrao"><b>{e(f["padrao_nome"])}</b>'
                    f'<span>{e(f.get("padrao_mecanismo"))}</span></div>'
                )
            for rot, chave in (
                ("achado", "achado"),
                ("implicação prática", "implicacao_pratica"),
                ("exemplo", "exemplo_concreto"),
                ("ressalva", "ressalva"),
            ):
                if f.get(chave):
                    bloco.append(f'<div class="campo"><em>{rot}</em>{e(f[chave])}</div>')
            if not f:
                bloco.append(f'<div class="campo">{e(t.get("justificativa"))}</div>')

            links = []
            for rot, url in (
                ("Hugging Face", p.get("url_hf")),
                ("arXiv", p.get("url_arxiv")),
                ("código", p.get("github_repo")),
                ("projeto", p.get("project_page")),
            ):
                if url:
                    links.append(f'<a href="{e(url)}" target="_blank" rel="noopener">{rot}</a>')

            # data-busca concentra o que o filtro do topo varre.
            alvo = " ".join(
                str(x).lower() for x in (
                    p.get("titulo"), f.get("padrao_nome"), f.get("achado"),
                    p.get("organizacao"), f.get("implicacao_pratica"),
                ) if x
            )
            corpo.append(
                f'<div class="card" data-veredito="{ver}" data-busca="{e(alvo)}">'
                f'<h2>{e(p.get("titulo"))}</h2>'
                f'<div class="meta">{"".join(meta)}</div>'
                f'{"".join(bloco)}'
                f'<div class="links">{"".join(links)}</div>'
                f"</div>"
            )

    gerado = dt.datetime.now().replace(microsecond=0)
    doc = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>HF Daily Papers · painel</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:wght@400;500&family=Instrument+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>{CSS}</style></head>
<body><div class="wrap">
<h1>HF Daily Papers</h1>
<p class="sub">Janela de {janela} dias · {corte.isoformat()} a {hoje.isoformat()} · gerado {gerado.strftime("%d/%m/%Y %H:%M")}</p>

<div class="kpis">
  <div class="kpi"><div class="n">{total}</div><div class="r">papers na janela</div></div>
  <div class="kpi"><div class="n" style="color:#d9a441">{n_estrito}</div><div class="r">estritos</div></div>
  <div class="kpi"><div class="n" style="color:#9dc3d8">{n_amplo}</div><div class="r">amplos</div></div>
  <div class="kpi"><div class="n">{vereditos["fora"]}</div><div class="r">fora</div></div>
  <div class="kpi"><div class="n">{taxa}%</div><div class="r">taxa de aprovação</div></div>
</div>

<div class="barra" title="volume coletado por dia">{barras}</div>

<div class="ctrl">
  <input id="busca" class="busca" type="search" placeholder="Filtrar por título, padrão, achado, organização…" autocomplete="off">
  <button class="chip" data-v="estrito" aria-pressed="false">estrito</button>
  <button class="chip" data-v="amplo" aria-pressed="false">amplo</button>
</div>

{"".join(corpo) or '<div class="vazio">Nenhum paper aprovado nesta janela.</div>'}
<div id="vazio" class="vazio" hidden>Nada corresponde ao filtro.</div>

<div class="rodape">
  run_id {e(manifest.get("run_id"))} · export {e(manifest.get("gerado_em"))} ·
  base completa {manifest.get("linhas", {}).get("dim_paper", "?")} papers ·
  fonte de verdade: marts/ (Power BI)
</div>
</div>
<script>{JS}</script>
</body></html>"""
    return doc, manifest


def main() -> int:
    ap = argparse.ArgumentParser(description="Gera o painel HTML estatico de marts/.")
    ap.add_argument("--dias", type=int, default=JANELA_PADRAO,
                    help=f"Janela em dias (padrao {JANELA_PADRAO}). Segura o tamanho do arquivo.")
    ap.add_argument("--destino", type=Path, default=DESTINO_PADRAO,
                    help=f"Arquivo de saida (padrao {DESTINO_PADRAO}).")
    ap.add_argument("--force", action="store_true",
                    help="Regera mesmo se o run_id nao mudou.")
    args = ap.parse_args()

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

    doc, _ = montar(args.dias)

    args.destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.destino.with_suffix(".html.tmp")
    tmp.write_text(doc, encoding="utf-8")
    os.replace(tmp, args.destino)   # atomico: ninguem le um arquivo pela metade

    if run_id:
        CARIMBO.write_text(run_id, encoding="utf-8")

    kb = len(doc.encode("utf-8")) / 1024
    print(f"painel: {args.destino} ({kb:.0f} KB, janela {args.dias}d, run_id {run_id})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
