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

**Status:** done

- [x] Backup do banco tomado antes da primeira escrita
      (`data/hfpapers.db.pre-t06-20260908T084115`, 4,95 MB)
- [x] Papers de maio a agosto de 2026 presentes na base, com a contagem por mês
      conferida contra a amostragem — **2.641 papers retroativos** (01/05 a 13/08),
      base total de 525 para 3.166. Maio 856 e junho 892 caem dentro da faixa de
      700-900; **julho fecha em 602, 14% abaixo do piso**, e 01-13/08 traz 291 em
      9 dias úteis (~32/dia, o mesmo ritmo de agosto). A estimativa da spec errou
      para os dois lados: subestimou o total (2.641 contra ~2.100, +26%) e
      superestimou julho. Ver a nota abaixo, que o ticket 07 precisa ler.
- [x] Nenhum paper novo recebeu triagem nesta etapa — 0 linhas de `fato_triagem`
      entre os 2.641; as 522 existentes são todas de papers de 14/08 em diante
- [ ] Os papers retroativos ficam fora da janela viva do painel, pela data de daily
      — **não, e o critério é que está errado**: com a janela de 90 dias de
      `gerar_painel` (corte em 10/06/2026), 1.445 dos 2.641 caem *dentro* dela por
      data e só 1.196 ficam fora. O que o critério queria dizer se cumpre por outro
      caminho: nenhum deles aparece em lista alguma do painel, porque a aba viva e
      as duas listas do hall exigem linha em `fato_triagem`. Eles só engordam o chip
      de pendentes — exatamente o efeito colateral que este ticket já previa no
      texto acima, e que contradiz o próprio critério. O painel não foi tocado.
- [x] O custo de LLM da etapa é zero — 0 linhas em `log_llm` com `run_id LIKE 'retro-%'`
      (total da tabela intacto em 2.815), e US$ 0,00 nas três execuções `retro-`
- [x] Uma interrupção no meio pode ser retomada sem duplicar paper — provado duas
      vezes: a varredura real morreu no 429 da HF com 1.508 papers e a retomada
      seguiu do dia 87 pendente sem duplicar; e a varredura repetida ponta a ponta
      depois de pronta coletou 0 e deixou a contagem em 3.166

**Nota de volume para o ticket 07:** a base a classificar é de 3.166 papers, não os
~2.600 da spec. Ao custo medido do Estágio A (US$ 0,000256/paper) são ~US$ 0,81 só na
primeira rodada, contra os ~US$ 0,67 previstos.

**Nota de operação:** 5 req/s derruba a API da HF com HTTP 429 depois de ~1.000
requisições seguidas. A varredura longa rodou a 2 req/s com `tentativas: 6` e
`backoff_inicial_s: 10`, por `HFPAPERS_CONFIG` apontando para uma cópia do
`config.yaml`. O `config.yaml` do repositório não foi alterado: a rodada diária são
~30 papers e nunca chega perto do teto.
