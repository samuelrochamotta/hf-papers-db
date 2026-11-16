# Marco zero do painel v2 (main em e9484d9, PR #13)

Tudo aqui foi medido no build publicado, com as ferramentas de `painel-v2/medir/`.
As mesmas medidas rodam a cada rodada do redesenho; "pronto" é comparado com esta página.

## Resumo

| Medida | Marco zero |
|---|---|
| Tarefas simuladas, desktop 1280 px (19 tarefas) | 18 certas · 84 passos · 209 s estimados · primeiro clique certo em 17 |
| Tarefas simuladas, celular 360 px (8 tarefas de prioridade A) | 6 certas · 54 passos · 121 s estimados · primeiro clique certo em 5 |
| axe-core (12 estados: 2 larguras × 2 temas × 3 telas) | 122 nós em violação, 4 regras |
| Contraste de texto | mínimo de 3,36:1 (rótulos em `--faint`) |
| Teclado | 10 de 10 percursos completos, 472 teclas; 95 paradas de Tab na página |
| Casos extremos | sem rolagem horizontal; 3 quebras visuais (abaixo) |
| Daltonismo | 1 par de cores abaixo de ΔE 10; 2 cores de dado abaixo de 3:1 contra o fundo |
| Capturas | 24 (360, 768, 1280 e 1600 px; claro e escuro; base, lente e paper aberto) |

## Tarefas simuladas

Cinco subagentes receberam só o enunciado e capturas de tela; cada ação
(clicar, rolar, passar o ponteiro, tecla) devolve uma nova captura. O tempo é
uma estimativa pelo modelo KLM (decidir 1,35 s, apontar 1,1 s, clicar 0,2 s,
rolar 0,6 s), a mesma régua para o antes e o depois.

