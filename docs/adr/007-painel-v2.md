# ADR 007 — Painel v2: leitura do texto completo e front-end em Svelte + ECharts 6

- **Data**: 2026-11-14
- **Estado**: proposto
- **Complementa**: ADR 006 (painel público estático). O painel v1 continua
  onde está; o v2 nasce ao lado, em `relatorios/painel-v2/`.

## Contexto

O painel v1 classifica papers pelo abstract (natureza, área, vertente). O v2
quer classificar pelo que o paper prova, e isso só está no texto completo:
tabelas de resultado, contra quem compara, variância, o que liberou, o que
admite. O estudo de 2026-11-14 (protótipos B e v3) fixou o desenho: a unidade é
o **resultado ancorado** (linha de tabela "nosso" contra o melhor rival, presa
a um trecho literal), e o painel abre muito visual, com o texto aparecendo só
quando se desce num paper.

## Decisão

1. **Leitura com Claude Haiku 5.5 pelo OpenRouter** (`anthropic/claude-haiku-5.5`),
   com o mesmo `ClienteLLM` dos estágios A e B e a mesma chave. O catálogo do
   OpenRouter anuncia `structured_outputs` e `response_format` para o modelo
   (conferido em 2026-11-14), então a saída vai em `json_schema` estrito.
   A leitura tem prazo próprio (`leitura.prazo_s`, 300 s), porque o de 90 s dos
   estágios é curto para o texto inteiro. Custo estimado: ~US$ 0,006 por paper
   (40–80 mil tokens de entrada a US$ 0,10/M, 3–6 mil de saída a US$ 0,50/M).
   O teto de 320 mil caracteres mantém o prompt abaixo de 100 mil tokens, onde
   o preço quintuplica (US$ 0,50/M de entrada e 2,50/M de saída).
2. **O modelo só copia e escolhe; o código confere e conta.** Cada trecho é
   procurado no texto enviado e cada valor de tabela precisa existir como
   número nele (`_ok`). Linha não conferida não entra em gráfico. Deltas,
   solidez, esforço e os seis eixos do radar saem de
   `hfpapers.leitura.derivar`, na hora do export.
3. **Texto do HTML do arXiv** (`arxiv.org/html/<id>`, LaTeXML), sem as
   referências. Paper sem HTML cai para o abstract e fica marcado como leitura
   parcial; o painel mostra "não lido", nunca "não reportado".
4. **Front-end em Svelte 5 + Apache ECharts 6** (`painel-v2/`, Vite). Svelte
   dá transições e estado compartilhado (lente, comparação, realce cruzado)
   com pouco código; ECharts 6 traz radar, `jitter` nativo para o enxame,
   séries custom e animação de atualização. O build fica versionado em
   `relatorios/painel-v2/` com nomes fixos, então a rodada diária só regrava
   `dados.json` e não precisa de Node.
5. **Uma codificação só nos pontos: cor = solidez.** As formas e
   preenchimentos do protótipo v3 confundiam; entrega, abertura e esforço
   aparecem no tooltip e no cartão do paper.
6. **Radar de seis eixos** (ganho, solidez, abertura, facilidade, amplitude,
   atenção), de 0 a 100, com eixo nulo quando o texto lido não permite medir.
   É a assinatura do paper na faixa do topo e a base da comparação lado a lado.

## Consequências

- `leitura_texto` guarda a extração conferida por paper e versão de esquema;
  `log_llm` ganha linhas `etapa='leitura'`, com o provedor que o OpenRouter escolheu.
- `hfpapers ler` roda à parte do `run` diário até haver medição contra um
  conjunto-ouro; depois pode entrar no `run_daily.sh`.
- Os cortes de solidez e esforço são heurísticas do estudo, não calibradas.
- O Pages passa a publicar `relatorios/painel-v2/` em `/v2/`.
