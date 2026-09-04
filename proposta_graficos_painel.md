# Proposta de revisão dos gráficos do painel

Assumindo que a cobertura de `regra_fora` será corrigida, o **Pareto dos motivos de descarte entra no painel e substitui “Perfil do aprovado”**. Isso deixa a composição mais orientada a decisões sem aumentar excessivamente o tamanho da página.

## Substituição gráfico a gráfico

| Gráfico atual | Decisão | Substituição ou complemento |
|---|---|---|
| **O lote diário e o que sobrou dele** | **Fica** | Recebe abaixo uma linha de **taxa diária de aprovação**. As barras mostram carga de trabalho; a linha mostra mudança de seletividade. Preferencialmente em painéis alinhados, sem eixo duplo. |
| **Perfil do aprovado** | **Sai** | Substituído pelo **Pareto dos motivos de descarte**. O Pareto explica diretamente onde o pipeline está cortando papers, enquanto o perfil mostra apenas associações indiretas entre atributos e aprovação. |
| **Área primária** | **Fica** | Recebe a **matriz área primária × área secundária** como visualização alternável: `Distribuição | Cruzamentos`. |
| **Tópicos mais atribuídos** | **Sai** | Substituído pelo **heatmap tópico × tempo**, preservando à direita de cada linha o total do período e a taxa de aprovação. |
| **Votos por veredito** | **Sai** | Substituído pela **curva de maturação dos votos por veredito**, normalizada por dias desde a entrada no HF. |
| **Votos & comentários** | **Sai** | Substituído pela dispersão **upvotes no HF × stars no GitHub**. Comentários permanecem disponíveis no tooltip. |
| **Quem pegou tração** | **Sai** | Consolidado na **curva de maturação**. Os cinco papers com maior velocidade podem aparecer numa lista lateral do mesmo card. |

## Como ficam os novos gráficos

### Taxa de aprovação ao longo do tempo

Complementa o volume diário:

- `% aprovado`, calculado como `(estrito + amplo) / total`;
- decomposição opcional entre `% estrito` e `% amplo`;
- média móvel dos últimos cinco dias de publicação;
- volume e quantidades absolutas no tooltip;
- mesmo eixo temporal do gráfico de volume.

A taxa mede a seletividade do pipeline. Ela não deve ser apresentada como medida de qualidade ou acurácia.

### Pareto dos motivos de descarte

Substitui “Perfil do aprovado”:

- barras horizontais ordenadas por quantidade;
- uma barra por `regra_fora`;
- linha de percentual acumulado;
- quantidade e percentual diretamente rotulados;
- opção de alternar entre `quantidade` e `% dos descartados`;
- clique numa barra para filtrar o restante do painel;
- cobertura de `regra_fora` informada no subtítulo.

Mesmo após a melhoria da cobertura, registros sem regra devem aparecer como `regra não registrada`, evitando desaparecimento silencioso de dados.

### Heatmap tópico × tempo

Substitui o ranking estático de tópicos:

- linhas: tópicos;
- colunas: dias ou semanas;
- intensidade: participação do tópico no lote daquele período;
- colunas adicionais à direita: total no período e `% aprovado`;
- ordenação por volume total, crescimento recente ou taxa de aprovação;
- clique na célula aplica os filtros de tópico e período.

Se a janela produzir colunas demais, o gráfico deve mudar automaticamente de dia para semana.

### Matriz área primária × área secundária

Entra como visualização alternativa do card “Área primária”:

- linhas: área primária;
- colunas: área secundária;
- intensidade: quantidade ou percentual de papers;
- diagonal vazia ou visualmente neutralizada;
- tooltip com total, aprovados, descartados e taxa de aprovação;
- clique numa célula filtra a combinação de áreas.

O gráfico atual de áreas continua como visualização padrão porque apresenta melhor os totais marginais e a composição por veredito.

### Curva de maturação dos votos

Substitui “Votos por veredito” e “Quem pegou tração”:

- eixo X: dias desde `data_hf_daily`;
- eixo Y: votos acumulados;
- uma linha mediana por veredito;
- faixa P25–P75 ao redor de cada linha;
- quantidade de papers observados em cada idade no tooltip;
- escala visual `log1p`, mantendo os rótulos em votos reais;
- lista lateral com os cinco papers de maior velocidade recente.

A idade deve ser calculada a partir de `data_hf_daily`, não do primeiro snapshot. Isso corrige uma fragilidade do gráfico atual: o texto diz “dia da publicação”, mas o cálculo usa o primeiro snapshot disponível em `scripts/painel_app.js`.

### Upvotes no HF × stars no GitHub

Substitui “Votos & comentários”:

- incluir somente papers com repositório;
- eixo X: upvotes atuais no HF;
- eixo Y: stars atuais no GitHub;
- escalas `log1p`;
- cor por veredito;
- página de projeto diferenciada por forma ou contorno;
- comentários, área, idade e organização no tooltip;
- rótulos permanentes somente para outliers.

Stars igual a zero precisa continuar diferente de “paper sem repositório”. Papers sem repositório não entram na dispersão.

### Defasagem arXiv → HF Daily

Entra como gráfico adicional na seção de volume:

- defasagem calculada como `data_hf_daily - data_arxiv`;
- box plot por veredito;
- unidade em dias;
- mediana e intervalo interquartil;
- outliers identificáveis;
- opção de alternar o agrupamento entre veredito e área.

Valores negativos, caso apareçam, não devem ser corrigidos silenciosamente: precisam ser destacados como possível problema de dados.

## Organização final do painel

Uma disposição coerente seria:

1. **Volume e recência**
   - O lote diário e o que sobrou dele
   - Taxa de aprovação ao longo do tempo
   - Defasagem arXiv → HF Daily

