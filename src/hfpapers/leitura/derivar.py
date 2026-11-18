"""Tudo que e conta no painel v2 sai daqui, nunca do modelo.

Entrada: a extracao conferida de um paper (`extrator.Leitura.dados`) e os
metadados que o pipeline ja tem (votos, data do HF Daily, repositorio).
Saida: um dicionario compacto por paper, que `scripts/gerar_painel_v2.py`
grava em `dados.json` para o front-end.

Os cortes de solidez e esforco sao heuristicas do estudo de 2026-11-14 e
ainda nao foram calibrados contra um conjunto-ouro.
"""

from __future__ import annotations

import math
import re
import statistics as st
from typing import Any, Iterable, Optional, cast

GRAVE = {"preliminar", "amostra_pequena", "pesos_ficticios"}
RANK_ARTEFATO: dict[Optional[str], int] = {"liberado": 4, "prometido": 3, "so_pagina": 2, "ausente": 1}
FATOR_ARTEFATO = {"liberado": 1.0, "prometido": 0.4, "so_pagina": 0.15, "ausente": 0.0}
PESO_ARTEFATO = {"codigo": 0.4, "pesos": 0.3, "dados": 0.2, "demo": 0.1}
EIXOS = ("ganho", "solidez", "abertura", "facilidade", "amplitude", "atencao")


def num(x: Any) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _valor(linha: dict) -> float:
    """O `valor` de uma linha que ja passou pelo filtro `num(valor) is not None`."""
    return cast(float, num(linha["valor"]))


def _pm(linha: dict) -> Optional[float]:
    return num(linha.get("pm")) if linha.get("pm") is not None else None


# ── resultados ──────────────────────────────────────────────────────────────


_HTTP = re.compile(r"^\s*https?://", re.I)


def _ok(x) -> bool:
    """Trecho conferido, ou sem trecho a conferir. So `_ok is False` sai."""
    return isinstance(x, dict) and x.get("_ok") is not False


def _conferidos(xs) -> list[dict]:
    return [x for x in (xs or []) if _ok(x)]


def url_segura(u):
    """A URL vem copiada pelo modelo: so http(s) vira link no painel."""
    return u.strip() if isinstance(u, str) and _HTTP.match(u) else None


def resultado(r: dict) -> Optional[dict]:
    """Uma tabela comparativa: melhor linha nossa contra o melhor rival
    externo e contra a linha fraca (base ou trivial), no sentido da metrica.
    Linha cujo numero nao foi achado no texto fica de fora."""
    linhas = [l for l in (r.get("linhas") or [])
              if num(l.get("valor")) is not None and l.get("_ok") is not False]
    if not linhas:
        return None
    menor = r.get("direcao") == "menor_melhor"
    escolher = min if menor else max

    def melhor(xs: list[dict]) -> Optional[dict]:
        return escolher(xs, key=_valor) if xs else None

    nos = melhor([l for l in linhas if l.get("papel") == "nosso"])
    ext = melhor([l for l in linhas if l.get("papel") == "externo"])
    fracas = [l for l in linhas if l.get("papel") in ("base", "trivial")]
    fraca = (max if menor else min)(fracas, key=_valor) if fracas else None

    def delta(x: Optional[dict]) -> Optional[float]:
        if not nos or not x:
            return None
        d = _valor(nos) - _valor(x)
        return round(-d if menor else d, 4)

    def relativo(x: Optional[dict]) -> Optional[float]:
        d = delta(x)
        base = num(x["valor"]) if x else None
        if d is None or not base:
            return None
        return round(100 * d / abs(base), 1)

    dext = delta(ext)
    ruido = None
    if dext is not None and nos and ext and _pm(nos) is not None and _pm(ext) is not None:
        ruido = abs(dext) <= (_pm(nos) or 0) + (_pm(ext) or 0)
    if not nos:
        estado = "sem_nosso"
    elif ext is None or dext is None:  # com `nos` e `ext`, `dext` nunca e None
        estado = "sem_rival"
    elif ruido:
        estado = "ruido"
    elif dext > 0:
        estado = "ganha"
    elif dext == 0:
        estado = "empata"
    else:
        estado = "perde"
    return {
        "tab": r.get("tabela"), "b": r.get("benchmark"), "ar": r.get("arena") or "outra",
        "m": r.get("metrica"), "dir": r.get("direcao"), "rec": r.get("recurso"),
        "inf": bool(r.get("colunas_inferidas")), "sec": r.get("secao"), "e": estado,
        "nos": nos and [nos["nome"], num(nos["valor"]), _pm(nos)],
        "ext": ext and [ext["nome"], num(ext["valor"]), _pm(ext), bool(ext.get("fechado"))],
        "wk": fraca and [fraca["nome"], num(fraca["valor"]), fraca.get("papel")],
        "dext": dext, "rext": relativo(ext), "rwk": relativo(fraca),
        "lin": [[l["nome"], l.get("papel"), num(l["valor"]), _pm(l)] for l in linhas],
    }


