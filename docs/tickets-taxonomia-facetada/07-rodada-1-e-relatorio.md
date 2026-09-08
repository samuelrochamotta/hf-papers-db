# 07: Rodada 1 e relatório de massa

**O que construir:** a base inteira — cerca de 2.600 papers — classificada na grade v1,
**só no Estágio A**, e um relatório que diz se a grade se sustenta. É o ponto em que as
sub-áreas deixam de ser hipótese e viram medida.

O relatório responde às duas checagens objetivas da spec:

- nenhuma sub-área acima de ~25% da sua área — acima disso, falta ramificar;
- nenhuma vertente abaixo de ~2% — abaixo disso, o rótulo deve ser absorvido.

*Adaptar* e *Explicar* são as candidatas conhecidas a sumir: na classificação manual dos
127 aprovados, *Medir* ficaria com cerca de 40 e *Adaptar* com 3.

A rodada usa concorrência 4, conforme o ADR 001 — é espera de rede, e divide por N.
Vale também a consequência que o ADR registra: rodada interrompida no meio deixa papers
já pagos sem triagem, com o gasto visível no log de custos mas fora do custo da
execução.

**Bloqueado por:** 05, 06.

**Status:** done

- [x] Backup do banco tomado antes da rodada — `data/hfpapers.db.pre-t07-20260908-162425`
- [x] Custo estimado apresentado antes de disparar — US$ 1,23; o real foi US$ 1,2326
- [x] Todos os papers da base com área, sub-área e vertente, incluindo os `fora`
      — 3.166 com vertente (100%), 3.163 com par primário (99,9%), nenhum sem
      faceta. Os 3 restantes têm par secundário e não primário: a primária deles
      caiu na validação de parentesco, e o desenho do ticket 04 manda preservar a
      melhor atribuição possível em vez de zerar o paper
- [x] Uma única rodada, com `run_id` único em toda a triagem — `run-20260908-162429`,
      3.166 papers. Houve 15 reclassificações pontuais **depois** dela, uma por
      paper, para repopular a fila de não-encaixe com os pares rejeitados (ver
      *O par rejeitado virou fila*); elas não alteram a medição da grade
- [x] Nenhuma ficha nova gerada nesta etapa — `--so-estagio-a` segurou; `dim_ficha`
      continua com as 176 de antes
- [x] Relatório com a distribuição por sub-área e por vertente, e o resultado das duas
      checagens — `docs/relatorio-massa-grade-v1.md`
- [x] Relatório com a contagem de não-encaixes por eixo — 75 no total (2,4% da base),
      com a tabela de desacordo de parentesco à parte
- [x] Custo real conferido contra a estimativa — US$ 1,2326 contra US$ 1,2300, uma
      diferença de 0,2%. A duração ficou em 0,52 h contra 1,4 h previstas, porque a
      estimativa usava o ritmo de 36,6 ch/min de antes do `esforco_raciocinio`

## O que a rodada 1 mediu

3.166 papers, 3.169 chamadas, 31 minutos, **zero cortes por prazo**. Latência p50 de
2,1 s, p90 de 3,3 s, e pior caso de **75,7 s** — abaixo do teto de 90 s, e é o número
que justifica ter escolhido 90 e não 60: um teto de 60 s teria descartado uma chamada
legítima. Roteamento: 3.164 no Together, 3 no Wafer (2 truncadas), 2 no DeepInfra.

**Checagem A — nenhuma sub-área acima de ~25% da sua área: FALHA**, 15 acima do teto.
A pior é *Internos do modelo > Interpretabilidade & sondas* com 80,2%, seguida de
*Modelo & treino > Pós-treino & RL* com 60,8% e *Percepção & robótica > VLA &
manipulação* com 53,0%. A v1 foi desenhada sobre 127 títulos e é exatamente isto que
a medição existia para revelar.

**Checagem B — nenhuma vertente abaixo de ~2%: FALHA**, 1 abaixo do piso.
*Especificar* ficou com 46 papers (1,5%). As candidatas que o ticket previa eram
outras: *Adaptar* ficou em 2,3% e *Explicar* em 6,3% — a segunda com folga, o que
derruba a previsão do desenho. Três vertentes caem na faixa de incerteza de ±3 pontos
(*Endurecer* 3,3%, *Adaptar* 2,3%, *Especificar* 1,5%), e com ~19% de ruído intrínseco
isso significa que o ticket 08 decide sobre ruído se tratá-las pelo número seco.

