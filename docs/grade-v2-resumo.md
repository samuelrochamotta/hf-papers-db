# Grade v2 — o que mudou, rótulo a rótulo

- **Origem**: `relatorio-massa-grade-v1.md`, rodada `run-20260908-162429`, 3.166 papers
- **Regras**: `tickets-taxonomia-facetada/08-grade-v2.md`, aplicadas em passada única, 1 → 4
- **Resultado**: 10 áreas raiz (intactas), **64 sub-áreas** (eram 47), **10 vertentes** (eram 9)

Toda linha abaixo cita o número do relatório que a motivou. Onde a regra mandava mexer
e não se mexeu, a razão está registrada — nenhuma linha fica sem causa nem sem decisão.

> **Não regenere `relatorio-massa-grade-v1.md`.** As quatro fusões da regra 2 reescreveram
> a ponte de área, então o banco já não reproduz aquele relatório — e
> `scripts/relatorio_massa.py` grava naquele caminho por padrão, em silêncio. O relatório
> v1 é a medição que motivou esta grade; sobrescrevê-lo apaga a causa das mudanças. A
> próxima medição é a da rodada 2 e vai para outro arquivo.

## Como a estimativa da divisão foi feita

A regra 1 exige que **cada irmã fique com pelo menos 5% da área**, e esse número só
existe depois que os papers são redistribuídos — o que é trabalho do ticket 09. Para não
dividir no escuro, cada divisão foi estimada assim: as irmãs saíram da leitura dos
títulos do conjunto, viraram uma regra determinística sobre o título, e cada paper caiu
na primeira que casou; o que não casou ficou na sub-área de origem. Os percentuais de
divisão abaixo são **dessa estimativa**, não da medição — a medição real é a rodada 2.
A estimativa serve à guarda dos 5%, que é o uso que a regra faz dela.

## Regra 1 — Ramificar (sub-área acima de 25% da área)

O relatório listou **15 sub-áreas acima do teto** (checagem A: FALHA). Doze foram
divididas, três não. Em toda divisão a sub-área original **permanece**, com a definição
estreitada para dizer o que ficou nela: assim nenhum paper é movido à mão entre rótulos
que só a rodada 2 sabe separar, e a ponte não fica apontando para rótulo que sumiu.

### Divididas

| Sub-área (v1) | relatório | irmãs novas | divisão estimada |
|---|---|---|---|
| Modelo & treino > **Pós-treino & RL** | 547 papers, 60,8% | *RL agêntico & ambiente de treino* · *Otimização de política & recompensa verificável* | 174 (19,4%) · 163 (18,1%) · 210 (23,4%) |
| Geração de mídia > **Imagem & difusão** | 204 papers, 34,4% | *Edição & restauração de imagem* | 133 (22,4%) · 71 (12,0%) |
| Geração de mídia > **Vídeo & animação** | 188 papers, 31,7% | *Vídeo longo & streaming* · *Edição de vídeo* | 92 (15,5%) · 66 (11,1%) · 30 (5,1%) |
| Avaliação & instrumentação > **Benchmark de agente** | 190 papers, 42,2% | *Benchmark de agente de código* · *Benchmark de agente de computador & web* | 107 (23,8%) · 38 (8,4%) · 45 (10,0%) |
| Avaliação & instrumentação > **Benchmark de domínio** | 143 papers, 31,8% | *Benchmark científico & clínico* · *Benchmark de percepção multimodal* | 56 (12,4%) · 33 (7,3%) · 54 (12,0%) |
| Percepção & robótica > **VLA & manipulação** | 194 papers, 53,0% | *Modelo de mundo para ação* · *Dados & treino de política robótica* | 75 (20,5%) · 69 (18,9%) · 50 (13,7%) |
| Contexto & recuperação > **RAG & recuperação** | 86 papers, 37,7% | *Modelos de embedding & ranking* · *Busca agêntica* | 35 (15,4%) · 35 (15,4%) · 16 (7,0%) |
| Contexto & recuperação > **Memória de longo prazo** | 67 papers, 29,4% | *Memória multimodal & de vídeo* | 50 (21,9%) · 17 (7,5%) |
| Harness & orquestração > **Laço de execução & trajetória** | 72 papers, 32,0% | *Runtime & estado do agente* · *Uso de ferramenta & orquestração* | 25 (11,1%) · 35 (15,6%) · 12 (5,3%) |
| Serving & inferência > **Atenção, kernel & cache** | 59 papers, 40,7% | *Cache KV & compressão de contexto* | 35 (24,1%) · 24 (16,6%) |
| Guardrails & controle > **Risco & dano** | 48 papers, 42,1% | *Segurança de agente* · *Ataque & red-teaming* | 23 (20,2%) · 15 (13,2%) · 10 (8,8%) |
| Internos do modelo > **Interpretabilidade & sondas** | 73 papers, 80,2% | *Direção & edição de ativações* · *Monitoramento & atribuição causal* | 37 (40,7%) · 22 (24,2%) · 14 (15,4%) |

