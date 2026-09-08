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

**Status:** ready-for-agent

- [ ] Backup do banco tomado antes da rodada
- [ ] Toda a base classificada na grade v2, com `run_id` único
- [ ] Todo aprovado, retroativo ou não, tem ficha
- [ ] O hall exibe os trimestres retroativos, cada um com seu ranking
- [ ] Nenhum paper aprovado aparece no hall sem ficha
- [ ] Os Parquet trazem área, sub-área, vertente e ordem da vertente
- [ ] O diagnóstico sem rede sai com código 0
- [ ] O painel é gerado sem erro e sem corte por vertente
