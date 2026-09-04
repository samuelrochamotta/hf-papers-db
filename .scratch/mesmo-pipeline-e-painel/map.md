# Mapa: mesmo pipeline para todo paper, e o painel que decorre disso

Label: wayfinder:map
Tracker: markdown local (`.scratch/`), ver `issues/`.

## Destination

Uma spec de implementação com toda decisão travada para dois trilhos:
**dados** — os 482 papers classificados pelo mesmo pipeline, com regras
estrito/amplo revisadas, critério de veredito estruturado (lista) e regra de
descarte obrigatória em todo `fora`; **painel** — os cinco ajustes de gráfico
pedidos em 2026-09-04 mais o gráfico "por que o pipeline aprova".
A implementação e a reclassificação em massa ficam **fora** do mapa: começam
quando ele fecha.

## Notes

- Domínio: `README.md` (pipeline, backfill, painel), `prompts/regras_classificacao.md`
  e `prompts/estagio_b.md` (as regras), `scripts/painel_app.js` (os gráficos),
  `proposta_graficos_painel.md` (a proposta que gerou o painel atual), `CONTEXT.md`
  (glossário — consultar antes de cunhar termo).
- Skills por padrão: `grilling` + `domain-modeling`. Ticket de gráfico consulta
  também `dataviz`. Ticket `prototype` de painel gera sempre com
  `scripts/gerar_painel.sh --force --destino <scratch>` — nunca publica.
- Execução não entra no mapa, com uma exceção autorizada: `task`/`prototype` que
  rode o prompt novo numa **amostra** de papers para julgar antes de travar.
  Custo não é argumento: A ≈ US$ 0,0004/paper, B ≈ US$ 0,001/paper
  (`glm-5.3-flash`); reclassificar tudo ≈ US$ 0,5.
- Env: conda `digest-hf` (`/opt/miniconda3/envs/digest-hf/bin/python`).
- Idioma de tudo (tickets, prompts, painel): português.
- Fatos de partida (2026-09-04): 482 papers, 477 triagens; 242 com veredito
  herdado do digest (`run_id='backfill'`); 6 `fora` de rodadas normais sem
  regra; 5 papers de 03/09 pendentes depois de duas rodadas.

## Decisions so far

- [O que sobra do backfill](issues/01-o-que-sobra-do-backfill.md): vira só carga de papers (lista + hidratação); veredito do digest sai da `fato_triagem` e vive só no relatório de validação.
- [Regra obrigatória em todo `fora`](issues/02-regra-obrigatoria-em-todo-fora.md): dois rótulos novos (`portabilidade_reprovada`, `fora_de_escopo`), schema rejeita `fora` sem regra, regra continua única.
- [Critério de veredito](issues/03-criterio-de-veredito.md): lista com ≥1 critério; estrito prevalece quando os lados se misturam; justificativa aplica o critério; painel mostra os critérios e ganha o gráfico "por que aprova".
- [Cores e formas dos gráficos](issues/04-cores-e-formas-dos-graficos.md): heatmap com escala por vista, matriz de bolhas (cor = taxa, tamanho = total), verde = aprovado, Pareto sem linha acumulada.
- [Como o voto amadurece](issues/05-como-o-voto-amadurece.md): vira curva única normalizada (% do voto final × idade), com o dia dos 90% marcado.
- [Por que os 5 pendentes de 03/09 atravessaram a rodada de 04/09](issues/08-por-que-os-5-pendentes-atravessaram-a-rodada.md): latência esperada, não bug — nasceram pelo refresh (estágio 4) às 07:33:11, depois de o estágio 3 fechar às 07:33:07; nunca foram selecionados, entram na próxima varredura sem escopo; o corte do `doutor` (`finalizado_em`, pós-refresh) é um falso positivo latente.
- [Enum de critérios estrito/amplo](issues/06-enum-de-criterios-estrito-amplo.md): 10 critérios (5 estrito, 5 amplo), `panorama` e `exige_acesso_interno` novos; código aberto é critério, não régua; prática corrente = o que o leitor faz hoje; fronteira só com critério do outro lado na lista.

## Not yet specified

- **A spec final de implementação** — ordem das mudanças (schema → prompts →
  reclassificação → painel), o que muda em `doutor` (regra nula passa a ser erro,
  não aviso), o que o README e o CONTEXT.md precisam dizer depois. Só se escreve
  depois que o enum de critérios e o plano da reclassificação fecharem.
- **O relatório de validação pipeline × digest** depois que o veredito do digest
  não estiver mais na `fato_triagem`: de onde lê cada lado, o que compara, se
  continua sendo gerado pelo `backfill` ou vira comando próprio.
- **A transição do painel** enquanto a reclassificação em massa roda: se os
  482 vão de uma vez, o painel fica um instante sem triagem nenhuma; se vai em
  lotes, há dias com dois vocabulários de critério. Depende do plano da
  reclassificação.

## Out of scope

- Rubrica com pontuação para estrito/amplo — descartada na cartografia
  (2026-09-04): troca um julgamento por cinco e não deixa a escolha auditável;
  o enum de critérios faz esse papel.
- Power BI: nenhuma mudança nos Parquet além das colunas novas que a
  `fato_triagem` ganhar; medidas DAX não entram.