2. **Vocabulário e cruzamentos**
   - Área primária, com alternância para matriz primária × secundária
   - Heatmap tópico × tempo

3. **Regras do corte**
   - Pareto dos motivos de descarte

4. **Atenção e adoção**
   - Curva de maturação dos votos
   - Upvotes no HF × stars no GitHub

5. **Fichas**
   - Lista detalhada atual, sem mudança estrutural

## Definição final

### Gráficos que ficam

- **O lote diário e o que sobrou dele**
- **Área primária**

### Gráficos que saem

- **Perfil do aprovado**
- **Tópicos mais atribuídos**
- **Votos por veredito**
- **Votos & comentários**
- **Quem pegou tração**

### Gráficos que entram

- **Taxa de aprovação ao longo do tempo**
- **Pareto dos motivos de descarte**
- **Heatmap tópico × tempo**
- **Matriz área primária × área secundária**, alternável com “Área primária”
- **Curva de maturação dos votos por veredito**
- **Upvotes no HF × stars no GitHub**
- **Defasagem arXiv → HF Daily**

Assim, dos sete gráficos atuais, dois permanecem e cinco são substituídos. Entram sete análises, mas aproximadamente oito gráficos ficam visíveis simultaneamente, porque a matriz de áreas compartilha o card com “Área primária” e a curva de maturação assume o papel de dois gráficos antigos.

## Especificação resumida para implementação

| Novo gráfico | Dados e cálculo | Representação | Interação e comportamento esperado |
|---|---|---|---|
| **Taxa de aprovação ao longo do tempo** | Agrupar os papers filtrados por `p.d`. Calcular `total`, `estrito`, `amplo`, `fora` e `taxa = (estrito + amplo) / total`. Média móvel sobre os cinco últimos dias de publicação disponíveis. | Linha principal para taxa total; linhas opcionais mais discretas para estrito e amplo. Eixo Y fixo de 0% a 100%. Deve ficar alinhado temporalmente ao gráfico de volume. | Respeita todos os filtros globais. Tooltip mostra data, total, contagens e percentuais. Com menos de oito datas, ocultar a média móvel e enfatizar pontos individuais. |
| **Pareto dos motivos de descarte** | Considerar somente `p.v === "fora"`. Agrupar por `p.rf`, ordenar por quantidade decrescente e calcular participação e percentual acumulado. Nulos viram `regra não registrada`. | Barras horizontais para quantidade e linha para percentual acumulado, com eixo acumulado de 0% a 100%. | Clique em uma regra alterna o filtro correspondente. Para isso, adicionar `regrasFora` ao estado e à função de filtragem. Tooltip mostra quantidade, percentual e acumulado. |
| **Heatmap tópico × tempo** | Usar os tópicos de `p.tp`. Para cada tópico e período, calcular `papers com o tópico / total de papers do período`. Totais devem contar papers, não ocorrências duplicadas. | Linhas por tópico e colunas por dia ou semana. Intensidade representa participação percentual. Colunas finais mostram total e taxa de aprovação. | Clique numa célula aplica tópico e período; clique no nome aplica apenas tópico. Usar dias com até aproximadamente 24 colunas e semanas acima disso. Permitir ordenar por volume, crescimento ou aprovação. |
| **Matriz área primária × secundária** | Cruzar `p.a` com cada elemento de `p.as`. Cada paper pode contribuir para várias células, uma por área secundária. Calcular total, aprovados e taxa por célula. | Heatmap quadrado ou retangular. Linhas representam a área primária; colunas, a secundária. Diagonal neutra. | Alternância `Distribuição | Cruzamentos` no card de áreas. Clique numa célula filtra a combinação. Se o filtro global precisar representar áreas secundárias, adicionar `areasSec` ao estado. |
| **Curva de maturação dos votos** | Para cada ponto de `DADOS.serie[p.id]`, calcular `idade = data_snapshot - p.d`. Para cada idade e veredito, calcular mediana, P25, P75 e quantidade observada. Não interpolar snapshots ausentes. | Uma linha mediana por veredito, com faixa P25–P75. Eixo X em dias desde o HF Daily; eixo Y em escala `log1p`, com valores reais nos rótulos. | Respeita os filtros globais. Tooltip mostra idade, mediana, quartis e tamanho da amostra. Não desenhar ponto agregado com amostra muito pequena; usar `n ≥ 5` como mínimo recomendado. Lista lateral mostra os cinco maiores crescimentos recentes normalizados pelo intervalo observado. |
| **Upvotes no HF × stars no GitHub** | Considerar apenas `p.oa === 1`. Usar `p.u` no eixo X e `p.gs` no Y. Zero stars continua válido. Veredito, comentários, área, organização, página de projeto e idade ficam como contexto. | Dispersão com escalas `log1p`. Cor por veredito; forma ou contorno diferencia presença de página de projeto. Rótulos somente nos outliers. | Tooltip mostra título, upvotes, stars, comentários, veredito, área e organização. Clique pode abrir ou selecionar o paper. Deve haver estado vazio específico quando o recorte não contiver repositórios. |
| **Defasagem arXiv → HF Daily** | Calcular a diferença em dias entre `p.d` e `p.da`. Agrupar inicialmente por veredito; oferecer área como agrupamento alternativo. Preservar valores negativos para auditoria. | Box plot com mediana, P25, P75, hastes e pontos para outliers. Mostrar `n` de cada grupo. | Respeita os filtros globais. Tooltip do grupo mostra quartis e amostra; tooltip do outlier mostra paper e datas. Para grupos com menos de cinco papers, exibir pontos individuais em vez de uma caixa estatisticamente fraca. |