| Tarefa | Prio | Tela | Certa | Passos | Tempo (s) | 1º clique certo | O que foi respondido |
|---|---|---|---|---|---|---|---|
| T1 Você só tem tempo para três papers da última semana de col… | A | 360 | sim | 3 | 7,3 | sim | Confucius4-R2T2 (93 votos, firme), Few-Step Streaming... (88, forte) e P2-MOPD (70, firme)… |
| T3 Sem sair do painel: de que problema trata o paper Sage-Tai… | A | 360 | sim | 8 | 18,4 | **não** | Tipo de entrega: Sistema (arquitetura metacognitiva, Agentes e harness). Problema: a tela … |
| T5 O paper mais votado do período tem prova sólida?… | A | 360 | sim | 1 | 2,7 | sim | Nao se sabe: o paper mais votado (Advances in Agentic Computer Graphics, 150 votos, period… |
| T6 Quais papers têm muitos votos (acima da mediana do período… | A | 360 | sim | 7 | 15 | **não** | Mediana de votos dos 28 papers lidos (2 a 13 nov.) = 70. Acima dela com prova fragil ou ba… |
| T11 Quais papers dá para adotar sem treinar nada (basta config… | A | 360 | **não** | 16 | 34 | sim | Parcial: 9 papers dispensam treino (todos na faixa Integrar; Configurar vazio). Entre eles… |
| T12 Para adotar o Confucius4-R2T2: qual é o esforço estimado, … | A | 360 | **não** | 5 | 11,9 | sim | Esforço: Integrar (2 de 5 segmentos, ou seja, baixo). Hardware: não reportado. Código: mar… |
| T15 Entre os papers SLA e Harness-S: qual tem a prova mais sól… | A | 360 | sim | 11 | 24,8 | **não** | Prova mais sólida: SLA (solidez forte, vence o rival em 5 de 5, 5 de 6 sinais de prova), c… |
| T20 Restrinja o painel aos papers de Robótica e diga quantos s… | A | 360 | sim | 3 | 7,3 | sim | São 7 papers de Robótica (de 28). Filtro removido; o painel voltou a mostrar os 28 papers.… |
| T1 Você só tem tempo para três papers da última semana de col… | A | 1280 | sim | 2 | 5,3 | sim | Confucius4-R2T2 (93 votos, firme), Few-Step Streaming... (88, forte) e P2-MOPD (70, firme)… |
| T2 Que paper entrou no dia mais recente de coleta?… | B | 1280 | sim | 13 | 30,9 | sim | SO-Arena Benchmarking the Capability Spectrum and Reliability of System One Models (13 de … |
| T3 Sem sair do painel: de que problema trata o paper Sage-Tai… | A | 1280 | sim | 5 | 12,4 | sim | Entrega: Sistema (tema Agentes e harness). Problema: a tela nao o declara de forma explici… |
| T4 Quantos papers do período não tiveram leitura suficiente p… | C | 1280 | sim | 0 | 0 | sim | Periodo completo (28 papers, 2 a 13 nov.): 9 papers com leitura insuficiente para avaliar … |
| T5 O paper mais votado do período tem prova sólida?… | A | 1280 | sim | 1 | 2,7 | sim | Nao se sabe / nao: o mais votado do periodo completo (2 a 13 nov.) e Advances in Agentic C… |
| T6 Quais papers têm muitos votos (acima da mediana do período… | A | 1280 | sim | 3 | 6,9 | sim | 3 papers (periodo completo): CoworkOS (100 votos, frágil), SO-Arena Benchmarking (83 votos… |
| T7 O paper CoworkOS aparece com prova frágil. Quais sinais de… | B | 1280 | sim | 6 | 15,2 | **não** | Em 'Sinais de prova' (1 de 3 lidos... só 'Compara com rival externo' é cumprido). Marcados… |
| T8 A alegação de destaque (manchete) do paper Route Anything … | B | 1280 | sim | 5 | 12,6 | sim | Não confirmada: o painel marca 'Manchete confere' com X. A manchete diz que o oráculo por … |
| T9 Cite, nas palavras dos autores, um limite que o paper Wave… | B | 1280 | sim | 2 | 5,3 | sim | "VBench-based scores do not fully characterize long-stream quality" (§7 Limitations, trech… |
| T10 No paper Don't Just Trust Your Memory, qual foi o resultad… | B | 1280 | sim | 3 | 8 | sim | ALFWorld Seen (Tabela 1, Acc): o método (WikiTrace) fez 98,7±0,5; o melhor rival foi o AWM… |
| T11 Quais papers dá para adotar sem treinar nada (basta config… | A | 1280 | sim | 19 | 46,1 | sim | Pelo filtro Esforço: Integrar (Adoção; o painel diz 9 papers dispensam treino, nenhum em C… |
| T12 Para adotar o Confucius4-R2T2: qual é o esforço estimado, … | A | 1280 | **não** | 6 | 14,8 | sim | Esforço estimado: Integrar (2 de 5 segmentos da barra). Hardware: Não reportado. Código: l… |
| T13 Quais papers ficam mais baratos de rodar sem perder qualid… | B | 1280 | sim | 2 | 5,3 | **não** | MoviEdit e Think Less, Locally (os 2 papers no quadrante 'mais barato e melhor': custo rel… |
| T14 Sobre qual família de modelos-base o maior número de paper… | C | 1280 | sim | 1 | 2,7 | sim | Qwen (7 papers partem dele)… |
| T15 Entre os papers SLA e Harness-S: qual tem a prova mais sól… | A | 1280 | sim | 5 | 12,9 | sim | Prova mais sólida: SLA (solidez 83 contra 67 do Harness-S). Mais fácil de adotar: Harness-… |
| T16 O paper Harness-S está acima ou abaixo da mediana do perío… | B | 1280 | sim | 3 | 7,8 | sim | Abaixo nos dois: ganho 14 contra mediana 66 e solidez 67 contra mediana 75 (escores de 0 a… |
| T17 Em que área de disputa (arena) há mais papers competindo, … | B | 1280 | sim | 2 | 5,3 | sim | Robótica (7 papers); dentro dela, o maior ganho contra o rival é do DreamX (+66,2% mediano… |
| T18 Qual é o ganho típico (mediano) dos papers contra o melhor… | C | 1280 | sim | 2 | 5,1 | sim | Ganho mediano +3,4% (12 de 15 vencem o rival). O de maior ganho é o DreamX (+66,2%) e sim,… |
| T20 Restrinja o painel aos papers de Robótica e diga quantos s… | A | 1280 | sim | 4 | 9,9 | sim | 7 papers de Robótica (cabeçalho mostrou '7 de 28 papers' com o chip 'Arena: Robótica'). De… |

O que os usuários simulados relataram (sem a minha interpretação):

- **T2** (o que entrou no último dia): 13 passos. "A data só aparece dentro do painel de cada paper"; não há ordem nem visão por data.
- **T3** (do que trata o paper): o tipo de entrega aparece; **o problema não está em lugar nenhum** da tela, embora exista nos dados (`prob`).
- **T6** no celular: "foi preciso rolar a grade inteira, anotando 28 números de votos de cabeça"; a mediana de votos não aparece.
- **T11** (adotável, liberado e com prova): 19 passos no desktop e falha no celular. "Os filtros não se combinam"; "a Adoção mostra só pontinhos sem nome"; foi preciso abrir paper por paper.
- **T12**: falha nas duas telas. O painel diz "código liberado", mas não mostra o endereço.
- **T15**: "não achei como comparar dois papers"; o `+` só aparece ao passar o ponteiro, e o terceiro paper entra sem aviso.
- **T17 e T18**: o eixo do gráfico de ganho termina em +40%, mas a dica mostra +66,2%; a primeira leitura foi "cerca de +40%".
- **T20**: "o filtro fica escondido atrás de um ícone pequeno e só aparece na seção Resultados".
- Contadores que se contradizem: "28 papers lidos" ao lado de "Ver os 30 papers".
- "Não lido" nomeia duas coisas diferentes (fila sem leitura e leitura insuficiente).
- Forte e firme "só pela cor do radar, azul-escuro contra azul" geraram dúvida em três sessões.

## Acessibilidade (axe-core 4.10)

| Regra | Impacto | Estados | Exemplo |
|---|---|---|---|
| `color-contrast` | serious | 10 de 12 | Element has insufficient color contrast of 3.36 (foreground color: #80868f, background color: #f6f5f1, font si |
| `page-has-heading-one` | moderate | 8 de 12 | Page must have a level-one heading |
| `target-size` | serious | 8 de 12 | Target has insufficient size (22px by 22px, should be at least 24px by 24px) |
| `heading-order` | moderate | 4 de 12 | Heading order invalid |

Total: 122 nós. Os gráficos são `canvas`: o axe não vê o texto de dentro deles, então a paleta dos gráficos é conferida à parte.

## Teclado

Varredura com Tab: 95 paradas em 1280 px e 51 em 360 px; todas com nome e anel de foco; 1 parada fica atrás da barra fixa.

| Percurso | Completo | Teclas |
|---|---|---|
| K1 abrir o mais votado e voltar | sim | 22 |
| K2 abrir um paper e ler os trechos | sim | 34 |
| K3 filtrar por Robótica | sim | 86 |
| K4 limpar o filtro | sim | 13 |
| K5 comparar dois papers | sim | 47 |
| K6 ver só a última semana | sim | 9 |
| K7 abrir a ficha com tabelas e links | sim | 35 |
| K8 filtrar o que dá para integrar | sim | 96 |
| K9 achar os frágeis e abrir um | sim | 118 |
| K10 trocar o tema | sim | 12 |

Tudo é alcançável, mas caro: filtrar por arena custa 86 teclas e chegar a um paper frágil, 118, porque cada paper ocupa duas paradas de Tab e os filtros moram no fim da página.

## Casos extremos

Nove conjuntos derivados do `dados.json` real (`painel-v2/casos/`), em 360 e 1280 px, com o paper aberto.
A checagem automática não achou rolagem horizontal nem erro de console. A leitura das capturas achou:

1. **Palavra inquebrável no título** vaza da folha do paper em 360 px e é cortada sem reticências no índice.
2. **240 papers**: a página passa de 9 mil px e o índice vira um muro de miniaturas antes de qualquer gráfico.
3. **Números extremos**: o eixo de ganho fica preso em ±40% e empilha os pontos na borda; com 1 a 50 mil votos, o enxame vira uma linha.

## Daltonismo

Menor diferença de cor (CIEDE2000) entre duas categorias da mesma paleta, simulando protanopia, deuteranopia e tritanopia:
solidez 15,9 (claro) e 10,6 (escuro); resultado 14,2 e 13,4; comparação 11,2 (claro) e **7,6 (escuro, teal × magenta na deuteranopia)**.
Contra a superfície, "frágil" tem 1,42:1 e "sem rival" 1,45:1 (o mínimo para objeto gráfico é 3:1).

## Avaliação heurística

Gravidade: 3 atrapalha a tarefa, 2 custa tempo, 1 é acabamento.

### Nielsen

| # | Heurística | Achado | Grav. |
|---|---|---|---|
| 1 | Visibilidade do estado | A lente é aplicada no meio da página e o aviso fica no topo, fora da vista. "28 papers" e "Ver os 30" convivem. "14 dias" e "Tudo" dão o mesmo resultado sem dizer. | 2 |
| 2 | Linguagem do usuário | "Não lido" serve para a fila e para a leitura insuficiente. Ícones X e traço nos sinais de prova não têm chave. | 2 |
| 3 | Controle e liberdade | O quarto paper da comparação expulsa o primeiro em silêncio. | 2 |
| 4 | Consistência | Azul é solidez, é "vence o rival" e é o destaque da interface. No índice, o contorno teal ou laranja da comparação disputa com a cor da solidez (D4). "Prova" é seção e "Sinais de prova" mora dentro do paper. | 3 |
| 6 | Reconhecer em vez de lembrar | Data, problema e endereço do código só existem dentro do paper ou nem aparecem. Para cruzar esforço, abertura e prova é preciso abrir paper por paper. | 3 |
| 7 | Eficiência | Sem busca, sem ordem por data ou facilidade, uma lente por vez, `+` de comparar só no hover. | 3 |
| 8 | Minimalismo | Cinco frases de instrução, numeração 01 a 05 e sete números de 44 px competem com os dados. | 2 |
| 10 | Ajuda | Nenhuma chave para os seis eixos do radar na miniatura. | 1 |

### Tufte

| Achado | Grav. |
|---|---|
| O gráfico de ganho corta o eixo em +40% sem marcar o corte: DreamX (+66%) parece +40%. | 3 |
| O enxame de votos × prova não nomeia nenhum ponto; a resposta ("quais papers?") exige passar o ponteiro em cada um. | 3 |
| 28 miniaturas de radar ocupam a primeira tela e entregam pouco: a forma não se lê em 44 px e o único número é o de votos. | 2 |
| "Onde está a disputa?" usa duas unidades: o rótulo conta papers e a barra conta resultados. | 2 |
| Cada gráfico vem numa caixa com borda, sombra e raio de 18 px: tinta que não é dado. | 1 |

### Gestalt

| Princípio | Achado | Grav. |
|---|---|---|
| Proximidade | O controle que filtra (ícone no canto do cartão) fica longe do que mostra o filtro (chip no topo) e do que é filtrado (índice). | 2 |
| Semelhança | Paper aberto, paper em comparação e paper sob o ponteiro usam contornos parecidos. | 2 |
| Região comum | "A letra miúda" fica fora de cartão enquanto os vizinhos ficam dentro; a comparação é a única seção de um cartão só. | 1 |
| Continuidade | A grade de sete cartões tem três alturas e três larguras; o olho não acha uma ordem de leitura. | 2 |
