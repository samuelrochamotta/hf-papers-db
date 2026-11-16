# Redesenho do painel v2: o que é decisão e o que é acabamento

Fontes: ADR 007, `docs/specs/painel-v2.md`, o estudo de 2026-11-14
(`v3-desenho.md`, `proposta-visual.md`, `02-ux.md`) e os ajustes que Samuel pediu
na revisão do protótipo v3. O marco zero é o `main` em `e9484d9` (PR #13).

## Decisões deliberadas (só mudam com aprovação do Samuel)

| # | Decisão | Origem |
|---|---|---|
| D1 | A unidade é o **resultado ancorado**: linha "nosso" contra o melhor rival da mesma tabela, presa a um trecho literal. Não se confronta número de um paper com número de outro. | ADR 007, contexto; v3-desenho |
| D2 | **O modelo copia e escolhe; o código confere e conta.** Nenhum texto gerado na tela: o que aparece do paper é citação literal com seção. | ADR 007 §2 |
| D3 | **"Não lido" não é "não reportado"** e eixo não lido não vira zero. A incerteza aparece no gráfico, não numa nota. | ADR 007 §3 e §6 |
| D4 | **Uma codificação só nos pontos: cor = solidez.** Sem formas nem preenchimentos por entrega, abertura ou esforço. | ADR 007 §5 (ajuste do Samuel) |
| D5 | **Visual primeiro.** Sem manchete no topo, sem texto explicativo sob gráfico, sem texto final. O texto cresce conforme se desce no paper. | spec, abertura (ajuste do Samuel) |
| D6 | **Radar de seis eixos** (ganho, solidez, abertura, facilidade, amplitude, atenção), 0 a 100, como assinatura do paper e base da comparação; até 3 papers contra a mediana. | ADR 007 §6 |
| D7 | Cada gráfico responde a **uma pergunta** e traz **um número** que a responde. | v3-desenho, navegação |
| D8 | **Lente**: tocar numa categoria (arena, solidez, esforço, família) redesenha tudo; uma lente por vez. | v3-desenho; `dados.js` |
| D9 | **O catálogo de gráficos fica**: arenas, ganho contra o rival, votos × prova, escada de adoção, ganho × custo, régua e base, letra miúda. | pedido deste redesenho ("as ideias e os gráficos ficam") |
| D10 | **Três profundidades do paper**: resumo, trechos literais, ficha (tabelas, entidades, links). Qualquer ponto chega ao trecho em até dois toques. | v3-desenho |
| D11 | **Votos só ordenam e medem atenção**; nunca classificam. | v3-desenho |
| D12 | **Svelte 5 + ECharts 6**, build com nomes fixos em `relatorios/painel-v2/`; as contas vêm prontas do Python. O esquema do `dados.json` não muda neste redesenho. | ADR 007 §4 |
| D13 | Interface em **pt-BR**; estado no endereço (um link reproduz a tela). | spec |

## Acabamento (livre para refazer; vem do PR #13 ou de escolha de implementação)

- As cinco seções numeradas, a ordem delas e a grade de sete cartões.
- A barra do topo (o que mora nela), a linha de recorte e a posição da legenda.
- Tokens: Newsreader, Geist e Geist Mono, escala de tipo, grade de 4 px, raios, sombras.
- Paleta (papel quente, rampa azul da solidez, teal, laranja e magenta da comparação).
- Gaveta lateral no desktop e folha de baixo no celular; pontos de quebra.
- O botão de filtro em cada cartão, o chip da lente e como ela é desfeita.
- Ordenação do índice (votos, ganho, solidez) e a comparação inicial automática.
- Realce cruzado ao passar o ponteiro, esqueletos de carga, rodapé.
- Formato de cada gráfico **dentro** da pergunta que ele responde (por exemplo,
  haltere contra barras, enxame contra faixas), onde houver dúvida de leitura.
- Nomes dos parâmetros do endereço (os atuais continuam aceitos).

## Tensões encontradas no marco zero

1. **D5 contra os subtítulos de seção.** O PR #13 pôs uma frase explicativa em
   cada seção ("Cada forma é o radar do paper nos seis eixos; a cor indica...").
   É texto de instrução na tela inicial, que o ajuste do protótipo tinha tirado.
2. **D4 contra a comparação.** No índice, o paper em comparação ganha contorno
   teal ou laranja; no radar a cor passa a ser "qual paper", não solidez.
3. **D3 na prática.** 32% dos papers não têm solidez lida e 46% não têm ganho;
   26 de 28 leituras são parciais. O estado "não lido" é o caso comum, não a exceção.
4. **Período.** Com os dados de hoje, "14 dias" e "Tudo" mostram os mesmos 28 papers.