# ── sinais de solidez ───────────────────────────────────────────────────────


def sinais(o: dict, res: list[dict], parcial: bool) -> tuple[dict, Optional[float], Optional[dict]]:
    comp = [r for r in res if r["ext"] and r["nos"]]
    vit = round(sum(r["e"] == "ganha" for r in comp) / len(comp), 2) if comp else None
    # O que o codigo nao achou no texto nao conta como sinal.
    e: dict = o["estatistica"] if _ok(o.get("estatistica")) else {}
    ev = o.get("evidencia") or []
    sig: dict[str, Optional[bool]] = {}
    v = e.get("variancia")
    sig["var"] = True if v in ("pm_definido", "ic") else (
        False if v == "pm_sem_definicao" or (v == "nenhuma" and not parcial) else None)
    seeds, trials = num(e.get("seeds")), num(e.get("trials"))
    escala = max([num(x.get("n")) or 0 for x in _conferidos(o.get("escala"))] + [0])
    sig["n"] = True if ((seeds or 0) >= 3 or (trials or 0) >= 3 or escala >= 100) else (
        False if (seeds or trials) else None)
    sig["ext"] = (len(comp) > 0) if res else None
    sig["vit"] = (vit >= 0.7) if vit is not None else None
    sig["evid"] = (("humana" in ev) or ("mundo_real" in ev)) if ev else None

    manchetes = [x for x in _conferidos(o.get("alegacoes"))
                 if x.get("tipo") == "manchete" and num(x.get("numero")) is not None]
    man = None
    conf = None
    if manchetes:
        n0 = cast(float, num(manchetes[0]["numero"]))  # filtrado acima
        cands: list[float] = []
        for r in res:
            cands += [l[2] for l in r["lin"]]
            if r["dext"] is not None:
                cands.append(abs(r["dext"]))
            if r["nos"] and r["wk"]:
                cands.append(abs(r["nos"][1] - r["wk"][1]))
            for k in ("rext", "rwk"):
                if r[k] is not None:
                    cands.append(abs(r[k]))
        # Sem tabela conferida nao ha com o que comparar: conf fica None ("sem tabela").
        conf = any(abs(c - n0) <= max(0.051, abs(n0) * 0.01) for c in cands if c is not None) if res else None
        m = manchetes[0]
        man = {"n": n0, "u": m.get("unidade"), "contra": m.get("contra"), "tr": m.get("trecho"),
               "ok": m.get("_ok"), "conf": conf}
    sig["man"] = conf
    rs = _conferidos(o.get("ressalvas"))
    lim = (o.get("leitura") or {}).get("secao_limitacoes")
    sig["ress"] = False if any(x.get("tipo") in GRAVE for x in rs) else (
        True if (rs or lim == "presente") else None)
    return sig, vit, man


def solidez(sig: dict) -> tuple[str, int, int]:
    lidos = [k for k, x in sig.items() if x is not None]
    t = sum(1 for x in sig.values() if x)
    if len(lidos) < 3:
        return "sem_leitura", t, len(lidos)
    q = t / len(lidos)
    return ("fragil" if q < 0.35 else "basico" if q < 0.6 else "firme" if q < 0.8 else "forte"), t, len(lidos)