Duas observações que a tabela não mostra:

- **Internos do modelo > Interpretabilidade & sondas continua acima do teto** na
  estimativa: 37 papers, 40,7% da área. A regra 1 admite no máximo três irmãs, e uma
  quarta não caberia — a área inteira tem 91 papers, e a sub-área residual (interpretabilidade
  mecanicista propriamente dita) é o que sobra depois de tirar intervenção e monitoramento.
  O que está estreito é a **área**, não a sub-área: 80,2% dela é interpretabilidade
  porque é isso que "os pesos como objeto de estudo" quer dizer. Fica registrado para a
  próxima medição, com a estimativa de 40,7% como ponto de partida.
- **Duas irmãs novas já estavam na fila de não-encaixe.** *Direção & edição de ativações*
  responde os dois registros que diziam "a área Internos do modelo está certa, mas
  nenhuma filha descreve steering de ativações"; *Benchmark de percepção multimodal*
  responde os dois que diziam que Benchmark de domínio pressupõe perícia de campo e não
  cobre avaliação de VLM. Nenhum dos dois tinha quórum de oito na regra 4 — a regra 1
  chegou antes.

### Não divididas, e por quê

| Sub-área | relatório | razão |
|---|---|---|
| Serving & inferência > **Escala em tempo de inferência** | 37 papers, **25,5%** | 0,5 ponto acima do teto, e o relatório a lista na seção 7 (*Rótulos perto de um limiar*). Com ~19% de instabilidade intrínseca, dividir aqui é decidir sobre ruído. |
| Interface & modalidade > **Fala & áudio** | 19 papers, 36,5% | A divisão que os títulos sustentam é 11 / 8 (reconhecimento e transcrição de fala contra compreensão e interação por áudio). A irmã de 8 papers já nasce **abaixo do piso de 10 papers da regra 2** — a regra 1 fabricaria o que a regra 2 apaga. |
| Interface & modalidade > **GUI & visão de tela** | 18 papers, 34,6% | Divisão estimada 14 / 4. A irmã de 4 papers fica abaixo do piso de 10 **e** abaixo de 5% da área, que é a guarda da própria regra 1; e a residual continuaria em 26,9%. |

As duas sub-áreas de *Interface & modalidade* estouram o teto porque a **área** é pequena
(52 papers, 1,6% da base) e tem só quatro filhas, não porque alguma esteja inchada. É um
caso que a regra 1 não distingue: o teto é percentual e não olha o tamanho do
denominador.

## Regra 2 — Fundir (abaixo de 3% da área ou de 10 papers)

### Fundidas

| Sub-área que sai | relatório | vai para | por afinidade |
|---|---|---|---|
| Avaliação & instrumentação > **Custo da avaliação** | 2 papers, 0,4% | *Protocolo & metodologia* | os dois papers são sobre baratear a própria medição (avaliação por predição antecipada, proxy de capacidade) — o custo de medir é decisão de metodologia |
| Contexto & recuperação > **Verificação de fonte & citação** | 6 papers, 2,6% | *RAG & recuperação* | quatro dos seis são atribuição de evidência dentro de um laço de recuperação |
| Harness & orquestração > **Elicitação & requisito** | 2 papers, 0,9% | *Laço de execução & trajetória* | os dois são o agente pedindo esclarecimento antes de agir — é o primeiro passo do laço |
| Interface & modalidade > **Vídeo & streaming** | 3 papers, 5,8% | *GUI & visão de tela* | a irmã que também é canal visual em tempo real; a afinidade é a mais fraca das quatro e está registrada como tal |

