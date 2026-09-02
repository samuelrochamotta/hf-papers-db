"""Gera o painel HTML estatico a partir dos Parquet de marts/.

Nao e a interface de leitura do projeto - o Power BI continua sendo. Este
painel existe para distribuicao: um arquivo unico, sem dependencia de rede,
que abre em qualquer visualizador de HTML (Teams, e-mail, navegador).

O desenho e o mesmo do Artifact "Painel Daily Papers", que nasceu como
artboard da Claude Design. Aquele arquivo so roda dentro do runtime do canvas;
`scripts/painel_app.js` e o porte do mesmo layout para JS de navegador. Este
script nao desenha nada: extrai os dados, serializa em `DADOS` e embute o app.

Tres decisoes que valem explicacao:

1. Le `marts/_manifest.json` e nao roda de novo se o `run_id` for o mesmo da
   ultima geracao. O gatilho do launchd e `WatchPaths`, que pode disparar mais
   de uma vez para a mesma escrita; a trava de `run_id` torna o disparo extra
   um no-op em vez de trabalho repetido.

2. Recorta uma janela de dias (padrao 90). Sem isso o arquivo cresce para
   sempre: sao ~28 papers/dia entrando na base. A serie historica completa
   continua nos Parquet - o painel e a vitrine, nao o arquivo morto. O peso
   agora vem do texto das fichas embutido em `DADOS`, nao de HTML por card.
   Se ficar pesado para distribuir, `--dias` e o botao para girar.

3. Nada de pandas nem jinja2. O env `digest-hf` nao tem os dois, e um painel de
   distribuicao nao justifica dependencia nova - pyarrow e pyyaml ja estao la.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from collections import defaultdict
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
.mark { transition: opacity 120ms ease, transform 120ms ease; cursor: pointer; }
.mark:hover { opacity: 1 !important; transform: scale(1.35); }
.bar { transition: filter 120ms ease; cursor: pointer; }
.bar:hover { filter: brightness(1.22) saturate(1.1); }
.row { transition: background 120ms ease; cursor: pointer; }
.row:hover { background: #191d21; }
.card { background: #16191c; border: 1px solid #242a30; border-radius: 5px; }
.busca::placeholder { color: #6d7178; }
.busca:focus { border-color: #d9a441 !important; background: #1e2328 !important; }
#tip { display: none; position: fixed; max-width: 350px; background: #22272c; border: 1px solid #333a41;
  padding: 10px 13px; border-radius: 5px; pointer-events: none; z-index: 90; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
#tip .tip1 { font-size: 12.5px; color: #f5f3ee; line-height: 1.4; margin-bottom: 4px; }
#tip .tip2 { font-family: "IBM Plex Mono", monospace; font-size: 11px; color: #9aa0a8; }
"""


def ler(nome: str) -> list[dict]:
    caminho = DIR_MARTS / f"{nome}.parquet"
    if not caminho.exists():
        raise SystemExit(f"ERRO: {caminho} nao existe - rode `python -m hfpapers export` antes.")
    return pq.read_table(caminho).to_pylist()


def iso(d: Any) -> str | None:
    return d.isoformat() if isinstance(d, (dt.date, dt.datetime)) else (d or None)


def modelos() -> tuple[str, str]:
    """Rodape do painel. Vem do config para nao envelhecer quando o modelo trocar."""
    try:
        cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
        llm = cfg.get("llm", {})
        return (llm.get("estagio_a", {}).get("modelo", "?"),
                llm.get("estagio_b", {}).get("modelo", "?"))
    except OSError:
        return "?", "?"


def montar_dados(janela: int) -> tuple[dict, dict]:
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

    # A janela usa data_hf_daily (a data da operacao diaria), nao data_arxiv.
    na_janela = [p for p in papers if p.get("data_hf_daily") and p["data_hf_daily"] >= corte]
    ids = {p["paper_id"] for p in na_janela}

    area_primaria: dict[str, str] = {}
    areas_sec: dict[str, list[str]] = defaultdict(list)
    for r in ler("ponte_paper_area"):
        if r["paper_id"] not in ids:
            continue
        if r.get("is_primaria"):
            area_primaria[r["paper_id"]] = r["area"]
        else:
            areas_sec[r["paper_id"]].append(r["area"])

    topicos_por_paper: dict[str, list[str]] = defaultdict(list)
    for r in ler("ponte_paper_topico"):
        if r["paper_id"] in ids:
            topicos_por_paper[r["paper_id"]].append(r["topico"])

    serie: dict[str, list] = defaultdict(list)
    for m in sorted(ler("fato_metrica"), key=lambda r: (r["paper_id"], r["data_snapshot"])):
        if m["paper_id"] in ids:
            serie[m["paper_id"]].append(
                [iso(m["data_snapshot"]), m.get("upvotes"), m.get("comentarios"), m.get("github_stars")]
            )

    lista = []
    for p in sorted(na_janela, key=lambda x: (x["data_hf_daily"], x["paper_id"])):
        pid = p["paper_id"]
        t = triagem.get(pid, {})
        lista.append({
            "id": pid,
            "t": p.get("titulo") or "",
            "d": iso(p.get("data_hf_daily")),
            "da": iso(p.get("data_arxiv")),
            "v": t.get("veredito") or "fora",
            "rf": t.get("regra_fora"),
            "fr": 1 if t.get("decisao_fronteira") else 0,
            "art": t.get("tem_artefato_nomeado"),
            "a": area_primaria.get(pid),
            "as": areas_sec.get(pid, []),
            "tp": topicos_por_paper.get(pid, []),
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
        })

    modelo_a, modelo_b = modelos()
    dados = {
        "gerado": manifest.get("gerado_em") or dt.datetime.now().replace(microsecond=0).isoformat(),
        "modeloA": modelo_a,
        "modeloB": modelo_b,
        "areas": [{"a": a["area"], "def": a.get("definicao") or ""} for a in ler("dim_area")],
        "topicos": [{"t": t["topico"], "def": t.get("definicao") or ""} for t in ler("dim_topico")],
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
    }
    return dados, manifest


def montar(janela: int) -> tuple[str, dict]:
    dados, manifest = montar_dados(janela)
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