# ── abertura e esforco ──────────────────────────────────────────────────────


def abertura(o: dict, parcial: bool, github: Optional[str]) -> tuple[dict, bool]:
    ab: dict[str, Any] = {}
    for t in PESO_ARTEFATO:
        estados = [x.get("estado") for x in _conferidos(o.get("artefatos")) if x.get("tipo") == t]
        ab[t] = max(estados, key=lambda e: RANK_ARTEFATO.get(e, 0)) if estados else (
            "nao_lido" if parcial else "ausente")
    conferido = False
    if github and ab["codigo"] != "liberado":
        ab["codigo"] = "liberado"  # o repositorio vinculado no HF e evidencia externa
        conferido = True
    return ab, conferido


def esforco(entrega: str, camada: Optional[str], ab: dict) -> int:
    liberado = any(ab[t] == "liberado" for t in ("codigo", "pesos", "dados"))
    if entrega in ("panorama_posicao", "estudo"):
        return 0
    if entrega == "medida":
        return 2 if liberado else 0
    if liberado:
        return 3 if (entrega == "metodo" and camada in ("pos_treino", "arquitetura_pretreino")) else 2
    if entrega == "modelo":
        return 5
    return 4 if camada == "arquitetura_pretreino" else 3


def classe_hardware(hw: list[dict]) -> str:
    if not hw:
        return "nao_reportado"
    q = sum((num(h.get("qtd")) or 1) for h in hw)
    return "cluster" if q >= 16 else "1_no" if q >= 2 else "1_gpu"


# ── radar ───────────────────────────────────────────────────────────────────


TETO_BENCH = 16  # amplitude: 16 benchmarks ou mais tocam a borda


def amplitude(n: int) -> int:
    """Escala logaritmica fixa: 1, 3, 5, 9 e 16 benchmarks dao 24, 49, 63, 81
    e 100. Separa 5 de 9 e nao muda quando o periodo muda."""
    return round(min(100.0, 100 * math.log1p(n) / math.log1p(TETO_BENCH)))


def faixa_abertura(ab: dict) -> tuple[Optional[int], Optional[int]]:
    """Abertura como faixa: (confirmado, maximo possivel), de 0 a 100.
    O confirmado soma o que foi lido (artefato nao lido nao soma nada); o
    maximo soma o que foi lido e trata todo artefato nao lido como liberado.
    Com tudo lido os dois coincidem; sem nada lido a faixa e (None, None),
    que o painel desenha como "nao lido", nunca como zero."""
    if all(e == "nao_lido" for e in ab.values()):
        return None, None
    conf = sum(PESO_ARTEFATO[t] * FATOR_ARTEFATO.get(e, 0) for t, e in ab.items() if e != "nao_lido")
    falta = sum(PESO_ARTEFATO[t] for t, e in ab.items() if e == "nao_lido")
    return round(100 * conf), round(100 * (conf + falta))


def radar(p: dict) -> dict[str, Optional[float]]:
    """Seis eixos de 0 a 100. `None` quando o texto lido nao permite medir,
    o que o painel desenha como "nao lido", nunca como zero."""
    rx = [r["rext"] for r in p["res"] if r["rext"] is not None]
    # tanh: +3% ja aparece (65), +10% fica perto do topo (88), perda cai abaixo de 50.
    ganho = None if not rx else 50 + 50 * math.tanh(st.median(rx) / 10)
    sol = None if p["nl"] < 3 else round(100 * p["T"] / p["nl"])
    ab, _ = faixa_abertura(p["ab"])
    fac = None if p["esf"] == 0 else (5 - p["esf"]) * 20
    benchs = {r["b"] for r in p["res"] if r["nos"]}
    amp = amplitude(len(benchs)) if (benchs or not p["parcial"]) else None
    return {"ganho": None if ganho is None else round(ganho), "solidez": sol, "abertura": ab,
            "facilidade": fac, "amplitude": amp, "atencao": None}


