"""Relatorio de massa da grade facetada: le o banco e escreve o Markdown.

E o instrumento das duas checagens objetivas da spec (secao *Operacao*, passo 5),
e por isso mora aqui e nao numa consulta ad hoc: o ticket 08 deriva a grade v2
destas contagens, e uma contagem que ninguem consegue repetir nao serve de base
para fundir rotulo nenhum.

    python scripts/relatorio_massa.py <run_id> [saida.md] [estimativa_usd]

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


def gerar(
    conn: sqlite3.Connection, run_id: str | None, estimativa_usd: float | None = None
) -> str:
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
    # O desacordo de parentesco tem tratamento proprio porque nao e o mesmo
    # sinal: a area serviu e a sub-area existe - o que nao serviu foi a linha
    # entre as duas. E a unica entrada da fila que aponta um conserto concreto.
    parentesco = q("SELECT replace(justificativa, 'par rejeitado pelo parentesco "
                   "da grade: ', '') par, COUNT(*) n FROM tax_nao_encaixe "
                   "WHERE justificativa LIKE 'par rejeitado%' GROUP BY par ORDER BY n DESC")

    # ── custo e roteamento, estes sim recortados pela rodada ────────────────
    onde, par = ("WHERE run_id=?", (run_id,)) if run_id else ("WHERE 1=1", ())
    uso = q(f"SELECT COUNT(*) n, COALESCE(SUM(custo_usd),0) usd, "
            f"COALESCE(SUM(tokens_entrada),0) tin, COALESCE(SUM(tokens_saida),0) tout, "
            f"COALESCE(SUM(erro IS NOT NULL),0) erros, COALESCE(SUM(erro LIKE '%cortada%' OR erro LIKE '%Unterminated%'),0) cortadas, "
            f"COALESCE(SUM(erro LIKE 'ErroPrazo%'),0) prazo, "
            f"COALESCE(SUM(CASE WHEN erro IS NOT NULL THEN custo_usd END),0) usd_erro, "
            f"COALESCE(strftime('%s',MAX(criado_em))-strftime('%s',MIN(criado_em)),0) seg "
            f"FROM log_llm {onde}", par)[0]
    prov = q(f"SELECT COALESCE(provedor,'(não registrado)') provedor, COUNT(*) n, "
             f"COALESCE(SUM(erro LIKE '%cortada%' OR erro LIKE '%Unterminated%'),0) cortadas, "
             f"COALESCE(SUM(erro LIKE 'ErroPrazo%'),0) prazo, "
             f"COALESCE(SUM(erro IS NOT NULL),0) erros, "
             f"ROUND(AVG(latencia_ms)/1000.0,1) lat, ROUND(MAX(latencia_ms)/1000.0,1) pior, "
             # `latencia_ms` conta do inicio do laco de `chamar`, entao uma linha
             # de tentativa 3 carrega as duas anteriores e os dois backoffs. Sem
             # esta coluna o relatorio anuncia pior caso de 115,8 s numa rodada
             # cuja chamada mais lenta levou 19,1 s - e faz o teto de 90 s
             # parecer furado quando ele estava funcionando.
             f"ROUND(MAX(CASE WHEN tentativas=1 THEN latencia_ms END)/1000.0,1) pior1 "
             f"FROM log_llm {onde} GROUP BY 1 ORDER BY n DESC", par)

    o: list[str] = []
    w = o.append
    # O título não cita versão da grade nem número de rodada: o script não tem
    # como saber nem uma coisa nem outra, e o texto fixo da v1 saiu carimbado no
    # relatório da rodada 2, dizendo "grade v1" sobre a medição da v2. Quem
    # nomeia a versão é o arquivo de saída.
    w("# Relatório de massa da grade facetada\n")
    w(f"- **Rodada**: `{run_id or '(log inteiro)'}`")
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
    if parentesco:
        w("### Desacordo de parentesco\n")
        w("Estes não são rótulos inventados: os dois lados existem na grade, e o")
        w("que o modelo recusou foi de quem a sub-área é filha. É a entrada da")
        w("fila que aponta um conserto concreto — mudar o pai, e não criar rótulo.\n")
        w("| Par que o modelo tentou | papers | onde a grade pendura a sub-área |")
        w("|---|---:|---|")
        for r in parentesco:
            sub = r["par"].split(" > ")[-1]
            pai = um("SELECT area_pai FROM dim_area WHERE area = ?", (sub,)) or "—"
            w(f"| {r['par']} | {r['n']} | {pai} |")
        w("")

    seg = uso["seg"] or 0
    # A estimativa entra por parametro, e nao fixa no codigo: ela e do momento em
    # que a rodada foi disparada, e uma constante aqui viraria mentira na rodada
    # seguinte - a coluna "estimado" da rodada 2 anunciava os numeros da 1.
    if estimativa_usd is not None:
        w("## 5. Custo real contra a estimativa\n")
        w("| | estimado | real |")
        w("|---|---:|---:|")
        # So o custo e estimado; o resto sai em branco em vez de repetir o
        # numero de papers como se fosse previsao de chamadas - a rodada de dois
        # estagios faz mais de uma por paper.
        w(f"| chamadas | — | {uso['n']} |")
        w(f"| custo | US$ {estimativa_usd:.4f} | US$ {uso['usd']:.4f} |")
        erro_pct = (uso["usd"] / estimativa_usd - 1) if estimativa_usd else 0
        w(f"| tokens de entrada | — | {uso['tin'] / 1e6:.1f} M |")
        w(f"| tokens de saída | — | {uso['tout'] / 1e6:.1f} M |")
        w(f"| duração | — | {seg / 3600:.2f} h |")
        w(f"| ritmo | — | {uso['n'] * 60 / seg if seg else 0:.1f} ch/min |")
        w("")
        w(f"A estimativa errou por {erro_pct:+.1%}.")
    else:
        w("## 5. Custo real\n")
        w("| | real |")
        w("|---|---:|")
        w(f"| chamadas | {uso['n']} |")
        w(f"| custo | US$ {uso['usd']:.4f} |")
        w(f"| tokens de entrada | {uso['tin'] / 1e6:.1f} M |")
        w(f"| tokens de saída | {uso['tout'] / 1e6:.1f} M |")
        w(f"| duração | {seg / 3600:.2f} h |")
        w(f"| ritmo | {uso['n'] * 60 / seg if seg else 0:.1f} ch/min |")
    w("")
    if uso["n"]:
        w(f"Erros: {uso['erros']}. Respostas cortadas: {uso['cortadas']} "
          f"({_pct(uso['cortadas'], uso['n']):.1%} das chamadas) — a conta inclui o "
          "`json invalido: Unterminated string`, que é corte com outro nome.")
    if uso["erros"]:
        # `log_execucao.custo_usd` conta so o que virou triagem; `log_llm` conta o
        # que o OpenRouter cobrou. A tentativa que erra e refeita aparece so no
        # segundo, e conciliar fatura pelo primeiro deixa a diferenca sem dono.
        w("")
        w(f"O custo acima é o do `log_llm` — **tudo o que foi cobrado**, inclusive as "
          f"{uso['erros']} chamadas que erraram e foram refeitas "
          f"(US$ {uso['usd_erro']:.4f}). `log_execucao.custo_usd` conta só o que virou "
          "triagem, e por isso é menor: os dois estão certos e medem coisas diferentes.")
    if uso["prazo"]:
        # A chamada abandonada pelo `llm.prazo_total_s` foi cobrada e sai com uso
        # zero: os tokens vinham na resposta que ninguem leu. O custo real e o da
        # tabela mais estas - dize-lo aqui evita conciliar a fatura no escuro.
        w("")
        w(f"Abandonadas pelo prazo (`llm.prazo_total_s`): {uso['prazo']} "
          f"({_pct(uso['prazo'], uso['n']):.1%}). **O custo acima as subestima** — "
          "elas foram cobradas e saíram com uso zero, porque os tokens vinham na "
          "resposta que nunca foi lida.")
    w("")

    w("## 6. Roteamento — por provedor do OpenRouter\n")
    w("Os endpoints do OpenRouter não se comportam igual, e a cauda é o que diz")
    w("se a rodada aguentou: uma média boa a esconde. Mas leia a coluna certa —")
    w("*pior 1ª tent.* é o provedor; *pior acum.* conta do início do laço de")
    w("`chamar`, então numa linha de tentativa 3 ela carrega as duas anteriores e")
    w("os backoffs. É tempo do paper, não da chamada.\n")
    w("A linha *(não registrado)* concentra as chamadas que morreram antes da")
    w("resposta — inclusive as abandonadas pelo prazo: quem não respondeu não")
    w("informou quem era, e atribuí-las a um provedor seria acusar inocente.\n")
    w("| Provedor | chamadas | cortadas | prazo | erros | média (s) | pior 1ª tent. (s) | pior acum. (s) |")
    w("|---|---:|---:|---:|---:|---:|---:|---:|")
    for p in prov:
        w(f"| {p['provedor']} | {p['n']} | {p['cortadas']} | {p['prazo']} | {p['erros']} "
          f"| {p['lat']} | {p['pior1']} | {p['pior']} |")
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
    estimativa = float(sys.argv[3]) if len(sys.argv) > 3 else None
    conn = sqlite3.connect(BANCO)
    try:
        texto = gerar(conn, run_id, estimativa)
    finally:
        conn.close()
    with open(saida, "w", encoding="utf-8") as f:
        f.write(texto)
    print(f"{saida}: {len(texto.splitlines())} linhas")


if __name__ == "__main__":
    main()
