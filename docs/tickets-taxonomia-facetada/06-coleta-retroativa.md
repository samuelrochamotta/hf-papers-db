# 06: Coleta retroativa de três meses

**O que construir:** os papers de maio a agosto de 2026 — cerca de 2.100, anteriores ao
início do pipeline — entram na base com metadados e enriquecimento, sem classificação.
É o que leva a mediana por sub-área de cerca de 4 para cerca de 15 papers, a faixa em
que dá para distinguir uma sub-área real do ruído de um mês.

A coleta força a data dia a dia e roda só os estágios de coleta e enriquecimento. A API
de daily papers serve datas retroativas sem restrição, a cinco requisições por segundo,
e o volume medido por amostragem é de 700 a 900 papers por mês.

Não depende de nada da taxonomia e pode rodar em paralelo com os tickets 01 a 05.
**Efeito colateral esperado enquanto 07 não roda:** o painel exibirá cerca de 2.100
papers no chip de pendentes. Está correto — nunca classificado não é o mesmo que
`fora` —, apenas fica visualmente estranho até a rodada de classificação.

**Bloqueado por:** nenhum (pode começar imediatamente).

**Status:** ready-for-agent

- [ ] Backup do banco tomado antes da primeira escrita
- [ ] Papers de maio a agosto de 2026 presentes na base, com a contagem por mês
      conferida contra a amostragem
- [ ] Nenhum paper novo recebeu triagem nesta etapa
- [ ] Os papers retroativos ficam fora da janela viva do painel, pela data de daily
- [ ] O custo de LLM da etapa é zero
- [ ] Uma interrupção no meio pode ser retomada sem duplicar paper
