# Tarefas que o painel deve responder

Pessoa: quem constrói produto com IA e tem 5 minutos para decidir o que ler,
em que confiar e o que adotar. Cada tarefa tem resposta conferível no
`dados.json` de 2026-11-15, para que tempo e acerto possam ser medidos.

Prioridade proposta: **A** é o motivo de abrir o painel, **B** acontece em toda
visita, **C** é ocasional.

## 1. O que vale ler hoje?

| # | Tarefa | Resposta nos dados de hoje | Prio |
|---|---|---|---|
| T1 | Quais são os três papers desta semana que mais valem a leitura (muito voto e prova firme ou forte)? | Confucius4-R2T2, Few-Step Streaming Video Generation, P2-MOPD | A |
| T2 | O que entrou no último dia de coleta? | SO-Arena (13/11) | B |
| T3 | Sem sair do painel: do que trata este paper e o que ele entrega? | problema, entrega e camada do paper aberto | A |
| T4 | Quais papers ainda não foram lidos, e quanto do que vejo é leitura parcial? | 2 na fila; 9 sem leitura suficiente; 26 de 28 parciais | C |

## 2. Isso é sólido ou hype?

| # | Tarefa | Resposta nos dados de hoje | Prio |
|---|---|---|---|
| T5 | O paper mais votado tem prova? | Não se sabe: "Advances in Agentic Computer Graphics" (150 votos) não foi lido o bastante | A |
| T6 | Quais papers têm muito voto e pouca prova? | CoworkOS, Route Anything e SO-Arena (frágil ou básica, votos acima da mediana) | A |
| T7 | Por que este paper é frágil? Que sinais de prova faltam? | os sete sinais do paper aberto (CoworkOS: quais são falsos e quais não lidos) | B |
| T8 | A manchete deste paper aguenta a própria tabela? | Route Anything e SO-Arena: não confere | B |
| T9 | O que os próprios autores admitem como limite? | ressalvas literais do paper, com a seção | B |
| T10 | De onde veio este número? Ver o trecho literal e a linha da tabela. | trecho e tabela em até dois toques | B |

## 3. Dá para adotar já?

| # | Tarefa | Resposta nos dados de hoje | Prio |
|---|---|---|---|
| T11 | Quais papers dá para usar sem treinar, com algo liberado e prova pelo menos firme? | Confucius4-R2T2, Harness-S, Don't Just Trust Your Memory, Sage-Taiyi | A |
| T12 | O que este paper exige para adotar: esforço, hardware, o que liberou, onde está o código? | esforço, hardware e links do paper aberto | A |
| T13 | O que melhora gastando menos? | MoviEdit (30,9× menos), Route Anything (8,8× menos), Think Less, Locally (41,7% menos) | B |
| T14 | Sobre que modelo-base o campo está construindo? | Qwen (7 papers) | C |

## 4. Como A se compara com B?

| # | Tarefa | Resposta nos dados de hoje | Prio |
|---|---|---|---|
| T15 | Entre Wave Forcing e CoworkOS, quem tem prova mais sólida e quem é mais fácil de adotar? | Wave Forcing em solidez (75 contra 33); CoworkOS em facilidade (60 contra 40) | A |
| T16 | Este paper está acima ou abaixo da mediana do período em cada eixo? | radar do paper contra a mediana | B |
| T17 | Em que arena está a disputa e quem vence nela? | Robótica (7 papers); filtrar e ver os ganhos | B |
| T18 | Quanto os papers costumam ganhar do melhor rival, e os maiores ganhos são sólidos? | mediana +3,4%; 12 de 15 vencem; DreamX no topo | C |

## 5. Transversais

| # | Tarefa | Critério | Prio |
|---|---|---|---|
| T19 | Mandar a alguém exatamente o que estou vendo. | o endereço reproduz período, lente, paper e comparação | B |
| T20 | Desfazer um filtro e saber, a qualquer momento, em que recorte estou. | recorte sempre visível; um gesto para limpar | A |
| T21 | Fazer tudo acima só com o teclado e no celular (360 px). | sem armadilha de foco nem rolagem horizontal | A |

## Como serão medidas

Para cada tarefa: acerto, número de passos e acerto no primeiro clique,
simulados por subagentes que recebem só as capturas e o enunciado (sem o
código nem a minha justificativa). O marco zero roda as mesmas tarefas no
painel de hoje; "pronto" exige queda de passos e de erro em relação a ele.
