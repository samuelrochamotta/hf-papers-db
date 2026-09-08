# 09: Rodada 2, fichas retroativas e painel

**O que construir:** a base inteira na grade v2, os aprovados retroativos com ficha, e o
produto refletindo tudo isso. O hall ganha os trimestres anteriores — onde hoje há 25
dias de acervo, passa a haver três meses e meio — e nenhum aprovado aparece lá sem
conteúdo.

Duas etapas de LLM: a reclassificação na v2 (Estágio A, cerca de US$ 0,54) e o Estágio B
nos aprovados retroativos que ainda não têm ficha (cerca de 525, cerca de US$ 0,25).

O painel apenas **lê** os campos novos. O corte por vertente — o filtro transversal que
responderia "tudo que barateia, seja em serving, contexto ou harness" — fica fora deste
ticket por decisão da spec: é a peça que mais depende de ver a distribuição real, e
fazê-la antes significaria refazê-la.

**Bloqueado por:** 08.

**Status:** done

- [x] Backup do banco tomado antes da rodada — `data/hfpapers.db.pre-t09-20260908-173502`
      (19,5 MB, `integrity_check ok`), pela API de backup do SQLite: o banco é WAL e
      `cp` copiaria um arquivo sem o que ainda está no journal
- [x] Toda a base classificada na grade v2, com `run_id` único — `run-20260908-173724`,
      3.166 de 3.166 linhas de `fato_triagem`, nenhuma de outra rodada e nenhum paper
      sem triagem. 61,5 min a concorrência 4, **US$ 2,0406**, zero truncamentos e
      7 `ErroPrazo` em 4.407 chamadas (0,16%), todos recuperados na retentativa
- [x] Todo aprovado, retroativo ou não, tem ficha — 1.093 aprovados (348 amplo, 745
      estrito) e 1.093 fichas; zero aprovado sem ficha e zero ficha órfã
- [x] O hall exibe os trimestres retroativos, cada um com seu ranking — **um**
      trimestre, 2026-T2, com o ranking dos 10 aprovados e dos 10 descartados mais
      votados: 1.748 papers, 604 aprovados, 1.144 descartados, nenhum sem triagem.
      É o único que existe: o corte do hall é `refresh.janela_morna_dias` (90 dias,
      10/06/2026) e todo o 3º trimestre ainda está na aba viva, que passou de 455
      para 1.970 papers e de ~2.100 pendentes para zero
- [x] Nenhum paper aprovado aparece no hall sem ficha — zero no hall e zero na aba viva
- [x] Os Parquet trazem área, sub-área, vertente e ordem da vertente — conferido lendo
      os arquivos: `ponte_paper_area` com `area`+`subarea` (3.158 primárias, 587
      secundárias, 64 sub-áreas distintas) e `ponte_paper_vertente` com `ordem`
      (3.166 de ordem 1, 680 de ordem 2). `dim_area` passou a levar **`area_pai`**,
      que faltava: sem ela a dimensão chegava ao Power BI como 74 rótulos planos, sem
      dizer qual é raiz nem de quem cada sub-área é filha
- [x] O diagnóstico sem rede sai com código 0 — `doutor --sem-rede`, nenhum item em
      erro, `regra_fora` ok em todo `fora`
- [x] O painel é gerado sem erro e sem corte por vertente — 2.489 KB; a vertente só é
      exibida no card (`p.vt`), não existe filtro por ela em `painel_app.js`

**Custo, estimativa contra real:** as cifras do texto acima são da grade v1 e ficaram
para trás. A estimativa refeita antes de disparar, a partir do custo medido da rodada 1
e de um dia real reclassificado (29 papers, US$ 0,0183), foi de **US$ 2,00** — Estágio A
3.166 × US$ 0,000472 = US$ 1,49, mais Estágio B ~1.100 × US$ 0,00046 = US$ 0,51. O real
foi **US$ 2,0406** (A US$ 1,4968 em 3.172 chamadas, B US$ 0,5707 em 1.235), 2% acima. O
Estágio B foi muito maior que os "cerca de 525" do texto: quem chega lá é todo candidato
do Estágio A, não só o aprovado retroativo, e foram 1.093 fichas gravadas contra as 176
que a base tinha.

**Medição da rodada 2:** `docs/relatorio-massa-grade-v2.md`. As duas checagens continuam
falhando, com números melhores e um deslocamento novo: a checagem A caiu de 15 para 7
sub-áreas acima de 25%, e a checagem B trocou de réu — *Especificar* piorou de 1,5% para
**1,1%** e *Adaptar*, que a v1 media em 2,3%, caiu para **1,2%**. As duas perderam massa
para `Treinar`, que nasceu com 45,3% da base e é agora o rótulo maior; *Baratear* caiu de
33,6% para 16,6%, confirmando a suspeita do ticket 08 de rótulo inflado por falta de
vizinho. As 21 sub-áreas novas receberam papers — **todas as 21**, 1.011 papers no total
—, e nenhuma das 64 ficou vazia.
