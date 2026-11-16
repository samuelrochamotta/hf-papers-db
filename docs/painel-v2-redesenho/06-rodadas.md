# Rodadas de crítica independente

Cada rodada segue o mesmo roteiro: refazer a matriz de capturas, rodar axe,
contraste, daltonismo, teclado e casos extremos, pedir a crítica a quem não
recebeu nenhuma justificativa, corrigir tudo o que for de prioridade alta e
repetir.

## Como a crítica é pedida

- **Material**: só capturas de tela, uma janela do navegador por arquivo, na
  posição em que a pessoa veria (360, 768, 1280 e 1600 px; claro e escuro;
  lista, filtro, busca, paper nas três profundidades, panorama, panorama com
  filtro, comparação cheia e vazia). Nenhum código, nenhum documento deste
  redesenho.
- **Briefing**: para quem é o painel e as perguntas que ele precisa responder
  (as mesmas de `02-tarefas.md`, sem a resposta). Nada sobre por que as coisas
  são como são.
- **Quatro críticos**, cada um com uma lente: acabamento visual, gráficos,
  celular e tablet, uso e texto. Cada um entrega achados com prioridade, a
  tela em que viu, por que importa e uma nota de 0 a 10 para "parece obra de
  um time de design muito experiente?".
- **Prioridade alta** é o que faz a pessoa errar a resposta, perder o lugar ou
  ler um dado que a tela desmente.

## Rodada 1 (2026-11-16)

128 capturas do protótipo no commit `9eaccc7`.

| Lente | Nota | Achados | De prioridade alta |
|---|---|---|---|
| Acabamento visual | 7 | 16 | 3 |
| Gráficos | 6 | 16 | 5 |
| Celular e tablet | 6 | 18 | 4 |
| Uso e texto | 6,5 | 25 | 5 |

Os 17 achados de prioridade alta são 12 depois de juntar os repetidos.

| # | Achado | Quem viu | O que foi feito |
|---|---|---|---|
| 1 | O cabeçalho preso era translúcido: o que rolava por baixo aparecia atrás do recorte | visual, celular, uso | Fundo opaco na barra e na linha do recorte |
| 2 | A busca não entrava no recorte: o topo seguia em "28 papers" e não havia como limpar | celular, uso | A busca é parte do recorte: conta "N de 28", vira chip, sai no mesmo Limpar; o termo aparece marcado e, quando casou fora do título, a linha diz onde |
| 3 | No celular, com filtro ligado, a linha da contagem ficava cortada ao meio sob a barra | celular | Primeira linha de altura fixa: sem filtro sobe com a página, com filtro fica presa inteira |
| 4 | Na lista de 360 px o mesmo fato mudava de lugar de um paper para outro | celular | Fatos em colunas fixas (votos, prova, ganho; adoção, abertura), cada um com o nome ao lado |
| 5 | Títulos cortados numa linha; em 1600 px com o paper aberto sobravam 27 caracteres | visual | Título em até duas linhas em todas as larguras |
| 6 | Quadro de custo: uma das duas respostas sem nome, rótulos colidindo, eixo ilegível | visual, gráficos | Rótulos colocados por busca de lugar livre, com lugar garantido para as respostas; as respostas também por nome embaixo do gráfico; eixo em ÷64, ÷16, ÷4, igual, ×4 |
| 7 | Quadro de ganho: o ponto fora da escala (+66,2%) era desenhado dentro dela | gráficos | O ponto fica na borda com a marca de corte do lado de fora; o eixo estica um passo quando o valor está quase na borda |
| 8 | Quadro de ganho em 360 px: 50 px de área de desenho | gráficos, celular | No celular o nome sobe para cima da régua e a régua usa a largura toda |
| 9 | Comparação: 5 e 9 benchmarks com a mesma barra e os dois em negrito; perda desenhada como ganho | visual, gráficos, celular, uso | Barra e negrito seguem o valor real; amplitude vai até o paper com mais benchmarks do período; ganho sai do zero para os dois lados; abertura mostra os quatro artefatos, um a um |
| 10 | "O que dá para adotar já?": o número grande contava outra coisa | gráficos | O número é a resposta: papers que dispensam treino, têm algo liberado e prova firme ou forte (4 de 9), com os nomes |
| 11 | "5 de 7 sinais lidos" contradizia a lista logo abaixo | uso | "cumpre 5 de 7 sinais"; quando há sinal não lido, o texto diz quantos |
| 12 | Estado de leitura com três nomes e conta que não fechava; o resumo não seguia o recorte | uso, gráficos, visual | Um vocabulário (inteira, parcial, prova não lida, na fila), partes que somam o recorte, e "leitura parcial" na primeira linha do paper |

### Regressões que as medidas pegaram durante as correções

- axe: o termo da busca marcado na linha cinza ficou com contraste de 4,22:1
  (3,99 no escuro). Passou a usar a tinta cheia.
- Teclado: o percurso "limpar o filtro" quebrou quando o nome acessível do
  botão mudou. O nome voltou a começar por "Limpar o filtro".