Nenhuma das quatro caiu na exceção das áreas com duas sub-áreas: as áreas de origem
tinham 6, 5, 6 e 4 filhas.

### Não fundidas, e por quê

| Sub-área | relatório | razão |
|---|---|---|
| Internos do modelo > **Atalhos & espúrios** | 9 papers, 9,9% | Um paper abaixo do piso de 10. Com ~19% de instabilidade, 9 × 1,19 = 10,7: a decisão está dentro do ruído. |
| Internos do modelo > **Fidelidade do raciocínio** | 9 papers, 9,9% | Idem. E as duas são as únicas irmãs de *Interpretabilidade & sondas* na v1 — fundir as duas deixaria a área com uma filha só, que é o estado que a exceção da regra 2 existe para evitar. |

**A seção 7 do relatório não lista nenhuma das duas.** Ela mede proximidade em pontos
percentuais, e as duas estão a 6,9 pontos do piso de 3% — longe. O que está a um passo
do corte é a **contagem**, e a seção 7 não a mede. É uma lacuna do instrumento, não
do julgamento: um rótulo com 9 papers está tão perto do piso de 10 quanto um rótulo
com 2,9% está do piso de 3%.

## Regra 3 — Absorver vertente (abaixo de 2% da base)

O relatório reprovou a checagem B com **um** rótulo: *Especificar*, 46 papers, **1,5%**.
As candidatas que o desenho previa não se confirmaram — *Adaptar* ficou em 2,3% e
*Explicar* em 6,3%.

**Especificar não foi absorvida.** Três razões, nesta ordem:

1. **Está dentro da faixa de incerteza.** 0,5 ponto abaixo do piso, e o relatório a lista
   na seção 7 junto com *Endurecer* (3,3%) e *Adaptar* (2,3%). A instrução do ticket é
   que rótulo nessa faixa não se mexe pelo número seco.
2. **Medido na base: não há vertente substituta.** A co-ocorrência de *Especificar* com
   as outras se espalha sem dominante — Medir 8, Confiabilizar 8, Endurecer 5,
   Automatizar 4, Baratear 1, Explicar 1. E os 32 papers em que ela é dominante formam
   um tema coerente: contrato de execução, protocolo de coordenação, verificação formal
   de fluxo de agente, especificação antes da síntese. O que a regra 3 existe para matar
   é rótulo que não separa nada; este separa, só é raro.
3. **O denominador vai mudar de qualquer jeito.** A regra 4 promoveu *Treinar* nesta
   mesma passada, e a rodada 2 (ticket 09) redistribui a base inteira nas 64 sub-áreas
   novas. Absorver é irreversível — reescreve 46 pontes e tira o rótulo do enum do
   Estágio A, então a rodada seguinte não teria como remedi-la —, enquanto manter custa
   uma medição que já está paga.

**Consequência**: o critério de aceitação *"nenhuma vertente da v2 abaixo de 2%"* fica
**não cumprido**, por decisão registrada. O piso de seis vertentes vivas está folgado:
são dez.

Nenhum mapeamento de absorção foi declarado no arquivo de taxonomia porque nenhuma
vertente foi absorvida.

## Regra 4 — Promover não-encaixe (quórum de oito no mesmo eixo)

A fila do ticket 04 tem **75 registros** (área 32, sub-área 30, vertente 13). Três
famílias chegam ao quórum; **uma** virou rótulo.

### Promovida — vertente `Treinar`

**12 dos 13 registros de eixo `vertente`** dizem a mesma coisa: o movimento central do
paper é treinar, e nenhum dos nove verbos o cobre. As justificativas nomeiam o buraco
com precisão — *"Adaptar exclui retreino por definição e nenhum outro verbo cobre treino
de modelo"*, *"nenhum dos nove verbos cobre 'treinar/otimizar pesos'"*, *"nenhum dos nove
verbos cobre ganho de capacidade por treino"* — e cada uma registra em que rótulo o paper
foi despejado no lugar: Baratear, Confiabilizar, Adaptar, Escalar, Explicar.

A base confirma o despejo. Dentro de *Modelo & treino* (899 papers), a distribuição de
vertente é:

| vertente | atribuições | dominantes |
|---|---:|---:|
| Baratear | 360 | 339 |
| Automatizar | 165 | 163 |
| Confiabilizar | 132 | 118 |
| Medir | 105 | 75 |
| Escalar | 102 | 83 |

