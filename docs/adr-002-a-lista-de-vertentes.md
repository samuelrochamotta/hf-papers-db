# ADR 002 — A lista de vertentes: dez verbos, e a previsão que errou

- **Data**: 2026-09-08
- **Estado**: aceito
- **Contexto**: `spec-taxonomia-facetada.md`, seção *Further Notes*; tickets 07, 08 e 09
- **Substitui**: a lista de nove vertentes fixada na seção *A grade* da spec

## Contexto

A spec tratou as áreas e as vertentes como decisões firmes e as sub-áreas como
hipóteses. Mas ela própria registrou, em *Further Notes*, que **a lista de nove
verbos era a hipótese mais frágil do sistema** — e previu como ela cairia:

> Na classificação manual, *Medir* ficaria com cerca de 40 dos 127 e *Adaptar*
> com 3. Se a distribuição se confirmar em 2.600 papers, *Adaptar* e *Explicar*
> devem ser absorvidas.

Foi por isso que a vertente ganhou o seu próprio detector de erro: o eixo
`vertente` de `tax_nao_encaixe`, em que o modelo declara que nenhum dos verbos
serve, sem propor nome nenhum. Duas rodadas depois, sobre 3.166 papers, o
detector respondeu — e a resposta não foi a prevista. Este ADR registra a
mudança de rumo.

## Decisão

**A lista passa de nove para dez vertentes. Nenhuma foi removida; uma foi
acrescentada.**

```
Treinar ....... muda os pesos para a peça ficar melhor: pós-treino, RL,
                destilação, adaptação com retreino
```

Três achados sustentam a decisão, na ordem em que apareceram.

### 1. A previsão errou, e errou de réu

A rodada 1 (`run-20260908-162429`, grade v1, 3.166 papers) mediu:

| vertente | papers | % dos classificados | previsão da spec |
|---|---:|---:|---|
| Explicar | 198 | 6,3% | absorvida |
| Endurecer | 103 | 3,3% | — |
| Adaptar | 72 | 2,3% | absorvida |
| **Especificar** | **46** | **1,5%** | — |

*Explicar* passou com folga de três vezes o piso. *Adaptar* passou. Quem
reprovou a checagem B foi *Especificar*, que a spec não citou uma única vez
como candidata. A régua dos 127 aprovados classificados à mão previu o eixo
errado: ela mediu o que o produto **aprova**, e a grade classifica o que a base
**tem** — 65% da qual é descartada.

### 2. A grade estava faltando um verbo, não sobrando dois

**12 dos 13 registros de eixo `vertente`** da rodada 1 pedem literalmente o
mesmo verbo, e nomeiam o buraco com precisão: *"Adaptar exclui retreino por
definição e nenhum outro verbo cobre treino de modelo"*, *"nenhum dos nove
verbos cobre 'treinar/otimizar pesos'"*. Cada registro diz também em que rótulo
o paper foi despejado no lugar — Baratear, Confiabilizar, Adaptar, Escalar,
Explicar.

A base confirmou o despejo antes de o rótulo existir. Dentro de *Modelo &
treino* (899 papers na v1), *Baratear* — "reduz custo, latência, memória ou
tokens" — era **dominante em 339** deles, cujo payload é pós-treino. Não era o
que esses papers faziam; era o rótulo mais próximo que existia.

`Treinar` é o complemento exato de *Adaptar*, que a fila cita nominalmente:
*Adaptar* ajusta **sem retreinar**, *Treinar* é o caso que sobrava. O eixo
continua transversal — treinar o esboço de uma decodificação especulativa cai em
*Serving & inferência*, treinar uma política de manipulação cai em *Percepção &
robótica* —, e a trava do ticket 08 protege o **piso de seis** vertentes, não o
número nove.

### 3. A rodada 2 mediu o efeito, e ele foi grande

`run-20260908-173724`, grade v2, mesma base de 3.166 papers:

| | rodada 1 (9 verbos) | rodada 2 (10 verbos) |
|---|---:|---:|
| Treinar | — | **1.435 (45,3%)**, 1.365 dominantes |
| Baratear | 1.063 (33,6%) | **524 (16,6%)** |
| Medir | 1.001 (31,6%) | 1.007 (31,8%) |
| não-encaixe de eixo `vertente` | 13 | **2** |