def atencao(papers: list[dict]) -> None:
    """Percentil de votos dentro do conjunto exportado (segunda passada)."""
    votos = sorted(p.get("u") or 0 for p in papers)
    n = len(votos)
    for p in papers:
        u = p.get("u") or 0
        abaixo = sum(1 for v in votos if v < u)
        iguais = sum(1 for v in votos if v == u)
        p["radar"]["atencao"] = round(100 * (abaixo + 0.5 * iguais) / n) if n else None


# ── paper ───────────────────────────────────────────────────────────────────


def derivar(o: dict, meta: dict) -> dict:
    """`o` e a extracao conferida; `meta` traz t, d, u, org, gh do pipeline."""
    pid = o.get("id") or meta.get("id")
    lt = o.get("leitura") or {}
    parcial = lt.get("cobertura") != "completa"
    res = [x for x in (resultado(r) for r in (o.get("resultados") or [])) if x]
    sig, vit, man = sinais(o, res, parcial)
    sol, t, nl = solidez(sig)
    ab, ab_conf = abertura(o, parcial, meta.get("gh"))
    entrega = (o.get("entrega") or {}).get("primaria") or "metodo"
    camada = (o.get("camada") or {}).get("primaria")
    esf = esforco(entrega, camada, ab)
    comp = [r for r in res if r["ext"] and r["nos"] and r["rext"] is not None]
    best = max(comp, key=lambda r: r["rext"]) if comp else None
    ok = _ok  # trecho nao achado fica fora
    p = {
        "id": pid, "t": o.get("titulo") or meta.get("t"), "d": meta.get("d"),
        "u": meta.get("u") or 0, "org": meta.get("org") or "",
        "L": {"f": lt.get("fonte_texto"), "c": lt.get("cobertura"), "fim": lt.get("termina_em"),
              "lim": lt.get("secao_limitacoes")},
        "parcial": parcial,
        "ent": entrega, "ent2": (o.get("entrega") or {}).get("secundaria"),
        "entTr": (o.get("entrega") or {}).get("trecho") if ok(o.get("entrega") or {}) else None,
        "cam": camada, "prob": o.get("problema"),
        "res": res, "vit": vit, "sig": sig, "sol": sol, "T": t, "nl": nl,
        "ab": ab, "abConf": ab_conf, "esf": esf,
        "rel": any(ab[k] == "liberado" for k in ("codigo", "pesos", "dados")),
        "prom": any(ab[k] == "prometido" for k in ("codigo", "pesos", "dados")),
        "hw": classe_hardware(_conferidos(o.get("hardware"))),
        "ar": sorted({r["ar"] for r in res}),
        "ents": [[e.get("nome"), e.get("tipo"), e.get("papel"), e.get("tamanho"), bool(e.get("fechado"))]
                 for e in _conferidos(o.get("entidades"))],
        "man": man,
        "aleg": [[x.get("tipo"), x.get("trecho"), x.get("secao")] for x in (o.get("alegacoes") or []) if ok(x)],
        "ress": [[x.get("tipo"), x.get("trecho"), x.get("secao")] for x in (o.get("ressalvas") or []) if ok(x)],
        "ef": [x for x in (o.get("efeitos_custo") or []) if ok(x)],
        "art": [[x.get("tipo"), x.get("estado"), url_segura(x.get("url"))] for x in _conferidos(o.get("artefatos"))],
        "naoex": o.get("nao_extraivel") or [],
        "best": best and {"b": best["b"], "r": best["rext"], "x": best["ext"][0]},
        "url": f"https://arxiv.org/abs/{pid}",
    }
    p["radar"] = radar(p)
    p["abTeto"] = faixa_abertura(ab)[1]  # o maximo que a abertura pode chegar quando o resto for lido
    return p


def derivar_todos(itens: Iterable[tuple[dict, dict]]) -> list[dict]:
    papers = [derivar(o, meta) for o, meta in itens]
    atencao(papers)
    return papers
