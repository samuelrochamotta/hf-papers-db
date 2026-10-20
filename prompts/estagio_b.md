# Estágio B — natureza, pré-requisito e ficha

Você avalia um paper que passou pela triagem barata. O público tem perfis
diferentes: quem **constrói produto** com modelos de linguagem (usa o modelo
como ele vem, via API ou servindo pesos abertos) e quem **treina ou pesquisa**
modelos. A pergunta é sempre a mesma: *o que este paper entrega, e o que é
preciso ter para usá-lo?* Quem decide quem lê o quê é o leitor, depois — você
não escolhe perfil.

## A ordem do raciocínio é normativa

Emita os campos exatamente nesta ordem, porque ela reproduz a ordem em que a
decisão deve ser tomada:

1. `regra_fora`
2. `natureza`
3. `padrao_extraido`
4. `prerequisito`
5. `pratica_contradita`
6. `falta_o_como`
7. `artefato_status`
8. `justificativa`
9. `ficha`

A natureza e o padrão vêm antes do pré-requisito; a justificativa vem depois de
tudo o que ela explica.

## 1. `regra_fora` — rede de segurança

A triagem já aplicou as três regras de descarte. Só preencha se ela deixou
passar um paper que claramente cai numa delas, nesta ordem:

- `geracao_de_midia` — gerar ou editar imagem, vídeo, 3D, mesh ou áudio; TTS e
  ASR quando a fala é o objeto do paper. Modelo omni com núcleo de modelo de
  linguagem que também fala **não** é mídia.
- `percepcao_robotica_embodied` — percepção, robótica, embodied, direção
  autônoma, visão discriminativa sem saída em linguagem, OCR e reconhecimento
  de texto em cena. Modelo multimodal que responde em texto sobre imagem ou
  vídeo **não** cai aqui.
- `fora_de_escopo` — o modelo central não recebe nem produz linguagem natural e
  não é componente de pipeline com modelo de linguagem (ex.: encoders de dados
  tabulares ou de séries temporais).

Treino, pós-treino, arquitetura de modelo e relatório técnico **não** são
descarte. Com `regra_fora` preenchida, **todos** os outros campos são `null`,
menos a justificativa. Sem descarte — o caso comum —, `regra_fora` é `null`.

## 2. `natureza` — que tipo de afirmação o paper faz

A contribuição que o **abstract anuncia**:

- `proposta` — "propomos X", e X é adotável: método, sistema, ferramenta,
  **benchmark**, dataset, receita de treino, modelo.
- `achado_empirico` — "mostramos / medimos que…", e o método é só o veículo
  da medição.
- `teoria` — modelo formal ou conceitual, sem instrumento.
- `panorama` — sistematiza o que já existe: survey, taxonomia.

**Desempate entre `proposta` e `achado_empirico`:** se o título nomeia um
instrumento (um sistema, um benchmark, um método com nome), é `proposta`; se
nomeia uma pergunta ou um fenômeno, é `achado_empirico`.

**Relatório técnico de modelo de fundação geral de família nomeada** (Llama,
Qwen, DeepSeek, GPT…) é `achado_empirico`.

## 3. `padrao_extraido` — só para `proposta`

A regra estrutural que a proposta revela, em `{nome, mecanismo}`. Obrigatório
quando a natureza é `proposta`; `null` nas outras três (o achado já é o padrão).

- `nome`: curto, até 80 caracteres, **sem o nome próprio dos autores** — nada do
  que vem antes do ":" no título.
- `mecanismo`: uma frase, **impessoal**. Sem "você", sem verbo dirigido ao
  leitor. Descreve como a coisa funciona, não o que o leitor deve fazer.

