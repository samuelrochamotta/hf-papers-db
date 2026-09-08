# ADR 001 — Os três itens fora de escopo do mapa

- **Data**: 2026-09-05
- **Estado**: aceito
- **Contexto**: seção 8 da `spec-mesmo-pipeline-e-painel.md`

> **Nota de 08/09/2026, sem alterar o texto abaixo.** A decisão 3 cita
> `registrar_candidato` para explicar por que a escrita no banco segue na ordem
> original dos papers. Esse mecanismo deixou de existir com a taxonomia facetada
> (`spec-taxonomia-facetada.md`): a classificação não promove mais rótulo
> nenhum, e o que ela grava é o não-encaixe em `tax_nao_encaixe`. **A decisão
> continua valendo e a razão também** — a ordem de escrita ainda é determinística
> por desenho, e agora o exemplo é a ponte de área. O princípio da decisão 1
> (uma fonte de verdade por decisão) é o que fundamenta não versionar a grade
> antiga.

## Contexto

A spec fechou o mapa deixando três itens de fora, sem decidi-los: *rubrica com
pontuação*, *mudanças no Power BI além das colunas novas dos Parquet* e
*concorrência no estágio 3 para encurtar a rodada total*. Este ADR os decide.
Dois morrem, um foi implementado.

## Decisão

### 1. Rubrica com pontuação — não

O veredito já decorre da lista de critérios: os tickets 03 e 06 fizeram
`criterios_veredito` ser a causa do veredito, não um comentário sobre ele
(`estrito` prevalece quando os lados se misturam; `exige_acesso_interno` é
excludente). Uma rubrica que somasse pontos seria uma **segunda fonte de
verdade para o mesmo veredito** — e no dia em que as duas discordassem, o
pipeline teria de escolher uma e a outra viraria ruído. Isso reabre exatamente
o que o mapa fechou.

O que a pontuação daria de útil — "quão forte é esta aprovação" — já sai do
card *Por que o pipeline aprova* (ticket 11): um paper aprovado por três
critérios aparece em três barras, e a leitura de força vem da contagem por
ocorrência, sem inventar uma escala.

### 2. Power BI além das colunas novas — fora

Não há `.pbix` no repositório: o Power BI lê os Parquet de `marts/` e o modelo
vive fora do git. Mudar o relatório não é mudança de código, e não há como
versioná-la aqui. O que falta é **documentar** `ponte_paper_criterio` e
`fato_triagem.fronteira_contraparte` na seção *Modelo de dados* do README —
tarefa da seção 6 da spec, não deste ADR.

### 3. Concorrência no estágio 3 — implementada

É o único dos três com valor mensurável. A rodada total é sequencial: com
A ≈ 65 s e B ≈ 127 s por paper (spec, seção 3), 482 papers e ~30% chegando ao
Estágio B, o piso é

```
482 × 65 s  +  145 × 127 s  ≈  49.700 s  ≈  13,8 h
```

(a spec estima 8–10 h com uma fração de candidatos menor; a ordem de grandeza é
a mesma). É tempo de espera de rede, não de CPU: paralelizar o I/O divide isso
por N.

| `--concorrencia` | pela conta acima | pela estimativa da spec |
|---|---|---|
| 1 (padrão) | 13,8 h | 8–10 h |
| 4 | 3,5 h | 2,0–2,5 h |
| 8 (teto) | 1,7 h | 1,0–1,3 h |

Duas restrições moldaram o desenho:

- **O paralelismo é só do I/O do OpenRouter.** Toda escrita no banco continua
  na thread principal e na ordem original dos papers. `registrar_candidato`
  acumula quórum e promove: drenar por ordem de chegada daria vocabulário
  diferente a cada rodada. Numa rodada **que completa**, `concorrencia=4`
  termina com o banco idêntico ao de `concorrencia=1` — inclusive a ordem das
  linhas de `log_llm`. Numa rodada que estoura no meio, não: ver *Consequências*.
- **`concorrencia == 1` é o caminho de hoje, letra por letra**: sequencial, sem
  pool, sem thread. A rodada diária são ~30 papers e não ganha nada com
  paralelismo, enquanto a rajada é o modo de falha real do provedor.

O padrão em `config.yaml` é 1 e quem pede mais é a linha de comando
(`reclassificar --concorrencia N`). Teto de 8: a issue #1 registra 404 de
roteamento, 429 e timeout **em rajada**, e cada uma custa o retry interno mais,
no Estágio B, uma segunda passada inteira — acima de 8 o tempo economizado
começa a voltar como retentativa. Valor fora da faixa é cortado com aviso, não
recusado: abortar uma varredura de horas por causa de um dígito é pior que
rodá-la mais devagar.

## Consequências

- O veredito continua com uma fonte só. Quem quiser força de aprovação lê o
  card do painel, não um número novo no banco.
- O README ganha as colunas novas no *Modelo de dados* (bloco 6); nada mais
  muda no lado do Power BI.
- A rodada total do passo 2 da seção 3 da spec passa a ser
  `reclassificar --tudo --concorrencia 4` — de uma noite para uma manhã.
- A rodada diária não mudou de comportamento: mesma sequência, mesmas
  gravações, mesma conta.
- **Rodada que estoura no meio gasta mais do que aproveita.** Os workers vão
  adiante da thread principal, então quando a varredura cai há papers já pagos
  que nunca virão a ter triagem: medido com `concorrencia=4` e um paper travado,
  2 triagens gravadas contra 10 papers já em `log_llm`. Com `concorrencia=1`
  isso não acontece — nada é chamado adiante do paper que estoura. Nenhuma linha
  se perde: o gasto desses papers fica em `log_llm` (e portanto em
  `hfpapers custos`), mas **fora** de `res.uso` e de `log_execucao.custo_usd`,
  que contam só o que virou triagem. No pior caso são ~US$ 0,04; limitar o
  adiantamento custaria código para economizar isso.
- Acima de `concorrencia=1`, **Ctrl+C não devolve o terminal na hora**: espera
  as chamadas em voo, no pior caso ~18 min. É inerente ao `concurrent.futures`.
  Matar o processo no lugar de esperar arrisca interromper uma gravação — o
  help do `--concorrencia` avisa.
- De brinde, `classificacao.rodar` passou a aceitar o acumulador de quem chama:
  varredura que estoura no meio não fecha mais `log_execucao` com zeros depois
  de horas de trabalho.
