"""Perfil do dados.json do painel v2 e casos extremos derivados dele.

    python paineis/v2/scripts/perfil_dados.py            # imprime o perfil em Markdown
    python paineis/v2/scripts/perfil_dados.py --casos    # grava paineis/v2/casos/*.json

Os casos extremos nao sao inventados: cada um parte dos papers reais e estica
uma dimensao (quantidade, comprimento, nulos, numeros) ate onde o esquema
permite, para o layout ser testado onde quebra e nao so na amostra de hoje.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
DADOS = RAIZ / "relatorios" / "painel-v2" / "dados.json"
CASOS = RAIZ / "paineis" / "v2" / "casos"
EIXOS = ["ganho", "solidez", "abertura", "facilidade", "amplitude", "atencao"]


def quantis(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return "–"
    n = len(xs)
    pega = lambda f: xs[min(n - 1, int(n * f))]
    return f"mín {xs[0]:g} · p50 {pega(.5):g} · p90 {pega(.9):g} · máx {xs[-1]:g} (n={n})"


def conta(c: Counter, total=None):
    return ", ".join(f"{k} {v}" for k, v in c.most_common())


def perfil(d) -> str:
    P = d["papers"]
    n = len(P)
    R = [r for p in P for r in p["res"]]
    E = [e for p in P for e in p["ents"]]
    ult = dt.date.fromisoformat(d["dias"][-1])
    no = lambda dias: sum(dt.date.fromisoformat(p["d"]) >= ult - dt.timedelta(days=dias - 1) for p in P)
    L = []
    w = L.append
    w(f"# Perfil do dados.json (gerado em {d['gerado_em']})\n")
    w(f"- **{n} papers lidos**, {len(d['faltam'])} na fila sem leitura, {len(d['dias'])} dias de coleta ({d['dias'][0]} a {d['dias'][-1]}).")
    w(f"- Períodos: 7 dias = {no(7)} papers, 14 dias = {no(14)}, tudo = {n}. Papers por dia: {quantis(Counter(p['d'] for p in P).values())}.")
    w(f"- Leitura: {sum(p['parcial'] for p in P)} de {n} parciais; fonte {conta(Counter(p['L']['f'] for p in P))}; seção de limites {conta(Counter(p['L']['lim'] for p in P))}.")
    w("\n## Distribuições\n")
    w(f"- Solidez: {conta(Counter(p['sol'] for p in P))}.")
    w(f"- Esforço (0 só informa … 5 fora de alcance): {conta(Counter(p['esf'] for p in P))}.")
    w(f"- Entrega: {conta(Counter(p['ent'] for p in P))}.")
    w(f"- Camada: {conta(Counter(str(p['cam']) for p in P))}.")
    w(f"- Arenas por paper: {conta(Counter(len(p['ar']) for p in P))}; arenas: {conta(Counter(a for p in P for a in p['ar']))}.")
    w(f"- Hardware: {conta(Counter(p['hw'] for p in P))}.")
    w(f"- Algo liberado: {sum(p['rel'] for p in P)}; só prometido: {sum(p['prom'] for p in P)}; abertura conferida: {sum(p['abConf'] for p in P)}.")
    w(f"- Votos: {quantis(p['u'] for p in P)}.")
    w("\n## Nulos\n")
    w("| Campo | Nulo ou não lido | % |\n|---|---|---|")
    for e in EIXOS:
        k = sum(p["radar"][e] is None for p in P)
        w(f"| radar.{e} | {k} | {100 * k // n}% |")
    for s in P[0]["sig"]:
        k = sum(p["sig"][s] is None for p in P)
        w(f"| sinal {s} | {k} | {100 * k // n}% |")
    for a in P[0]["ab"]:
        k = sum(p["ab"][a] == "nao_lido" for p in P)
        w(f"| abertura.{a} | {k} | {100 * k // n}% |")
    for campo, f in [("best (melhor resultado)", lambda p: not p["best"]), ("man (manchete)", lambda p: not p["man"]),
                     ("cam (camada)", lambda p: not p["cam"]), ("res vazio", lambda p: not p["res"]),
                     ("ents vazio", lambda p: not p["ents"]), ("ar vazio", lambda p: not p["ar"]),
                     ("hw não reportado", lambda p: p["hw"] == "nao_reportado"), ("org vazia", lambda p: not p["org"])]:
        k = sum(1 for p in P if f(p))
        w(f"| {campo} | {k} | {100 * k // n}% |")
    w(f"\nEixos do radar lidos por paper: {conta(Counter(sum(v is not None for v in p['radar'].values()) for p in P))}.")
    w("\n## Comprimentos de texto (caracteres)\n")
    w(f"- Título: {quantis(len(p['t']) for p in P)}; sem dois-pontos: {sum(':' not in p['t'] for p in P)}.")
    w(f"- Problema (`prob`): {quantis(len(p['prob'] or '') for p in P)}.")
    w(f"- Trecho de entrega: {quantis(len(p['entTr'] or '') for p in P)}.")
    w(f"- Alegações: {quantis(len(a[1]) for p in P for a in p['aleg'])}; ressalvas: {quantis(len(a[1]) for p in P for a in p['ress'])}.")
    w(f"- Benchmark: {quantis(len(r['b'] or '') for r in R)}; métrica: {quantis(len(r['m'] or '') for r in R)}.")
    w(f"- Nome do sistema na tabela: {quantis(len(l[0] or '') for r in R for l in r['lin'])}.")
    w(f"- Entidade: {quantis(len(e[0]) for e in E)}; organização: {quantis(len(p['org'] or '') for p in P)}.")
    w("\n## Listas por paper\n")
    for campo in ["res", "ents", "aleg", "ress", "ef", "art", "naoex"]:
        w(f"- `{campo}`: {quantis(len(p[campo]) for p in P)}.")
    w(f"- Linhas por tabela de resultado: {quantis(len(r['lin']) for r in R)}.")
    w("\n## Números\n")
    w(f"- {len(R)} resultados: {conta(Counter(r['e'] for r in R))}; inferidos: {sum(bool(r['inf']) for r in R)}.")
    w(f"- Ganho relativo contra o melhor rival (%): {quantis(r['rext'] for r in R)}.")
    w(f"- Diferença absoluta: {quantis(r['dext'] for r in R)}.")
    w(f"- Melhor ganho do paper (%): {quantis(p['best']['r'] for p in P if p['best'])}.")
    w(f"- Eficiência: {[(e['valor'], e['forma'], e['sentido']) for p in P for e in p['ef']]}.")
    return "\n".join(L) + "\n"


# --- casos extremos ---------------------------------------------------------

def _novo(d, papers, faltam=None, dias=None):
    o = {k: v for k, v in d.items() if k not in ("papers", "faltam", "dias")}
    o["papers"] = papers
    o["faltam"] = d["faltam"] if faltam is None else faltam
    o["dias"] = dias if dias is not None else sorted({p["d"] for p in papers} | {f["d"] for f in o["faltam"]}) or d["dias"][-1:]
    return o


def casos(d):
    P = d["papers"]
    por_res = sorted(P, key=lambda p: -len(p["res"]))
    cheio = por_res[0]
    c = {}

    c["vazio"] = _novo(d, [], faltam=[], dias=d["dias"][-1:])
    c["um-paper"] = _novo(d, [copy.deepcopy(cheio)], faltam=[])
    c["dia-unico"] = _novo(d, [dict(copy.deepcopy(p), d=d["dias"][-1]) for p in P[:6]], faltam=[])

    # nada lido: so o eixo atencao existe
    nl = [copy.deepcopy(p) for p in P if p["sol"] == "sem_leitura"]
    c["nada-lido"] = _novo(d, nl, faltam=[dict(f, id=f"{f['id']}.{i}") for i in range(12) for f in d["faltam"]])

    # 240 papers em 30 dias: o que acontece quando "tudo" vira um mes
    muitos, dias = [], []
    base = dt.date.fromisoformat(d["dias"][-1])
    for i in range(240):
        p = copy.deepcopy(P[i % len(P)])
        dia = base - dt.timedelta(days=i % 30)
        p["id"] = f"{p['id']}.{i}"
        p["d"] = dia.isoformat()
        p["u"] = max(1, int(p["u"] * (0.2 + ((i * 37) % 100) / 40)))
        p["radar"]["atencao"] = (i * 53) % 101
        muitos.append(p)
        dias.append(p["d"])
    c["muitos"] = _novo(d, muitos, dias=sorted(set(dias)))

    # textos no limite: titulo sem dois-pontos e com palavra inquebravel,
    # nomes de benchmark, sistema, entidade e trechos tres vezes o maximo real
    tl = []
    for i, p in enumerate(copy.deepcopy(P[:12] + por_res[:3])):
        p["id"] += ".t"
        p["t"] = (p["t"].replace(":", "") + " " + "Hiperparametrizacao" * 3 + " com um subtítulo que não termina e segue por mais de duzentos caracteres para testar corte").strip() if i % 2 else "Pneumoultramicroscopicossilicovulcanoconiotico" + p["t"]
        p["prob"] = (p["prob"] or "") * 4
        p["org"] = "Instituto-Nacional-de-Pesquisas-em-Inteligencia-Artificial-Aplicada"
        p["entTr"] = (p["entTr"] or "x") * 4
        for r in p["res"]:
            r["b"] = (r["b"] or "") + " Extended Long-Horizon Robustness Suite v2.1 (hard split)"
            r["m"] = (r["m"] or "") + " @ top-10 macro-averaged"
            for l in r["lin"]:
                l[0] = (l[0] or "") + " (fine-tuned, 128 passos, sem destilação)"
            if r.get("nos"): r["nos"][0] = r["lin"][0][0]
            if r.get("ext"): r["ext"][0] += " (fine-tuned, 128 passos, sem destilação)"
        if p["best"]: p["best"]["x"] += " (fine-tuned, 128 passos, sem destilação)"
        p["ents"] = [[e[0] + "-Instruct-Preview-2026-11-Extended", *e[1:]] for e in p["ents"]]
        p["aleg"] = [[a[0], a[1] * 3, a[2]] for a in p["aleg"]]
        p["ress"] = [[a[0], a[1] * 3, a[2]] for a in p["ress"]]
        tl.append(p)
    c["textos-longos"] = _novo(d, tl)

    # numeros no limite: empates, ganhos enormes e negativos, votos 1 e 50 mil
    nx = []
    for i, p in enumerate(copy.deepcopy(P)):
        p["id"] += ".n"
        modo = i % 4
        p["u"] = [1, 50000, 70, 70][modo]
        for r in p["res"]:
            if r["rext"] is None: continue
            f = [0, 60, -8, 1][modo]
            r["rext"] = round(r["rext"] * f, 1); r["dext"] = round((r["dext"] or 0) * f, 2)
        if p["best"]: p["best"]["r"] = round(p["best"]["r"] * [0, 60, -8, 1][modo], 1)
        if p["radar"]["ganho"] is not None: p["radar"]["ganho"] = [50, 100, 0, p["radar"]["ganho"]][modo]
        for e in p["ef"]: e["valor"] = [0.001, 12000, e["valor"], e["valor"]][modo]
        nx.append(p)
    c["numeros-extremos"] = _novo(d, nx)

    # tudo igual: mesmos votos, mesma solidez, mesmo esforco (enxame e escada empilham)
    ig = []
    for p in copy.deepcopy(P):
        p["id"] += ".i"; p["u"] = 70; p["sol"] = "firme"; p["esf"] = 2; p["radar"]["atencao"] = 50
        ig.append(p)
    c["tudo-igual"] = _novo(d, ig)

    # paper denso: 60 resultados em 12 arenas, 40 entidades, 8 trechos de cada
    dn = copy.deepcopy(cheio); dn["id"] += ".d"
    arenas = ["matematica_raciocinio", "codigo", "agentes_ferramentas", "conhecimento_linguagem", "compreensao_multimodal",
              "geracao_imagem", "geracao_video_mundo", "fala_audio", "robotica_acao", "3d_graficos", "ciencia_dominio", "seguranca_confiabilidade"]
    res = []
    for i in range(60):
        r = copy.deepcopy(cheio["res"][i % len(cheio["res"])]); r["ar"] = arenas[i % 12]; r["b"] = f"{r['b']} {i}"; res.append(r)
    dn["res"] = res; dn["ar"] = arenas
    todas = [e for p in P for e in p["ents"]]
    dn["ents"] = todas[:40]
    dn["aleg"] = [a for p in P for a in p["aleg"]][:8]
    dn["ress"] = [a for p in P for a in p["ress"]][:8]
    dn["ef"] = [e for p in P for e in p["ef"]][:6]
    dn["art"] = [a for p in P for a in p["art"]][:8]
    c["paper-denso"] = _novo(d, [dn] + [copy.deepcopy(p) for p in P[:5]])
    return c


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--casos", action="store_true")
    ap.add_argument("--dados", default=str(DADOS))
    a = ap.parse_args()
    d = json.loads(Path(a.dados).read_text(encoding="utf-8"))
    if a.casos:
        CASOS.mkdir(exist_ok=True)
        for nome, dados in casos(d).items():
            (CASOS / f"{nome}.json").write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
            print(f"{nome}: {len(dados['papers'])} papers, {len(dados['faltam'])} na fila, {len(dados['dias'])} dias")
    else:
        print(perfil(d))
