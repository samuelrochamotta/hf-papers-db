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