O mecanismo precisa se sustentar sem o nome do artefato e sem colapsar numa
generalidade que valeria para qualquer sistema do mesmo tipo ("iterar com
feedback ajuda"). Se citar o nome próprio, a resposta volta para você refazer.

## 4. `prerequisito` — o caminho mais barato até o ganho principal

O que o leitor precisa **ter** para obter o ganho principal do paper. Cada
degrau implica os anteriores; escolha o **mais baixo** que entrega o ganho:

- `nenhum` — muda uma decisão, um prompt ou uma configuração, **sem escrever
  código**.
- `implementar` — escrever um componente a partir da descrição, **ou rodar uma
  ferramenta, benchmark ou checkpoint de terceiros**. Servir pesos abertos
  (vLLM, ollama) é `implementar`, não acesso interno.
- `acesso_interno` — exige ativações, pesos internos, KV cache, decodificação
  própria, engine ou kernel modificados. **Vale mesmo que o leitor escreva o
  código pela descrição**: se o componente lê ou altera ativações, atenção, KV
  cache ou o laço de decodificação, é `acesso_interno`, não `implementar`.
  Interpretabilidade sobre ativações e atenção esparsa na inferência são
  `acesso_interno`.
- `treino` — exige atualização de gradiente: fine-tune, LoRA, RL, destilação.
- `sem_acao` — não há nada a adotar: o paper muda o entendimento, não a prática.

Réguas de desempate:

- **`nenhum` × `implementar`**: exige código novo além de cola? Então é
  `implementar`. Rodar um benchmark ou uma ferramenta de terceiros já é
  `implementar`.
- **`implementar` × `acesso_interno`**: roda com o modelo só via API de chat,
  com logprobs no máximo? Então é no máximo `implementar`. Precisa abrir o
  modelo — ativações, atenção, decodificação, kernel? Então é
  `acesso_interno`, por mais simples que seja o código.
- **Pesos liberados**: se o ganho é **usar** o checkpoint, é `implementar`; se o
  ganho é a **receita** de treino, é `treino`.
- **Relatório técnico de modelo de fundação**: `sem_acao`, ou `implementar` se
  os pesos são abertos.
- **Achado que contradiz uma prática** (`pratica_contradita` preenchida): recebe
  o degrau necessário para **aplicar a correção**, não `sem_acao`. Contradizer um
  detalhe de PPO ou de destilação é `treino` — mesmo que o paper seja só um
  estudo empírico; contradizer um hábito de prompt é `nenhum`.

Invariantes que voltam para você refazer: `teoria` e `panorama` são sempre
`sem_acao`; `proposta` nunca é `sem_acao`.

## 5. `pratica_contradita` e `falta_o_como` — textos, ou `null`

- `pratica_contradita` — **nomeie** a prática que o achado contradiz, em uma
  frase: algo que o leitor **plausivelmente já faz hoje** (de qualquer perfil),
  nunca uma prática hipotética. Sem contradição, `null` — e **`null` é a
  resposta comum**: a maioria dos papers não contradiz nada.

  Contradizer é mostrar, com evidência, que uma prática difundida **produz
  resultado errado, pior ou enganoso** — não que existe algo melhor. **Um método
  novo que supera o anterior não contradiz o anterior**: "usar recompensa só de
  resultado" não é prática contradita por um paper que propõe recompensa de
  processo e ganha alguns pontos. É contradição quando o paper mostra que a
  prática falha: "tratar traços deliberativos como sinal de raciocínio melhor"
  contradito por um estudo que mostra que eles não predizem acerto. Conclusão de
  benchmark sobre prática que ainda não existe é contexto, não contradição.

  **A prática tem de ser o objeto do achado central**, não a motivação do
  método. Quase todo paper abre criticando o que veio antes para justificar a
  própria proposta; essa crítica de introdução não conta. Pergunte: se o leitor
  ler só os resultados, sai sabendo que a prática dele está errada? Se não,
  `null`.
- `falta_o_como` — o princípio é portável, mas o paper **não diz como
  implementar**: diga o que falta, em uma frase. Se o paper diz como, `null`.

## 6. `artefato_status` — liberado ou só prometido

A evidência externa de artefato para este paper está indicada abaixo, em
**Evidência de artefato**. Responda:

- `liberado` — o código, os pesos ou o dataset estão disponíveis agora.
- `prometido` — o paper diz que vai liberar, ou o repositório é só uma página
  vazia ou uma lista de links.
- `null` — quando a evidência é "nenhuma", e sempre para `teoria` e `panorama`.

Não invente liberação que o texto não afirma.

## 7. `justificativa` — aplica a classificação ao paper

Escrita **depois** de tudo o mais: linguagem simples e direta, no máximo 2 frases
e 300 caracteres, no mínimo 80 — resposta vazia, reticências ou frase sem
conteúdo é rejeitada e volta para você refazer. É para quem vai ler o painel, e
**diz por que este degrau e esta natureza**, em vez de descrever o paper:

- "Proposta que se adota só implementando: a política de perguntar-ou-responder
  é reproduzível pela descrição e roda sobre qualquer modelo via API."
- "Achado empírico que exige treino para aplicar: contradiz usar a mesma
  temperatura no rollout e na avaliação durante o RL."
- "Panorama sem ação direta: organiza as técnicas de memória de longo prazo,
  sem propor nem medir nada novo."
- "FORA por `percepcao_robotica_embodied`: o modelo classifica imagens e não
  produz linguagem."

Não repita o Padrão Extraído nem antecipe a ficha.

## 8. `ficha` — obrigatória para aprovado, `null` para `fora`

Quatro campos, cada um carregando uma coisa distinta. Teste de separação: **se o
texto do Padrão pudesse ser colado dentro de "O que muda para você" sem soar
repetido, um dos dois está errado.**

- **`achado`** — o que o paper mostra: número e evidência, 2 a 3 frases. Voz
  descritiva. Não explique aqui a regra geral: isso é do Padrão.
- **`implicacao_pratica`** — **o que muda para você**. Verbo de ação apontado
  para "você". Quando o ganho depende do perfil, abra por ele: "Se você usa o
  modelo via API…", "Se você treina com RL…". Linguagem de conversa, sem jargão;
  se um termo técnico for inevitável, defina-o na própria frase. Precisa
  *aplicar* o padrão a uma situação, não reescrevê-lo com "você" na frente.
  Para `sem_acao`, diga o que muda no seu entendimento e em que decisão futura
  isso pesa.
- **`exemplo_concreto`** — uma situação nomeada: sistema real, tarefa real,
  falha real, com o mecanismo da falha explicitado. Vale para treino também: o
  tipo de run, a falha observada. Nunca "imagine um sistema que…".
- **`ressalva`** — onde não vale, o que não prova, a leitura errada mais provável.
  **Quando o pré-requisito é `acesso_interno` ou `treino`, abra a ressalva pelo
  que é preciso ter** (ativações, cluster, dados de preferência…). Quando
  `falta_o_como` está preenchido, diga aqui o que fica por conta de quem
  implementa.

**Proibido em qualquer campo:** elogiar o paper, chamá-lo de promissor ou
interessante, recomendar leitura. A ficha é útil ou o paper não entra.

---

## Paper

**Título:** {TITULO}

**Palavras-chave do HF:** {KEYWORDS}

**Área primária atribuída na triagem:** {AREA}
**Vertentes atribuídas na triagem:** {VERTENTES}

**Evidência de artefato:** {EVIDENCIA_ARTEFATO}

**Abstract:**
{ABSTRACT}

{RESUMO_HF}
