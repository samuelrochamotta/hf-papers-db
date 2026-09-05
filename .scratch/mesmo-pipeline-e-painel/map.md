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
- 2026-09-04: o usuário autorizou **implementar o Estágio B direto** (ticket 07
  pulado) e **pulou os protótipos de painel** (tickets 09 e 11), decidindo em
  conversa e registrando preferências nos tickets.
- Execução não entra no mapa, com uma exceção autorizada: `task`/`prototype` que
  rode o prompt novo numa **amostra** de papers para julgar antes de travar.
  Custo não é argumento: A ≈ US$ 0,0004/paper, B ≈ US$ 0,001/paper
  (`glm-5.3-flash`); reclassificar tudo ≈ US$ 0,5.
- Env: conda `digest-hf` (`/opt/miniconda3/envs/digest-hf/bin/python`).
- Idioma de tudo (tickets, prompts, painel): português.
- `proposta_graficos_painel.md` foi apagado do working tree em 2026-09-04 (não
  pelo mapa); os tickets 04/05 já carregam o que dele importava.
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
- [Enum de critérios estrito/amplo](issues/06-enum-de-criterios-estrito-amplo.md): 10 critérios (5 estrito, 5 amplo), `panorama` e `exige_acesso_interno` novos; código aberto é critério, não régua; prática corrente = o que o leitor faz hoje; fronteira fundamentada por `fronteira_contraparte` (regra ou critério do outro lado).
- [Prototipar o Estágio B com critérios](issues/07-prototipar-o-estagio-b-com-criterios.md): pulado; implementação direta com `ponte_paper_criterio`, `fronteira_contraparte`, validação real em 6 papers, só backend.
- [Plano da reclassificação total](issues/10-plano-da-reclassificacao-total.md): os 482 de uma vez via `reclassificar --tudo` (8–10 h, sequencial), registrado em `log_execucao`, taxonomia congelada, falhas do B reprocessadas por `--paper`; painel só regenera no fim, sem transição; relatório pipeline × digest, `backfill` e `seed/` morrem (revisa *O que sobra do backfill*), vocabulário ganha bootstrap exportado do banco.
- [Prototipar a curva normalizada](issues/09-prototipar-a-curva-normalizada.md): pulado; voto final = último snapshot de papers com idade ≥ 14 dias, uma faixa P25–P75 em escala linear, marca do dia em que a mediana cruza 90%, lista lateral fica.
- [Gráfico "por que o pipeline aprova"](issues/11-grafico-por-que-o-pipeline-aprova.md): pulado; barras horizontais por critério empilhadas por veredito (verdes), contagem por ocorrência com total no subtítulo, ao lado do Pareto com clique-filtro; ficha mostra critérios legíveis e a contraparte da fronteira.
- [Spec final de implementação](issues/12-spec-final-de-implementacao.md): escrita em `docs/spec-mesmo-pipeline-e-painel.md`; **destino alcançado**, mapa encerrado em 2026-09-04.

## Not yet specified

(vazio — mapa encerrado; a spec final graduou para o ticket *Spec final de implementação*;
o relatório pipeline × digest e a transição do painel fecharam no *Plano da
reclassificação total*: o primeiro morre, a segunda não existe.)

## Out of scope

- Rubrica com pontuação para estrito/amplo — descartada na cartografia
  (2026-09-04): troca um julgamento por cinco e não deixa a escolha auditável;
  o enum de critérios faz esse papel.
- Concorrência no estágio 3 (para encurtar as 8–10 h da rodada total) — ganho
  de engenharia sem decisão pendente; se quiser, é esforço próprio.
- Power BI: nenhuma mudança nos Parquet além das colunas novas que a
  `fato_triagem` ganhar; medidas DAX não entram.
