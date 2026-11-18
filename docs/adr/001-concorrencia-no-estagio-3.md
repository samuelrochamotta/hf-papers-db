# ADR 001 — Concorrência no estágio 3, só no I/O do OpenRouter

- **Data**: 2026-09-05 (reescrito em 2026-11-18)
- **Estado**: aceito
- **Contexto**: `src/hfpapers/estagios/classificacao.py`, `llm.concorrencia` no
  `config.yaml`, `reclassificar --concorrencia N`

> **Nota de 18/11/2026.** O texto original decidia três itens que a spec do mapa
> tinha deixado de fora. Dois deles perderam o objeto: a rubrica com pontuação
> (os critérios de veredito saíram no ADR 004) e o consumo dos Parquet (o ADR
> 005 e o ADR 008 tratam disso). Ficou só a concorrência, e o princípio que
> motivava recusar a rubrica: **uma fonte de verdade por decisão**.

## Contexto

A rodada é sequencial, e o tempo dela é espera de rede, não CPU: o Estágio A
leva ~65 s por paper e o B ~127 s, e só ~30% dos papers chegam ao B. A rodada
diária (~30 papers) cabe nisso. A reclassificação total, de milhares de papers,
leva uma noite inteira.

## Decisão

`reclassificar --concorrencia N` paraleliza as chamadas ao OpenRouter. Duas
restrições moldam o desenho:

- **O paralelismo é só do I/O do OpenRouter.** Toda escrita no banco continua
  na thread principal e na ordem original dos papers. `fato_triagem.revisao` é
  lida e incrementada, e `log_llm.id` é AUTOINCREMENT, então drenar por ordem
  de chegada daria um banco diferente a cada rodada. Numa rodada **que
  completa**, `concorrencia=4` termina com o banco idêntico ao de
  `concorrencia=1`, inclusive a ordem das linhas de `log_llm`.
- **`concorrencia == 1` é o caminho sem pool nem thread.** A rodada diária não
  ganha nada com paralelismo, e a rajada é o modo de falha real do provedor.

O padrão em `config.yaml` é 1. Quem pede mais é a linha de comando. O teto é 8:
a issue #1 registra 404 de roteamento, 429 e timeout **em rajada**, e cada um
custa o retry interno mais, no Estágio B, uma segunda passada inteira. Acima de
8, o tempo economizado volta como retentativa. Valor fora da faixa é cortado com
aviso, não recusado: abortar uma varredura de horas por causa de um dígito é
pior que rodá-la mais devagar.

O mesmo princípio vale para o resto do banco: uma decisão tem uma fonte só. Por
isso o veredito não ganhou uma pontuação paralela e a grade antiga saiu sem
versionamento (`db._contrair_grade_antiga`). A rastreabilidade fica no `run_id`
e no histórico do git.

## Consequências

- A rodada diária não muda de comportamento: mesma sequência, mesmas gravações,
  mesma conta.
- **Rodada que estoura no meio gasta mais do que aproveita.** Os workers vão
  adiante da thread principal, então quando a varredura cai há papers já pagos
  que nunca terão triagem. Com `concorrencia=4` e um paper travado, foram 2
  triagens gravadas contra 10 papers já em `log_llm`. Com `concorrencia=1` isso
  não acontece. Nenhuma linha se perde: o gasto desses papers fica em `log_llm`
  (e em `hfpapers custos`), mas **fora** de `log_execucao.custo_usd`, que conta
  só o que virou triagem.
- Acima de `concorrencia=1`, **Ctrl+C não devolve o terminal na hora**: espera
  as chamadas em voo (ver o ADR 003 para o prazo de cada uma). Matar o processo
  no lugar de esperar arrisca interromper uma gravação; o help do
  `--concorrencia` avisa.
- `classificacao.rodar` aceita o acumulador de quem chama: varredura que estoura
  no meio não fecha `log_execucao` com zeros depois de horas de trabalho.
