"""Gera `dados.json` do painel v2 a partir das leituras do texto completo.

Duas origens:

* o banco (padrao): `leitura_texto` + metadados de `dim_paper`/`fato_metrica`,
  papers do HF Daily nos ultimos `--dias` dias;
* uma pasta de extracoes (`--extracoes DIR --amostra amostra.json`), usada
  para a previa e para os testes, sem banco.

O front-end (paineis/v2/, Svelte + ECharts) le so este arquivo. O build do
front-end e separado e fica versionado em relatorios/painel-v2/; a rodada
diaria so precisa regravar o dados.json.

Uso:
    python paineis/v2/gerar_painel_v2.py
    python paineis/v2/gerar_painel_v2.py --dias 30
    python paineis/v2/gerar_painel_v2.py --extracoes pasta/ --amostra amostra.json --destino x.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from hfpapers.leitura.derivar import derivar_todos  # noqa: E402

DESTINO = RAIZ / "relatorios" / "painel-v2" / "dados.json"


def do_banco(dias: int, hoje: dt.date | None = None) -> dict:
    from hfpapers import db
    from hfpapers.config import config

    cfg = config()
    hoje = hoje or dt.date.today()
    ini = (hoje - dt.timedelta(days=dias)).isoformat()
    conn = db.abrir(cfg)
    try:
        metas = {
            r["paper_id"]: dict(r)
            for r in conn.execute(
                """SELECT p.paper_id, p.titulo, p.data_hf_daily, p.organizacao, p.github_repo,
                      (SELECT m.upvotes FROM fato_metrica m WHERE m.paper_id = p.paper_id
                       ORDER BY m.data_snapshot DESC LIMIT 1) AS upvotes
               FROM dim_paper p WHERE p.data_hf_daily >= ?""",
                (ini,),
            )
        }
        leituras = {
            r["paper_id"]: dict(r)
            for r in conn.execute(
                "SELECT paper_id, extracao, modelo FROM leitura_texto WHERE versao_esquema = ?",
                (cfg.leitura.versao_esquema,),
            )
        }
    finally:
        conn.close()
    itens, faltam = [], []
    for pid, m in metas.items():
        meta = {
            "id": pid,
            "t": m["titulo"],
            "d": m["data_hf_daily"],
            "u": m["upvotes"] or 0,
            "org": m["organizacao"] or "",
            "gh": m["github_repo"],
        }
        if pid in leituras:
            itens.append((json.loads(leituras[pid]["extracao"]), meta))
        else:
            faltam.append({"id": pid, "t": meta["t"], "u": meta["u"], "d": meta["d"]})
    modelo = next((l["modelo"] for l in leituras.values()), cfg.leitura.modelo)
    return montar(itens, faltam, modelo)


def de_arquivos(pasta: Path, amostra: Path) -> dict:
    metas = {a["id"]: a for a in json.loads(amostra.read_text(encoding="utf-8"))}
    itens, vistos = [], set()
    for f in sorted(pasta.glob("*.json")):
        o = json.loads(f.read_text(encoding="utf-8"))
        a = metas.get(o.get("id"), {})
        itens.append(
            (
                o,
                {
                    "id": o.get("id"),
                    "t": a.get("t"),
                    "d": a.get("d"),
                    "u": a.get("u", 0),
                    "org": a.get("org") or "",
                    "gh": a.get("gh"),
                },
            )
        )
        vistos.add(o.get("id"))
    faltam = [
        {"id": k, "t": v.get("t"), "u": v.get("u", 0), "d": v.get("d")}
        for k, v in metas.items()
        if k not in vistos
    ]
    return montar(itens, faltam, "claude-haiku-5-5")


def montar(itens: list, faltam: list, modelo: str) -> dict:
    papers = derivar_todos(itens)
    papers.sort(key=lambda p: (-(p["u"] or 0), p["id"]))
    faltam.sort(key=lambda p: -(p["u"] or 0))
    dias = sorted(
        {p["d"] for p in papers if p["d"]} | {f["d"] for f in faltam if f.get("d")}
    )
    return {
        "versao": 1,
        "gerado_em": dt.datetime.now().isoformat(timespec="seconds"),
        "modelo": modelo,
        "dias": dias,
        "papers": papers,
        "faltam": faltam,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dias", type=int, default=14)
    ap.add_argument("--extracoes", type=Path)
    ap.add_argument("--amostra", type=Path)
    ap.add_argument("--destino", type=Path, default=DESTINO)
    a = ap.parse_args(argv)
    if a.extracoes:
        if not a.amostra:
            ap.error("--extracoes pede --amostra")
        dados = de_arquivos(a.extracoes, a.amostra)
    else:
        dados = do_banco(a.dias)
    a.destino.parent.mkdir(parents=True, exist_ok=True)
    a.destino.write_text(
        json.dumps(dados, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    print(
        f"{len(dados['papers'])} papers lidos, {len(dados['faltam'])} sem leitura -> {a.destino}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