## O par rejeitado virou fila

A massa revelou uma lacuna do ticket 04: o par reprovado na validação de parentesco
só virava `WARNING` no log. Doze papers ficaram com faceta parcial ou nenhuma sem
aparecer em consulta alguma — um sinal que só existe no log não é fila de revisão.

E o padrão importava. Dos 15 pares rejeitados, quase todos eram os mesmos quatro, e
nenhum era rótulo inventado:

| Par que o modelo tentou | onde a grade pendura a sub-área |
|---|---|
| Harness & orquestração > Skills & conhecimento compilado | Contexto & recuperação |
| Harness & orquestração > Benchmark de agente | Avaliação & instrumentação |
| Percepção & robótica > GUI & visão de tela | Interface & modalidade |
| Internos do modelo > Pré-treino & arquitetura | Modelo & treino |

Os dois lados existem; o que o modelo recusou foi **de quem a sub-área é filha**. É a
única entrada da fila que aponta um conserto concreto — mudar o pai, não criar rótulo —
e o ticket 08 a recebe pronta.

A correção (`_registrar_par_rejeitado`) enfileira o par no eixo `subarea`, com o par
tentado na justificativa, e roda **depois** de `nao_coube`: a tabela guarda um
não-encaixe por paper, e a constatação do modelo é dado enquanto a rejeição de
parentesco é inferência nossa.

**Consequência: a fila de parentesco conta um piso, não o total.** O paper que tem
declaração do modelo *e* par rejeitado guarda só a declaração — a PK é o `paper_id` e o
primeiro registro vence. Os 15 pares desta seção vieram do log (`WARNING`), e a tabela
guardou 12. As duas medidas são legítimas e não são a mesma; a seção *Desacordo de
parentesco* do relatório de massa passou a dizer isso na cara de quem a lê.

Ao reprocessar os 15, só 4 repetiram a rejeição — os outros 11 encaixaram. É mais uma
medida do ruído de ~19% da grade, e um aviso para o ticket 08: o desacordo de
parentesco é real, mas sua contagem em uma rodada única subestima a frequência.

## Rodada 1, tentativa 1 — abortada em 2026-09-08 15:39

`run-20260908-153226`, Estágio A apenas, concorrência 4. **Sete minutos, quatro
chamadas em voo, zero concluídas.** Abortada pela regra de ritmo (piso de 10
chamadas/min).

O culpado é o roteamento: as quatro chamadas caíram todas em **Sail Research**,
que hoje mede assim no `log_llm` do Estágio A com a grade facetada:

| Provedor | chamadas | latência média | pior |
|---|---:|---:|---:|
| Together | 84 | 2,0 s | 3,9 s |
| Sail Research | 41 | 14,6 s | 55,5 s |
| DeepInfra | 1 | 28,0 s | 28,0 s |

Uma sonda com o payload real do Estágio A, fora do pipeline, pegou Sail Research
em **195,5 s para 178 tokens de saída e zero tokens de raciocínio** — não é o modo
de falha do `effort` ignorado, é endpoint lento. Oito sondas depois, o mesmo
provedor devolvia em 5,6 a 19,3 s. A cauda é o problema, não a média.

Dois achados que sobrevivem à rodada:

1. **`llm.timeout_s` não protege desta falha.** O OpenRouter manda linhas
   `: OPENROUTER PROCESSING` enquanto o provedor pensa, e cada uma reinicia o
   read timeout do httpx. Uma chamada de 195 s passa por baixo de um teto de
   180 s sem disparar nada, e a rodada fica pendurada em silêncio.
2. **`provider.require_parameters` sozinho não escolhe endpoint bom.** Dos 23
   endpoints do `z-ai/glm-5.3-flash`, 21 anunciam saída estruturada, e o
   balanceador escolhe entre eles por preço. A decisão de fixar (ou banir)
   provedor não é deste ticket.

## O que destravou — `llm.prazo_total_s`, 2026-09-08 16:30

