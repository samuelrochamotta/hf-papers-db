"""Relatorio de massa da grade facetada: le o banco e escreve o Markdown.

E o instrumento das duas checagens objetivas da spec (secao *Operacao*, passo 5),
e por isso mora aqui e nao numa consulta ad hoc: o ticket 08 deriva a grade v2
destas contagens, e uma contagem que ninguem consegue repetir nao serve de base
para fundir rotulo nenhum.

    python scripts/relatorio_massa.py <run_id> [saida.md]

O `run_id` recorta so o custo e o roteamento - a distribuicao sai das pontes,
que guardam o estado final da base, nao o de uma rodada. Sem `run_id`, o custo
e o do log inteiro.

A saida vai para `docs/` de proposito: `relatorios/` nao e versionado (so o
`painel.html` escapa do `.gitignore`), e este relatorio e entrada do proximo
ticket, nao artefato de leitura descartavel.

Duas leituras do denominador, e as duas aparecem porque respondem a perguntas
diferentes: a sub-area e medida **dentro da sua area** (e ali que a regra de
ramificar e a de fundir operam), a vertente e medida **sobre a base**, porque
ela e o unico eixo transversal e nao tem area a que pertencer.
"""

from __future__ import annotations

import sqlite3
import sys
from collections import defaultdict

BANCO = "data/hfpapers.db"

# Limiares da spec (secao *Operacao*, passo 5). Ficam nomeados porque o
# relatorio cita o numero que motivou cada marca, e um literal solto no meio de
# uma f-string nao se deixa citar.
TETO_SUBAREA = 0.25       # acima disso, falta ramificar
PISO_SUBAREA_PCT = 0.03   # abaixo disso (ou de 10 papers), a regra manda fundir
PISO_SUBAREA_N = 10
PISO_VERTENTE = 0.02      # abaixo disso, o rotulo e absorvido

# Faixa de incerteza em volta de cada limiar. A grade tem ~19% de instabilidade
# intrinseca (81-82% de auto-concordancia, tres medicoes em 2026-09-08): fundir
# um rotulo que esta a tres pontos do corte e decidir sobre ruido, e quem le
# precisa ver isso marcado, nao inferido.
FOLGA = 0.03


def _pct(n: int, total: int) -> float:
    return n / total if total else 0.0