- Casos extremos: 4 de 54 com vazamento em 360 px ("ganho −12,6%" e "50000
  votos" saindo da coluna). As colunas foram refeitas a partir das larguras
  medidas.

### Achados médios tratados antes da rodada 2

| Achado | O que foi feito |
|---|---|
| Os quatro níveis de prova são quatro azuis parecidos (três críticos) | Experimento E4 em `05-experimentos.md`: a marca passa a encher conforme a prova |
| Abas e título somem ao rolar a ficha | As abas ficam presas no topo do paper e, quando o título sai da tela, a faixa mostra o título em uma linha |
| Na ficha, os números não alinham pela vírgula | Cada tabela usa o mesmo número de casas; o desvio tem coluna própria |
| "De onde veio este número?" exigia achar a tabela na mão | Cada resultado do Resumo leva à tabela dele na Ficha |
| Ganho em % sem dizer que é relativo; quadrados dos resultados sem legenda | "ganho relativo" no cabeçalho dos resultados e chave dos quadrados no próprio paper |
| Alvos de toque desenhados abaixo de 44 px | Medição nova (`medir/alvos.mjs`): 32 de 176 controles respondiam em menos de 44 px; agora nenhum. O desenho continua com 40 e 36 px, a área que responde ao dedo passa do desenho |
| Em 768 px o paper era o celular esticado | A coluna de leitura para em 640 px e fica no centro da folha |
| "Onde está a disputa?" não dizia quem vence | Embaixo do gráfico, os papers que mais vencem na arena em foco (a do filtro ou a mais cheia), com "5 de 5" |
| "Manchete não confere · alega 7" | O número leva a unidade do paper e a frase diz o que a conferência fez: "5,4 pontos não está nas tabelas lidas" |
| O número grande do ganho não tinha marca no gráfico | Linha pontilhada "mediana +3,4%" |
| Radar da comparação pequeno, com vão em cima e embaixo no celular; mediana pesada | O radar usa a largura que tem e a altura acompanha; a mediana virou contorno tracejado, como no radar do paper |
| Dois "Limpar", "+ Trocar paper", "3 de 3" | "Esvaziar", "Trocar o paper A" com ícone de troca, "3 de 3 papers" |
| Com o paper aberto, a lista não mostrava a linha dele | A lista rola até a linha aberta |
| "Não reportado" ao lado de "não lido"; "arXiv" e o número em linhas separadas; ponto solto no fim da frase | Mesma caixa nos valores ausentes; fatos e links do paper quebram em grupos; a frase da letra miúda não usa mais ponto como separador |

### O que ficou para o Samuel ou para depois

- **Dependem das escolhas dele**: números em fonte monoespaçada (identidade e
  tipografia), "Panorama" como nome de vista e de tipo de paper e os rótulos
  "Amplitude", "Ficha" e "Entidades" (vocabulário), a aba Resumo sem frase em
  português (D2, decisão 8), a marca de prova (D4, decisão 10), a escala da
  amplitude no radar (decisão 11) e a miniatura do radar na lista (decisão 12).
- **Baixa prioridade, não mexido**: a chave de prova repetida nos quadros do
  Panorama; a ordem dos eixos igual no radar e na tabela da comparação.

### Medidas depois das correções

| Medida | Marco zero | Depois da rodada 1 |
|---|---|---|
| axe, nós em violação | 122 | 0, em 40 estados (360 e 1280 px, claro e escuro) |
| Dez percursos só com teclado | 472 teclas | 10 de 10, 180 teclas |
| Contraste | texto mínimo de 3,36:1 | 76 pares de tokens, 0 abaixo do mínimo; pior texto 5,35:1 |
| Daltonismo | 1 par de cores abaixo de ΔE 10; 2 cores de dado abaixo de 3:1 contra o fundo | menor ΔE2000 de 10 ou mais nas 24 combinações de tema, visão e paleta |
| Casos extremos, 54 combinações | 3 quebras visuais | 0 |
| Alvos de toque em 360 px, 176 controles | não medido | 0 abaixo de 44 px |
| Testes | não havia do painel | 20 do painel; 417 na suíte do repositório |

O teste de casos extremos passou a medir o conteúdo de cada caixa por um
`Range`: a área de toque estendida passa do desenho de propósito e não é texto
vazando.

## Rodada 2 (2026-11-16)

129 capturas do protótipo no commit `435fa49`, com quatro críticos novos.

| Lente | Nota | Achados | De prioridade alta |
|---|---|---|---|
| Acabamento visual | 7 (antes 7) | 21 | 1 |
| Gráficos | 7,5 (antes 6) | 14 | 1 |
| Celular e tablet | 7 (antes 6) | 15 | 2 |
| Uso e texto | 7 (antes 6,5) | 23 | 2 |

Os 6 achados de prioridade alta são 3 depois de juntar os repetidos (na
rodada 1 eram 12).

| # | Achado | Quem viu | O que foi feito |
|---|---|---|---|
| 1 | O radar satura e desmente a tabela ao lado: 5 e 9 benchmarks no mesmo vértice de Amplitude; Abertura no anel de fora com só o código lido; nenhum anel diz quanto vale; "Abertura 100" e "Amplitude 100" sem unidade no paper | visual, gráficos, celular, uso | Sem mexer na conta do Python (D12). O desenho passa a dizer o que a nota esconde: marca de corte "»" fora do anel em quem passa de 5 benchmarks, vértice vazado onde a abertura só conta parte dos artefatos, "50" e "100" escritos nos anéis. No radar do paper, cada eixo mostra o fato com a unidade ("9 bench.", "código", "+10,2%") no lugar da nota solta. Na tabela, "código · 3 não lidos" e os segmentos não lidos tracejados. As duas contas viram as decisões 11 e 13 |
| 2 | Os dois papers da fila (105 e 102 votos) só apareciam depois da 28ª linha; o topo não avisava e a busca não os achava | celular, uso | A fila entra na lista, na posição do voto ou da data, com "Na fila, ainda sem leitura" e link para o arXiv; o topo conta "28 papers · mais 2 na fila"; a busca acha pelo título e pelo id |
| 3 | O traço "–" queria dizer "não lido", "sem rival" e "não há" ao mesmo tempo | uso, celular, visual | Nenhuma tela põe traço no lugar de um fato: "ganho não lido", "sem rival", "Só informa", "não lida", iguais na lista, no celular, no paper e na comparação |

### Achados médios tratados antes da rodada 3

| Achado | O que foi feito |
|---|---|
| "Onde está a disputa?": a manchete conta papers e a barra conta resultados | O fim de cada barra diz o placar ("13 de 27 vencem") |
| "12 de 15 vencem o rival" contava como vitória ganhos colados no zero | "12 de 15 acima de zero": a frase diz o que o desenho mostra |
| "O que dá para adotar já?": o 4 de 9 não aparecia no desenho; os nomes escondiam quem perde do rival | Faixa "dispensam treino" nos dois degraus que contam, traço embaixo dos papers da resposta e o ganho ao lado de cada nome |
| "Onde há votos sem prova?" ignorava os não lidos mais votados; "mediana 70" sem dizer de quê | "3 papers… mais 5 com prova não lida"; "mediana do período 70"; o mais votado ganha o nome inteiro |
| O mesmo paper com cortes diferentes em cada componente | Um nome curto único (o título até os dois-pontos, até 28 letras) em gráficos, nomes, legenda e comparação; só onde ele não cabe o desenho usa o menor |
| Gráfico de custo: um ponto sem nome e "Think Less…" ao lado do ponto de outro paper | Com até 6 pontos todos têm nome; o nome encosta no próprio ponto (posições em diagonal) e há margem para os nomes do lado direito |
| "construído sobre" e "medido contra" fora do eixo das barras | O eixo central é desenhado e os dois títulos ficam presos a ele, um de cada lado |
| Quadros com buraco branco; número e frase em arranjos diferentes na mesma fileira | A letra miúda mostra 4 trechos, o gráfico de modelos até 12 famílias; em quadro estreito o número fica sozinho na linha em todos; o seletor Modelos/Benchmarks desce para junto do gráfico |
| "Manchete não confere" afirmava mais do que a leitura sustenta | "Manchete fora das tabelas lidas · 5,4 pontos"; no paper, "número fora das tabelas lidas" |
| Ganho e Adoção coladas na tabela | 12 px a mais de calha, tirados da coluna Abertura |
| Ganho negativo só tinha cor no Panorama | A mesma cor de alerta na lista, no paper e na comparação |
| A linha "Esforço" mostrava mais barrinhas quanto menor o esforço | A linha se chama "Facilidade" |
| Bloco Ganho, Prova, Adoção do paper: microtexto apertado e "recorte" órfão | "acima da mediana", régua na largura da coluna, o detalhe do melhor resultado fica só em Resultados |
| Ficha: tabelas sem cabeçalho, "±" sem nome, rival não marcado; "98 de ExpeL" e "98,0" | Cabeçalho (Sistema, Papel, Valor, ± do paper), a linha do rival usado na conta diz "melhor rival"; os dois números de um resultado saem com as mesmas casas |
| Comparar: a barra de Votos era o percentil; dois "Firme" com barras diferentes; "A × B × C ×" no celular | A barra de Votos é proporcional ao número; a Prova escreve "5 de 7 sinais"; no celular cada coluna é uma caixa com a letra, o nome e o botão de tirar |
| Desfazer um filtro só pedia abrir o menu | Cada filtro ligado tem um "×" ao lado, como a busca |
| Em 1600 px com o paper aberto a lista usava o arranjo estreito | Entre 980 e 1120 px de lista entra uma tabela sem as colunas de data e amplitude |
| O seletor de período mudava de nome | No celular e com o paper aberto ele mostra o mesmo nome e a mesma contagem ("Tudo 28") |
| No escuro, o segmento ativo afundava | O ativo fica mais claro que o trilho |
| Rodapé no meio da janela em páginas curtas | O rodapé assenta no pé da janela |

### O que ficou para o Samuel ou para depois

- **Dependem das escolhas dele**: a escala da amplitude no radar (decisão 11) e
  a conta da abertura no radar (decisão 13, nova); a miniatura do radar na
  lista (decisão 12; por ora o estado sem leitura virou um hexágono tracejado
  limpo); números em fonte monoespaçada (decisão 2); "Panorama" como nome de
  vista e de tipo, "Amplitude", "Abertura", "Forte" e "Firme" (decisão 4); a
  aba Resumo sem frase em português (decisão 8); atalhos de um toque ("vale
  ler", "dá para adotar já"), filtro de abertura e índice no topo do Panorama
  (entram ou não, decisões 5 e 6).
- **Não mexido**: a ficha repete o mesmo benchmark em tabelas diferentes sem
  dizer a condição (a leitura não extrai a condição); o chip da busca repete o
  campo no celular; "Trocar o paper A".

### Regressões que as medidas pegaram durante as correções

- **Dois alvos de toque abaixo de 44 px**. Com o "×" ao lado de cada filtro
  ligado, os filtros passaram a quebrar em duas linhas no celular, a 6 px uma
  da outra ("Arena: Robótica" ficou com 80 × 42 px). E a caixa de cada coluna
  da comparação deixava a área de toque do "×" cobrir os 8 px de cima do nome
  ("A: SLA" com 54 × 38 px). Corrigido com 8 px entre as linhas dos filtros,
  sem a seta no chip ligado, e com a distância de volta entre o nome e o "×".
- **Teclado**: a tabela reduzida escondia colunas que a navegação do cabeçalho
  tentava focar. A navegação pula o que não está na tela.

### Medidas depois das correções

| Medida | Marco zero | Depois da rodada 1 | Depois da rodada 2 |
|---|---|---|---|
| axe, nós em violação | 122 | 0, em 40 estados | 0, em 40 estados |
| Dez percursos só com teclado | 472 teclas | 10 de 10, 180 teclas | 10 de 10, 188 teclas |
| Contraste | texto mínimo de 3,36:1 | 76 pares, 0 abaixo do mínimo; pior texto 5,35:1 | igual |
| Daltonismo | 1 par abaixo de ΔE 10 | 0 nas 24 combinações | 0 nas 24 combinações |
| Casos extremos, 54 combinações | 3 quebras visuais | 0 | 0 |
| Alvos de toque em 360 px, 176 controles | não medido | 0 abaixo de 44 px | 0 abaixo de 44 px |
| Testes | não havia do painel | 20 do painel; 417 na suíte | 25 do painel; 417 na suíte |

As 8 teclas a mais têm duas origens. Seis vêm dos dois papers da fila, que
agora são linhas da lista: descer com a seta até o Confucius4-R2T2, o SLA ou o
MoviEdit passa por duas linhas a mais (K2, K5 e K7, duas teclas cada). Duas vêm
do "×" ao lado do filtro ligado, que é uma parada de Tab nova (K4 e K9, uma
tecla cada). Em troca, a varredura com Tab perdeu as duas paradas da antiga
lista da fila, no fim da página.

## Rodada 3 (2026-11-16)

134 capturas do protótipo no commit `03b9bb8`, com quatro críticos novos.
As telas de 768 px foram capturadas sem toque, e por isso mostram os
controles na densidade de mouse; no tablet de verdade eles crescem com
`pointer: coarse`. A rodada 4 captura 768 px com toque.

| Lente | Nota | Achados | De prioridade alta |
|---|---|---|---|
| Acabamento visual | 7,5 (antes 7) | 16 | 1 |
| Gráficos | 7 (antes 7,5) | 15 | 1 |
| Celular e tablet | 7 (antes 7) | 18 | 1 |
| Uso e texto | 7 (antes 7) | 20 | 2 |

Cinco achados de prioridade alta, nenhum repetido entre os críticos.

| # | Achado | Quem viu | O que foi feito |
|---|---|---|---|
| 1 | A abertura do mesmo paper mudava de palavras e de valor entre telas: "nada" na lista, "nada liberado" no celular, "só a página · 3 não lidos" em Comparar. A lista nunca mostrava a parte não lida | uso; gráficos e celular como médio | Uma função só escreve a abertura em toda tela ("código", "código e pesos", "só a página", "nada liberado") e outra diz quanto ficou sem ler ("3 não lidos"). A lista, o celular, o paper e a comparação usam as duas. Coberto por teste |
| 2 | "Mediana" apontava para bases diferentes: a do recorte na lista, no radar e em Comparar; a do período no Panorama; nenhuma nos indicadores do paper | uso | A mediana é sempre a do período escolhido, com ou sem filtro, e sempre escrita "mediana do período": divisor da lista, indicadores e radar do paper, Comparar e Panorama |
| 3 | No celular, com busca, a contagem passava por baixo de "Limpar" | celular | A contagem mostra o que cabe ao lado do botão, por ordem de importância; os filtros ficam numa linha só, que rola de lado com os ligados na frente |
| 4 | Gráfico de custo: nomes fora do quadro e cortados pela grade, dois nomes em negrito empilhados, cada rótulo de um lado | visual; gráficos como médio | Eixo simétrico em potências de 2 que usa a largura do cartão; os nomes ficam dentro do quadro, com fundo sobre a grade e ar mínimo entre eles |
| 5 | O radar usa uma escala que ninguém explica e que contradiz a tabela: 5 e 9 benchmarks no mesmo vértice, abertura na borda com 3 de 4 itens não lidos | gráficos; uso, celular e visual como médio | **Não fecha no desenho.** É a terceira rodada em que a marca de corte e o vértice vazado são lidos como máximo. O que deu para fazer sem mexer na conta (D12): tabela antes do radar, polígonos sem preenchimento, "anéis em 50 e 100, a nota de cada eixo" na legenda, marcas dos anéis com fundo. O resto depende das decisões 11 e 13 |

### Achados médios tratados antes da rodada 4

| Achado | O que foi feito |
|---|---|
| Buracos de 70 a 110 px dentro dos cartões do Panorama | O gráfico cresce até 1,4 vez a altura mínima para ocupar o cartão esticado pela fileira; o quadro sem dado encolhe em vez de esticar |
| "Onde está a disputa?": "13 de 27" incluía resultados sem rival e ficava colado na ponta da barra | Coluna própria "vencem", alinhada à direita, com o denominador só de quem tem rival ("13 de 24"); coluna "papers" em negrito; frase própria para empate e para recorte sem disputa |
| Coluna de valores do gráfico de ganhos alinhada à esquerda; no celular a grade riscava nomes e valores | Valores alinhados à direita; no celular, nome e valor têm fundo sobre a grade |
| "Onde há votos sem prova?": rótulo solto do mais votado; em 360 px a faixa perdia o título e os pontos embolavam | O paper mais votado ganha anel e o nome encostado no ponto; o título da faixa procura um canto livre e, se não há, desce para junto dos nomes; pontos de mesmo voto empilham |
| "Dá para adotar já" listava quem perde do rival sem sinal; ganho negativo sem cor nos nomes | O ganho aparece ao lado de cada nome, em cor de alerta quando negativo |
| Nomes cortados de formas diferentes ("SO-Arena Benchmarking the…") | O nome curto não termina em palavra de ligação |
| Número grande e frase em arranjos diferentes | O número fica sempre sozinho na linha, com a frase embaixo |
| Tema escuro: seleção fraca, prova frágil quase sumida, A, B e C em outra família de cor | Segmento ativo mais claro e com borda, os inativos mais apagados; frágil a 3,85:1 da superfície; A, B e C são vinho, verde e violeta nos dois temas |
| Comparar: o radar empurrava a tabela para fora da primeira tela; legenda da abertura não batia com o desenho; nomes quebravam no hífen; ordem das linhas diferente da lista | Tabela antes do radar em tela estreita; quatro posições contáveis na abertura, com legenda só dos estados presentes; hífen sem quebra; linhas na ordem das colunas da lista |
| Lista em 1280: altura gasta antes da tabela, título apertado, valores no meio da linha | A busca entra no cabeçalho da tabela; a coluna do título ganha largura; os valores alinham pela primeira linha do título; "Só informa" alinha com os outros degraus |
| Paper aberto: faixa presa sem borda, título condensado abaixo dos metadados, endereço do código quebrando no meio da palavra, sinais com ritmo irregular, radar pequeno | A borda e o título condensado só aparecem quando a faixa prende; o endereço quebra nas barras; linhas de sinais com a mesma altura; radar maior, com a legenda embaixo; no celular a folha ocupa a tela inteira |
| Em 768 px o paper aberto era o celular esticado | A ficha usa duas colunas de tabelas; a coluna de leitura para em 680 px |
| Quatro nomes para os limites dos autores | "Limite admitido" e "Limite grave", com o tipo por extenso ("amostra pequena", "fator de confusão"), no Panorama e nos trechos. Coberto por teste |
| Legendas listavam níveis de prova ausentes e deixavam uma palavra órfã | A legenda lista só os níveis presentes no gráfico e quebra por item |
| "leitura parcial" sem dizer até onde | "Leitura parcial: o texto foi lido até …; o que vem depois ficou fora" |

### O que ficou para o Samuel ou para depois

- **Dependem das escolhas dele**: a escala da amplitude e a conta da abertura
  no radar (decisões 11 e 13, o único achado alto ainda aberto); a miniatura
  do radar na lista, apontada como ilegível por três críticos pela terceira
  vez (decisão 12); atalhos "vale ler" e "dá para adotar já" e índice do
  Panorama (decisões 5 e 6); frase em português no Resumo (decisão 8);
  "Panorama" como vista e como tipo, "Amplitude", "Abertura" e os rótulos de
  Entidades (decisão 4); dois tipos de algarismo (decisão 2).
- **Não mexido, de prioridade baixa**: o cabeçalho anda de lugar em 1600 px
  quando o paper abre; o resultado da busca não mostra por que casou; os
  filtros globais continuam visíveis em Comparar; a marca de leitura parcial
  por linha da lista.

### Regressões que as medidas pegaram durante as correções

- **Contraste de 3,91:1** no número do período selecionado, no tema escuro: o
  segmento ativo ficou mais claro e o número continuou na cor apagada. O
  número do segmento ativo usa a tinta secundária (5,8:1).
- **Nome do mais votado sumia em 360 px** no gráfico de votos e prova: a
  posição de baixo falhava por meio pixel e a de cima encostava na faixa.
  Folgas ajustadas.
- **"Harness-/S" e "ReasoningBa/nk"** quebravam no meio depois das mudanças de
  largura em Comparar (360 px) e na Ficha em duas colunas. Corrigido com menos
  respiro na caixa do nome e colunas mais largas na Ficha.
- **Botão da comparação vazia** ("Comparar os dois mais votados com prova lida")
  passava da caixa em 360 px, nos 6 casos extremos com a comparação vazia. O
  rótulo encurtou ("Comparar os dois lidos mais votados") e pode quebrar em
  duas linhas se ainda não couber.
- **Toque no tablet**, medido pela primeira vez (`alvos.mjs --largura 768`,
  com ponteiro grosso): 19 controles abaixo de 44 px. Os filtros ficavam com
  o alto da área de toque por baixo da primeira linha do cabeçalho, e o link
  do código no paper tinha 40 px. A segunda linha ganhou 4 px de folga no
  toque e o link, 44 px de alvo.

### Medidas depois das correções

| Medida | Marco zero | Depois da rodada 2 | Depois da rodada 3 |
|---|---|---|---|
| axe, nós em violação | 122 | 0, em 40 estados | 0, em 40 estados |
| Dez percursos só com teclado | 472 teclas | 10 de 10, 188 teclas | 10 de 10, 188 teclas |
| Contraste | texto mínimo de 3,36:1 | 76 pares, 0 abaixo do mínimo; pior texto 5,35:1 | igual |
| Daltonismo | 1 par abaixo de ΔE 10 | 0 nas 24 combinações | 0 nas 24 combinações |
| Casos extremos, 54 combinações | 3 quebras visuais | 0 | 0 |
| Alvos de toque em 360 px | não medido | 0 de 176 abaixo de 44 px | 0 de 176 |
| Alvos de toque em 768 px, com toque | não medido | não medido | 0 de 184 |
| Testes | não havia do painel | 25 do painel; 417 na suíte | 27 do painel; 417 na suíte |

## Rodada 4 (2026-11-16)

Notas: acabamento 7, gráficos 7, celular e tablet 6, uso e texto 7.

| Achado alto | Críticos | O que foi feito |
|---|---|---|
| O radar satura em 100 e contradiz a tabela ao lado (abertura com só o código lido, amplitude de 5 e de 9 benchmarks no mesmo vértice) | gráficos, celular | Decisões 11 e 13 do Samuel, aplicadas no Python com teste: amplitude em escala logarítmica fixa e abertura como faixa do confirmado ao máximo possível |
| O glifo que abre cada linha da lista não tem chave e não se decifra | gráficos | Decisão 12: a miniatura do radar saiu e a marca de prova abre a linha |
| Em 360 px, a linha do recorte vira um "2" solto | celular, uso | Regressão da rodada 3: margens negativas deixavam a contagem dividir a linha com os filtros. Os filtros voltaram a ocupar a linha inteira |
| "Mais vencem em Robótica" põe no pódio quem perde do rival na maioria das vezes | uso | A lista ordena pela taxa de vitória, depois pelas vitórias e pelos votos |

### Decisões do Samuel aplicadas (2026-11-16)

1. Identidade Periódico, com o display da própria identidade (Newsreader); fontes servidas pelo painel.
2. Tom direto e um nome por conceito: Ganho, Prova, Abertura, Adoção, Amplitude, Votos.
3. O painel abre em Papers, por votos ("o que vale ler hoje"); ficam os sete quadros; o tema segue o sistema.
4. A frase do problema escrita pelo modelo aparece no paper aberto ("Problema, segundo o modelo") e no índice, em itálico.
5. Filtros somados.
6. Marca de prova com cor mais preenchimento, também no lugar da miniatura do radar na lista.
7. Radar: amplitude em escala logarítmica fixa (teto em 16 benchmarks) e abertura como faixa tracejada do confirmado ao máximo possível.

### Achados médios tratados antes da rodada 5

- As réguas da mediana no topo do paper (Ganho, Prova, Adoção) ficavam em
  alturas diferentes quando uma frase quebrava em duas linhas. As três colunas
  agora dividem as mesmas linhas (`subgrid`), e as réguas alinham.
- A fonte de números (IBM Plex Mono) resolveu o espaço largo depois da vírgula
  que a rodada 4 apontou.

### Medidas na versão com as decisões

axe 0 nós em violação; teclado 10 de 10 percursos, 186 teclas; contraste com 76
pares e 0 abaixo do mínimo (pior texto 5,41:1); daltonismo 0 das 24
combinações abaixo de ΔE 10 com a paleta Periódico; casos extremos 0 de 54;
alvos de toque 0 de 176 em 360 px e 0 de 184 em 768 px; testes 27 do painel e
420 na suíte (3 novos para a amplitude e a abertura).

## Rodada 5 (2026-11-16), sobre a versão com as decisões

Notas: acabamento 7, gráficos 8, celular e tablet 7, uso e texto 7.

| Achado alto | Críticos | O que foi feito |
|---|---|---|
| A faixa da abertura no radar, tracejada, se confunde com a série B (também tracejada) e parece levar B e C ao anel de 100 | acabamento, gráficos, uso | A faixa virou uma banda larga e translúcida na cor do paper, com traço firme no fim; a legenda mostra a mesma banda |
| O paper mais votado aparece no gráfico de votos e prova com um anel sem explicação e o nome cortado | gráficos | Ele ganha nome embaixo do gráfico ("O mais votado", com votos e prova), como os papers da zona |
| "Onde está a disputa?" diz que nenhuma arena tem disputa e mesmo assim aponta quem mais vence | celular | Sem filtro de arena, o quadro só aponta vencedor onde há dois papers ou mais |
| No tablet o texto da lista e o botão de comparar ficam pequenos para o toque | celular | Com ponteiro grosso e largura de tablet, os fatos e a frase do modelo sobem para 14 px e o botão para 32 px de desenho. As capturas de 768 px passaram a sair em dobro de resolução, como as de 360 |
| "Não lida" com vários sentidos: o mesmo anel tracejado marca a fila e a prova não lida de um paper lido; "3 não lidos" solto | uso, celular | A fila perdeu a marca (a linha já diz "Na fila, ainda sem leitura"); a abertura diz "3 de 4 não lidos" |
| O ganho do paper não diz que é mediana, e a manchete ("10.7 points") não se liga à tabela | uso | "mediana de 13 resultados, contra o melhor rival externo"; a manchete mostra o número e contra quem ("10,7 pontos contra No Memory") e leva às tabelas |

Médios tratados na mesma passada: o Frágil do tema escuro ficou mais claro
(#a8b048, 4,4:1 contra a superfície, ΔE mínimo das quatro categorias mantido
em 11,5); as réguas da mediana no topo do paper alinham entre as colunas; o
itálico da frase do modelo não corta mais o último glifo.

Ficam como limite: a frase do problema vem do modelo e sai em inglês em 20 dos
28 papers; trocar isso pede mudar o prompt de leitura e reler.

Medidas depois das correções: axe 0; teclado 10 de 10, 186 teclas; contraste
76 pares, 0 abaixo do mínimo; daltonismo 0 de 24; extremos 0 de 54; alvos de
toque 0 de 177 em 360 px e 0 de 185 em 768 px; testes 27 do painel e 420 na
suíte.

## Rodada 6 (2026-11-16)

Notas: acabamento 7, gráficos 8, celular e tablet 6, uso e texto 7. Gráficos e
celular não acharam nada de prioridade alta.

| Achado alto | Críticos | O que foi feito |
|---|---|---|
| As cores da comparação repetem a rampa de prova (B em oliva se lê como Frágil) e o A rosado fica perto do vermelho de "Perde" | acabamento | A, B e C passam a azul, petróleo e violeta nos dois temas, longe dos verdes da prova e do alerta, com ΔE de 20 ou mais entre si nas três simulações de daltonismo |
| "Não lida" com vários sentidos: o nível de prova "Não lida" aparece em papers com ganho, adoção e amplitude lidos | uso | O nível passa a se chamar "Não avaliada" (o paper foi lido, mas com poucos sinais de prova para avaliar); "não lido" fica para o que a leitura não alcançou. No celular a coluna da prova alargou para caber a palavra |
| A faixa da abertura sai do radar e quase toca o rótulo; três faixas juntas parecem defeito | uso (médio para acabamento e gráficos) | Banda mais fina (4 px, 5 px entre bandas) e os nomes dos eixos 5 px mais longe do anel |

Médio tratado junto: faltava o espaço em "10,7 pontos contra No Memory".

## Rodada 7 (2026-11-16)

Notas: acabamento 7, gráficos 8, celular e tablet 7, uso e texto 7. Gráficos
sem achado alto; cada um dos outros três com um.

| Achado alto | Crítico | O que foi feito |
|---|---|---|
| As faixas da abertura ainda são a marca mais forte do radar da comparação e parecem dizer "abertura máxima" | acabamento (médio para gráficos) | A faixa virou um fio fino na cor apagada, abaixo das séries, com um anel vazado na cor do paper no máximo possível |
| "Integrar" perde a parte de baixo no radar do paper (360 e 768 px) | celular | O radar do paper ganhou 16 px de altura para os nomes de eixo em duas linhas |
| ScienceWorld Unseen aparece em duas tabelas com rivais diferentes, e o Resumo não diz de qual tabela vem cada linha | uso | O link de cada resultado no Resumo passa a nomear a tabela ("tabela 1", "tabela 2"); a Ficha já trazia o nome no título de cada tabela |

Médios tratados junto: "3 de 4 não lidos" desce inteiro para a linha de
baixo na comparação; a linha "Facilidade" da adoção no paper passou a
"Esforço", como o resto do painel.

## Rodada 8 (2026-11-16)

Notas: acabamento 7, gráficos 7, celular e tablet 7, uso e texto 7. Quatro
achados altos depois de juntar repetidos.

| Achado alto | Críticos | O que foi feito |
|---|---|---|
| Na comparação a 360 px, "3 de 4 não lidos" das três colunas se sobrepõe | celular, gráficos, uso | O texto quebra dentro da coluna. A regra da rodada 7, de não quebrar no meio, causava o transbordo e também comia o espaço antes do "·" |
| "3 de 4 não lidos" se lê como partes do paper, e "não lido" num artefato não diz se o paper não liberou ou se a leitura não verificou | celular, uso | Os artefatos vêm pelo nome e com outra palavra: "pesos, dados e demo não verificados". Na lista a coluna Abertura alargou para o texto caber inteiro |
| No radar da comparação, os fios da abertura são cinza, não têm dono e as pontas se encostam | acabamento (médio para gráficos) | Com dois ou três papers o fio leva a cor do paper; fios lado a lado a 8 px. A legenda diz "até o máximo possível" |
| "Mais vencem em Robótica" lista quem vence 5 de 15 com ganho negativo, e a ordem não segue as vitórias | uso (médio para gráficos) | O quadro lista só quem vence a maioria das disputas na arena ("Vencem a maioria em Robótica") |

## Rodada 9 (2026-11-16)

Notas: acabamento 7, gráficos 7, celular e tablet 7, uso e texto 7. Um achado
alto por crítico; acabamento e gráficos acharam o mesmo.

| Achado alto | Críticos | O que foi feito |
|---|---|---|
| No radar da comparação, os fios "até o máximo possível" e os anéis do fim são as marcas mais fortes do eixo e se leem como abertura alta medida | acabamento, gráficos | A faixa virou um intervalo: fio fino e tique de fecho, ambos na cor apagada, sem anel. Ela fica só no radar do paper aberto; na comparação a tabela ao lado já mostra os artefatos não verificados |
| A barra "Leitura: 2 inteiras · 17 parciais · 9 com prova não avaliada" soma 28 e mistura leitura com prova; com isso, "não lido" nas linhas parece contradizer a barra | uso | A barra conta só a leitura ("2 inteiras · 26 parciais"); a prova não avaliada fica no filtro Prova |
| Na lista a 360 px, "pesos, dados e demo não verificados" quebra em quatro linhas numa coluna de 90 px | celular | O texto curto passou a "resto não verificado" (o paper aberto e a dica dizem quais); no celular a abertura ganhou uma linha inteira, "liberou código · resto não verificado" |
| Na tabela da comparação a 360 px, os valores de A, B e C não começam na mesma altura | celular | O valor fica no topo da célula e a barra no pé: os três valores e as três barras se alinham |

## Rodada 10 (2026-11-16)

Notas: acabamento 7, gráficos 8, celular e tablet 7, uso e texto 8. Acabamento,
gráficos e celular não acharam nada de prioridade alta.

| Achado alto | Crítico | O que foi feito |
|---|---|---|
| "não lido" e "não lida" aparecem em papers lidos e se confundem com a fila ("Na fila, ainda sem leitura"); nenhuma linha diz se a leitura foi inteira ou parcial | uso (médio para celular) | O fato que a leitura parcial não alcançou passa a "não achado" ("ganho não achado", "abertura não achada"); cada linha da lista abre a linha de tipo com "leitura parcial", "leitura inteira" ou "só o resumo lido", também no celular |

## Rodada 11 (2026-11-16)

Notas: acabamento 7, gráficos 8, celular e tablet 7, uso e texto 7. Gráficos
sem achado alto; cada um dos outros três com um.

| Achado alto | Crítico | O que foi feito |
|---|---|---|
| No gráfico de custo, "Think Less, Locally" fica empilhado sobre "MoviEdit" e longe do próprio ponto: dá para trocar os papers | acabamento | `rotular()` passou a penalizar posição em que o nome fica mais perto de outro ponto que do seu |
| Linha cheia e pontilhada trocam de sentido: no Panorama a cheia é o zero e a pontilhada a mediana; na comparação e no paper, o contrário | celular | Uma convenção só: zero cheio, mediana pontilhada, nas barras da comparação e do paper e nas legendas |
| "26 parciais" inclui os dois papers que a linha chama de "só o resumo lido" | uso | A barra conta três estados com as palavras da linha: "2 inteiras · 24 parciais · 2 só do resumo"; o medidor deixa a parte parcial mais clara, para não parecer cheio |

## Rodada 12 (2026-11-16)

Notas: acabamento 7, gráficos 8, celular e tablet 7, uso e texto 7.
Acabamento, gráficos e uso sem achado alto.

| Achado alto | Crítico | O que foi feito |
|---|---|---|
| Com o filtro Frágil, "Onde está a disputa?" mostra "1" ao lado de "nenhuma arena tem disputa", e as arenas somam 3 papers num recorte de 2 | celular (médio para os outros três) | Sem disputa, o número grande é 0 ("arenas com disputa neste recorte: cada arena tem um paper só"), e a frase avisa quando um paper conta em mais de uma arena |