A preferência por `Together` **não bastou**. Uma validação de 29 papers com
`provider.order: [Together]` roteou 28 das 30 chamadas para lá, e mesmo assim
teve **uma chamada de 409,8 s** — no endpoint de melhor mediana do catálogo
(3,2 s nas outras 28 com latência registrada). **Essa chamada não consumiu parte
da parede: ela *foi* a parede.** A rodada levou 409 s do início ao fim
(`log_execucao`, `run-20260908-160502`; 405 s pelo intervalo entre a primeira e a
última linha de `log_llm`), e a chamada durou 409,8 s. Com quatro threads, as
outras 29 rodaram inteiras por baixo dela, e a rodada só terminou quando ela
terminou — o ritmo caiu para 4,4 chamadas/min, abaixo do piso de 10 que aborta a
rodada.

É esse o formato da falha, e por isso ela não se mede em percentual da parede: um
número como "68%" sugere uma chamada cara entre outras, quando o que houve foi
uma rodada inteira pendurada esperando uma chamada só.

**A cauda não tem dono.** Atribuí-la ao Sail Research foi erro meu: o Together
produziu a pior chamada do dia. Trocar de endpoint trata a mediana, não a cauda,
porque a causa é a ausência de um teto de tempo efetivo — `llm.timeout_s` é read
timeout do httpx e o keep-alive `: OPENROUTER PROCESSING` o reinicia a cada
linha.

A correção é um prazo de ponta a ponta nosso: a chamada roda numa thread e é
abandonada aos 90 s, caindo na retentativa que já existia. O valor vem da
medição já sob `esforco_raciocinio` — em **201 chamadas com provedor
registrado** (as quatro rodadas de validação de 15:06–15:12, 171 chamadas, mais
as 30 de `run-20260908-160502`, que é a que expôs a cauda), o pior caso legítimo
foi 55,5 s no Estágio A e 13,8 s no Estágio B, e o valor seguinte depois de
55,5 s era 409,8 s. O teto cai no vazio entre os dois.

O denominador precisa conter a chamada de 409,8 s, senão a frase "o valor
seguinte depois de 55,5 s" não tem a que se referir. Contar também
`run-20260908-162127` — a validação já **com** o prazo ligado — daria 230, mas
aquelas 29 chamadas são resultado da correção, não a evidência que a produziu.

Duas validações, o mesmo dia de 29 papers:

| | sem prazo (`run-...160502`) | com prazo (`run-...162127`) |
|---|---:|---:|
| chamadas | 30 | 29 |
| p50 | 2,4 s | 2,8 s |
| pior caso | **409,8 s** | **5,7 s** |
| parede | 405 s | **20 s** |
| ritmo | 4,4/min | **87,0/min** |
| custo | US$ 0,0124 | US$ 0,0114 |
| triagem | 19 `fora` | 19 `fora` |

Ressalva de leitura: **nesta rodada o prazo não chegou a ser acionado** — a cauda
simplesmente não apareceu. O que a tabela prova é que o teto não cria falso
positivo. Que ele corta de fato foi provado à parte, com o prazo baixado de
propósito contra a API real, e a retentativa recuperando na tentativa seguinte.

**Correção do número.** Este parágrafo dizia "16 cortes, cada um com sua linha em
`log_llm`". O banco não tem essas 16 linhas: as únicas `ErroPrazo` que existem
são **7**, todas de `run-20260908-173724` (3 no Estágio A, 4 no B) e todas com o
prazo de 90 s. O experimento do prazo baixado rodou contra a API real, mas fora
de uma rodada registrada — ele não deixou rastro em `log_llm`, e a frase "cada um
com sua linha" não se sustenta. O que o banco sustenta são as 7 da rodada 2, que
o README já reporta como "7 chamadas em 4.407 (0,16%), todas recuperadas".

Duas consequências operacionais:

1. A chamada abandonada **continua sendo cobrada** e sua resposta é descartada
   (~US$ 0,0004). `log_llm` subestima o gasto exatamente nessas linhas, porque
   os tokens vêm na resposta que nunca foi lida. Para conferir a fatura, conte
   `erro LIKE 'ErroPrazo%'`.
2. O 6º modo de falha do OpenRouter deixa de ser silencioso: antes a chamada
   pendurada não gerava linha nenhuma.