def gerar(conn: sqlite3.Connection, run_id: str | None) -> str:
    conn.row_factory = sqlite3.Row
    q = lambda s, p=(): [dict(r) for r in conn.execute(s, p)]
    um = lambda s, p=(): conn.execute(s, p).fetchone()[0]

    total = um("SELECT COUNT(*) FROM dim_paper")

    # ── cobertura ───────────────────────────────────────────────────────────
    cobertura = [
        ("com par primário (área > sub-área)",
         um("SELECT COUNT(DISTINCT paper_id) FROM ponte_paper_area WHERE is_primaria=1")),
        ("com par secundário",
         um("SELECT COUNT(DISTINCT paper_id) FROM ponte_paper_area WHERE is_primaria=0")),
        ("com ao menos uma vertente",
         um("SELECT COUNT(DISTINCT paper_id) FROM ponte_paper_vertente")),
        ("com duas vertentes",
         um("SELECT COUNT(*) FROM (SELECT paper_id FROM ponte_paper_vertente "
            "GROUP BY paper_id HAVING COUNT(*)=2)")),
        ("**sem faceta nenhuma**",
         um("SELECT COUNT(*) FROM dim_paper WHERE paper_id NOT IN "
            "(SELECT paper_id FROM ponte_paper_area)")),
    ]

    # ── area > sub-area, pelo par primario ──────────────────────────────────
    linhas = q("SELECT area, subarea, COUNT(*) n FROM ponte_paper_area "
               "WHERE is_primaria=1 GROUP BY area, subarea")
    por_area: dict[str, int] = defaultdict(int)
    for a in linhas:
        por_area[a["area"]] += a["n"]

    # A sub-area que ninguem recebeu e o achado mais forte do relatorio, e ela
    # nao aparece num GROUP BY sobre a ponte: entra da grade, com zero.
    vistas = {(a["area"], a["subarea"]) for a in linhas}
    for g in q("SELECT area, area_pai FROM dim_area WHERE area_pai IS NOT NULL"):
        if (g["area_pai"], g["area"]) not in vistas:
            linhas.append({"area": g["area_pai"], "subarea": g["area"], "n": 0})
            por_area.setdefault(g["area_pai"], 0)
    linhas.sort(key=lambda a: (-por_area[a["area"]], a["area"], -a["n"], a["subarea"]))

    # ── vertentes ───────────────────────────────────────────────────────────
    verts = q("SELECT v.vertente, COUNT(p.paper_id) n, "
              "SUM(CASE WHEN p.ordem=1 THEN 1 ELSE 0 END) dom "
              "FROM dim_vertente v LEFT JOIN ponte_paper_vertente p USING (vertente) "
              "GROUP BY v.vertente ORDER BY n DESC")
    atribuicoes = sum(v["n"] for v in verts)
    classificados = um("SELECT COUNT(DISTINCT paper_id) FROM ponte_paper_vertente")

    nao = q("SELECT eixo, COUNT(*) n FROM tax_nao_encaixe GROUP BY eixo ORDER BY n DESC")

    # ── custo e roteamento, estes sim recortados pela rodada ────────────────
    onde, par = ("WHERE run_id=?", (run_id,)) if run_id else ("WHERE 1=1", ())
    uso = q(f"SELECT COUNT(*) n, COALESCE(SUM(custo_usd),0) usd, "
            f"COALESCE(SUM(tokens_entrada),0) tin, COALESCE(SUM(tokens_saida),0) tout, "
            f"COALESCE(SUM(erro IS NOT NULL),0) erros, COALESCE(SUM(erro LIKE '%cortada%'),0) cortadas, "
            f"COALESCE(strftime('%s',MAX(criado_em))-strftime('%s',MIN(criado_em)),0) seg "
            f"FROM log_llm {onde}", par)[0]
    prov = q(f"SELECT COALESCE(provedor,'(não registrado)') provedor, COUNT(*) n, "
             f"COALESCE(SUM(erro LIKE '%cortada%'),0) cortadas, "
             f"COALESCE(SUM(erro IS NOT NULL),0) erros, "
             f"ROUND(AVG(latencia_ms)/1000.0,1) lat, ROUND(MAX(latencia_ms)/1000.0,1) pior "
             f"FROM log_llm {onde} AND etapa='estagio_a' GROUP BY 1 ORDER BY n DESC", par)

    o: list[str] = []
    w = o.append
    w("# Relatório de massa — grade v1 (ticket 07, rodada 1)\n")
    w(f"- **Rodada**: `{run_id or '(log inteiro)'}` — Estágio A apenas, concorrência 4")
    w(f"- **Base**: {total} papers")
    w("- **Checagens**: `docs/spec-taxonomia-facetada.md`, seção *Operação*, passo 5\n")

    w("## 1. Cobertura\n")
    w("| | papers | % da base |")
    w("|---|---:|---:|")
    for rotulo, v in cobertura:
        w(f"| {rotulo} | {v} | {_pct(v, total):.1%} |")
    w("")

    w("## 2. Distribuição por área e sub-área\n")
    w(f"Percentual da sub-área **dentro da sua área**. Acima de {TETO_SUBAREA:.0%} falta")
    w(f"ramificar; abaixo de {PISO_SUBAREA_PCT:.0%} da área ou de {PISO_SUBAREA_N} papers, a")
    w("regra manda fundir.\n")
    w("| Área | Sub-área | papers | % da área | leitura |")
    w("|---|---|---:|---:|---|")
    acima, perto = [], []
    ultima = None
    for a in linhas:
        pct = _pct(a["n"], por_area[a["area"]])
        marca = ""
        if pct > TETO_SUBAREA:
            marca = f"**ramificar** (acima de {TETO_SUBAREA:.0%})"
            acima.append((a["area"], a["subarea"], a["n"], pct))
        elif pct < PISO_SUBAREA_PCT or a["n"] < PISO_SUBAREA_N:
            motivo = " e ".join(
                x for x in (
                    f"{pct:.1%} da área" if pct < PISO_SUBAREA_PCT else "",
                    f"{a['n']} papers" if a["n"] < PISO_SUBAREA_N else "",
                ) if x
            )
            marca = f"fundir ({motivo})"
        # Sub-area vazia nao esta "perto do piso": ela esta no chao, e a
        # decisao sobre ela nao tem ruido que a atrapalhe.
        if a["n"] and (abs(pct - TETO_SUBAREA) <= FOLGA
                       or abs(pct - PISO_SUBAREA_PCT) <= FOLGA):
            perto.append((f"{a['area']} > {a['subarea']}", a["n"], f"{pct:.1%} da área"))
            marca = f"{marca} · **no limiar**".lstrip(" ·")
        if a["area"] != ultima:
            ultima = a["area"]
            w(f"| **{ultima}** | _{por_area[ultima]} papers_ | | | |")
        w(f"| | {a['subarea']} | {a['n']} | {pct:.1%} | {marca} |")
    w("")
    w(f"**Checagem A — nenhuma sub-área acima de ~{TETO_SUBAREA:.0%} da sua área**: "
      f"{'FALHA' if acima else 'passa'}, {len(acima)} acima do teto.")
    for area, sub, n, pct in acima:
        w(f"  - {area} > {sub}: {n} papers, {pct:.1%}")
    w("")

    w("## 3. Distribuição por vertente\n")
    w(f"Abaixo de ~{PISO_VERTENTE:.0%} o rótulo é absorvido. O denominador da")
    w("checagem são os papers **classificados**, e não a base: com cobertura")
    w("total os dois coincidem, e com cobertura parcial só o primeiro mede o")
    w("rótulo em vez de medir o buraco. A coluna *dominante* conta só a vertente")
    w("de ordem 1 — um rótulo com massa e sem dominante nenhuma não define paper")
    w("algum, só acompanha.\n")
    w("| Vertente | papers | % da base | % dos classificados | dominante | leitura |")
    w("|---|---:|---:|---:|---:|---|")
    abaixo, perto_v = [], []
    for v in verts:
        pct = _pct(v["n"], classificados)
        marca = ""
        if pct < PISO_VERTENTE:
            marca = f"**absorver** (abaixo de {PISO_VERTENTE:.0%})"
            abaixo.append((v["vertente"], v["n"], pct))
        if v["n"] and abs(pct - PISO_VERTENTE) <= FOLGA:
            perto_v.append(
                (f"vertente {v['vertente']}", v["n"], f"{pct:.1%} dos classificados")
            )
            marca = f"{marca} · **no limiar**".lstrip(" ·")
        w(f"| {v['vertente']} | {v['n']} | {_pct(v['n'], total):.1%} | {pct:.1%} "
          f"| {v['dom'] or 0} | {marca} |")
    w("")
    w(f"Atribuições no total: {atribuicoes} para {classificados} papers "
      f"({atribuicoes / classificados if classificados else 0:.2f} por paper).")
    w(f"**Checagem B — nenhuma vertente abaixo de ~{PISO_VERTENTE:.0%}**: "
      f"{'FALHA' if abaixo else 'passa'}, {len(abaixo)} abaixo do piso.")
    for rot, n, pct in abaixo:
        w(f"  - {rot}: {n} papers, {pct:.1%}")
    w("")

    w("## 4. Não-encaixes por eixo\n")
    w("| Eixo | registros | % da base |")
    w("|---|---:|---:|")
    for r in nao:
        w(f"| {r['eixo']} | {r['n']} | {_pct(r['n'], total):.1%} |")
    soma = sum(r["n"] for r in nao)
    w(f"| **total** | {soma} | {_pct(soma, total):.1%} |")
    w("")

    w("## 5. Custo real contra a estimativa\n")
    seg = uso["seg"] or 0
    w("| | estimado | real |")
    w("|---|---:|---:|")
    w(f"| chamadas | {total} | {uso['n']} |")
    w(f"| custo | US$ 1,2300 | US$ {uso['usd']:.4f} |")
    w(f"| tokens de entrada | 13,9 M | {uso['tin'] / 1e6:.1f} M |")
    w(f"| tokens de saída | 0,7 M | {uso['tout'] / 1e6:.1f} M |")
    w(f"| duração | ~1,4 h | {seg / 3600:.2f} h |")
    w(f"| ritmo | 36,6 ch/min | {uso['n'] * 60 / seg if seg else 0:.1f} ch/min |")
    w("")
    if uso["n"]:
        w(f"Erros: {uso['erros']}. Respostas cortadas: {uso['cortadas']} "
          f"({_pct(uso['cortadas'], uso['n']):.1%} das chamadas).")
    w("")

    w("## 6. Roteamento — por provedor do OpenRouter\n")
    w("Os endpoints do OpenRouter não se comportam igual, e a coluna *pior* é o")
    w("que diz se a rodada aguentou: uma média boa esconde a cauda.\n")
    w("| Provedor | chamadas | cortadas | erros | latência média (s) | pior (s) |")
    w("|---|---:|---:|---:|---:|---:|")
    for p in prov:
        w(f"| {p['provedor']} | {p['n']} | {p['cortadas']} | {p['erros']} "
          f"| {p['lat']} | {p['pior']} |")
    w("")

    w("## 7. Rótulos perto de um limiar\n")
    w("A grade tem ~19% de instabilidade intrínseca: o mesmo paper, mesma")
    w("configuração, temperatura 0, recebe pares diferentes em cerca de uma em")
    w("cada cinco rodadas (81-82% de auto-concordância, três medições em")
    w("2026-09-08). Fundir um rótulo que está a poucos pontos do corte é decidir")
    w("sobre ruído — o ticket 08 precisa tratar esta lista à parte.\n")
    if perto or perto_v:
        for rot, n, onde_ in perto + perto_v:
            w(f"- **{rot}**: {n} papers, {onde_}")
    else:
        w("- nenhum rótulo caiu na faixa de incerteza.")
    w("")
    return "\n".join(o) + "\n"


def main() -> None:
    run_id = sys.argv[1] if len(sys.argv) > 1 else None
    saida = sys.argv[2] if len(sys.argv) > 2 else "docs/relatorio-massa-grade-v1.md"
    conn = sqlite3.connect(BANCO)
    try:
        texto = gerar(conn, run_id)
    finally:
        conn.close()
    with open(saida, "w", encoding="utf-8") as f:
        f.write(texto)
    print(f"{saida}: {len(texto.splitlines())} linhas")


if __name__ == "__main__":
    main()