*Baratear* — "reduz custo, latência, memória ou tokens" — é dominante em 339 papers cujo
payload é pós-treino. Não é o que eles fazem; é o rótulo mais próximo que existia.

```
Treinar ....... muda os pesos para a peça ficar melhor: pós-treino, RL, destilação,
                adaptação com retreino
```

É o complemento exato de *Adaptar*, que a fila cita nominalmente: *Adaptar* ajusta **sem
retreinar**, *Treinar* é o caso que sobrava. O eixo continua transversal — treinar o
esboço de uma decodificação especulativa cai em *Serving & inferência > Atenção, kernel
& cache*, e treinar uma política de manipulação cai em *Percepção & robótica > Dados &
treino de política robótica* —, e a trava do ticket protege o **piso** de seis
vertentes, não o número nove.

### Com quórum e não promovida — área `neurociência & sinal biomédico`

**8 registros de eixo `area`**, exatamente no quórum: decodificação de fala por MEG,
BCI por fMRI, geometria de representação no hipocampo, códigos neurais de regiões
cerebrais, correspondência entre estímulo sensorial e atividade neural. Todos dizem que
nenhuma das dez áreas cobre sinal biomédico como peça de sistema.

**A trava do ticket vence a regra.** Promover esta família seria criar uma **11ª área
raiz**, e o ticket é explícito: *"o agente não altera as dez áreas raiz"*. Registrado
para a revisão de desenho, que é outro trabalho — a regra 4 e a trava das dez raízes se
contradizem exatamente aqui, e é a primeira vez que a contradição fica visível com
número.

As outras famílias do eixo `area` ficam abaixo do quórum: finanças e econometria (5),
ciência natural fora de LLM — proteína, fármaco, circuito quântico, clima (5).

### Sem quórum — eixo `subarea`

Nenhuma família chega a oito. A maior é visão pura sob *Percepção & robótica* —
predição densa, segmentação, backbone de sensoriamento remoto, compressão de sinal de
sensor — com **4** registros. O desacordo de parentesco da seção 4 do relatório fica em
**3** (*Harness & orquestração > Skills & conhecimento compilado*) e **1**
(*Harness & orquestração > Benchmark de agente*), os dois muito abaixo do quórum: mudar
o pai de *Benchmark de agente*, que tem 190 papers e 42,2% de *Avaliação &
instrumentação*, com um paper de evidência, seria a maior mudança estrutural da v2
apoiada no menor número do relatório. Ficam registrados.

## O que não se mexeu

- **As dez áreas raiz**: intactas, mesmas dez, mesmos nomes e definições.
- **Os dois eixos**: área hierárquica em dois níveis, vertente plana e transversal.
- **A cardinalidade**: um par primário, no máximo um secundário, uma ou duas vertentes
  ordenadas. `MAX_VERTENTES_POR_PAPER` não foi tocado.
- **Nenhuma regra reaplicada.** A regra 2 fundiu com o denominador da v1, não com o que
  a regra 1 tinha acabado de produzir; a regra 4 leu a fila da rodada 1, não a fila
  depois das fusões.

## O que a rodada 2 vai pagar a mais

O prompt do Estágio A carrega a grade inteira, e ela cresceu de 47 para 64 sub-áreas: o
prompt passou de **13.579 para 17.532 caracteres**, cerca de **mil tokens de entrada a
mais por chamada**. A rodada 1 gastou 13,9 M de tokens de entrada em 3.169 chamadas
(seção 5 do relatório), ou ~4.400 por chamada — o acréscimo é de **~23% na entrada**. A
estimativa de custo do ticket 09 foi feita sobre o prompt da v1 e precisa subir na mesma
proporção.

## O que a rodada 2 precisa remedir

1. *Internos do modelo > Interpretabilidade & sondas*, estimada em 40,7% da área.
2. *Especificar*, com o denominador redistribuído e com *Treinar* competindo por
   atribuição.
3. O efeito de *Treinar* sobre *Baratear*, que hoje leva 33,6% da base e é a suspeita
   mais forte de rótulo inflado por falta de vizinho.
4. As três divisões recusadas: *Escala em tempo de inferência*, *Fala & áudio* e
   *GUI & visão de tela*.