*Baratear* perdeu metade da sua massa para um rótulo que não existia — a medida
mais direta de que ele estava inflado por falta de vizinho, e não por ser o que
os papers faziam. *Medir*, que não disputa treino com ninguém, não se mexeu: 31,6%
contra 31,8%. E a fila que motivou a mudança secou: **13 registros viraram 2**.

## Consequências

- **A lista de vertentes deixa de ser decisão de desenho e passa a ser decisão
  medida.** As dez áreas raiz continuam firmes; as dez vertentes agora têm a
  mesma origem que as 64 sub-áreas — massa, não leitura de título.
- **O detector de erro do próprio desenho funcionou.** O eixo `vertente` de
  `tax_nao_encaixe` foi a única peça do sistema que apontou a falha, e apontou
  com o verbo escrito por extenso. É a justificativa retroativa de a
  classificação declarar não-encaixe em vez de inventar rótulo: um campo aberto
  teria devolvido treze sinônimos de "treinar", não um verbo.
- **A régua dos aprovados não serve para dimensionar a grade.** A previsão da
  spec saiu de 127 papers aprovados; a grade classifica 3.166, dos quais 2.073
  são `fora`. Toda projeção futura de distribuição de rótulo precisa sair da
  base inteira.
- **`Baratear` continua sendo o rótulo a vigiar.** Ele caiu de 33,6% para 16,6%
  numa passada; se cair de novo na v3, a leitura é que ainda há verbo faltando
  embaixo dele.

### Pendência declarada para uma v3 — *Especificar* e *Adaptar*

A regra 3 do ticket 08 (absorver vertente abaixo de 2%) mandava absorver
*Especificar* na v2 e **foi suspensa por decisão de coordenação**, não por
leitura do implementador. O ticket 08 registrou o compromisso em letra: *"se
Especificar continuar abaixo de 2% na rodada 2, ela é absorvida sem mais
discussão."*

A rodada 2 respondeu. **Continuou, e piorou** — e arrastou uma segunda junto:

| vertente | v1 | v2 | piso |
|---|---:|---:|---:|
| Especificar | 1,5% | **1,1%** | 2% |
| Adaptar | 2,3% | **1,2%** | 2% |

Vale registrar o que a espera acertou e o que ela não salvou. As três razões da
suspensão eram: (1) *Especificar* está dentro da faixa de incerteza de ~19% de
instabilidade intrínseca da grade; (2) medida na base, ela não tem vertente
substituta — co-ocorrência espalhada, sem dominante, e 32 papers dominantes com
tema coerente (contrato de execução, protocolo de coordenação, verificação
formal); (3) o denominador ia mudar de qualquer jeito, com `Treinar` entrando na
mesma passada.

**A razão 3 estava certa quanto ao fato e errada quanto à conclusão.** O
denominador mudou muito — `Treinar` levou 45,3% da base e derrubou *Baratear*
pela metade —, e mesmo assim nenhuma das duas se recuperou: as duas caíram. A
espera custou uma rodada e comprou a informação de que a queda não era ruído de
denominador.

**Este ADR não absorve nenhuma das duas.** O ticket 10 é documentação e não mexe
na grade; absorver é reescrever pontes e tirar rótulo do enum do Estágio A, o
que exige uma rodada de reclassificação. Fica como a primeira decisão da v3, com
o que já está medido:

- *Especificar* (35 papers, 1,1%) — a razão 2 da suspensão **continua de pé**: o
  tema dominante é coerente e não há destino óbvio. Absorver aqui é escolher um
  destino, não descobri-lo. A pergunta da v3 é se um rótulo raro e coerente vale
  o custo de existir.
- *Adaptar* (38 papers, 1,2%) — caiu justamente porque `Treinar` ocupou o caso
  que a definição dela exclui ("ajusta sem retreinar"). É a candidata com
  destino mais claro das duas, e a que a spec previu que sumiria, ainda que por
  outro motivo.
- O piso de seis vertentes vivas segue folgado: são dez. Absorver as duas
  deixaria oito.
