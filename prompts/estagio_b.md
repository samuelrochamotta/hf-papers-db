# Estágio B — portabilidade, critérios, veredito e ficha

Você avalia um paper que passou pela triagem barata. O leitor **usa** modelos de
linguagem em produção e **não treina** modelos. A pergunta é sempre a mesma:
*o que muda no trabalho dessa pessoa por causa deste paper?*

## A ordem do raciocínio é normativa

Emita os campos exatamente nesta ordem, porque ela reproduz a ordem em que a
decisão deve ser tomada:

1. `tem_artefato_nomeado`
2. `padrao_extraido`
3. `teste_portabilidade`
4. `criterios_veredito`
5. `veredito`
6. `regra_fora`
7. `justificativa_veredito`
8. `decisao_fronteira`
9. `fronteira_contraparte`
10. `ficha`

**O padrão é escrito e testado, e os critérios são listados,
antes de o veredito ser decidido.** Decidir o veredito primeiro e escrever o
padrão ou os critérios depois inverte a regra e degrada o resultado.

## 1. `tem_artefato_nomeado`

`true` quando o paper propõe ou usa framework, sistema, benchmark ou ferramenta
**com nome próprio**. `false` para achado puramente empírico — uma medição, uma
vulnerabilidade sem ferramenta. Nesse caso o achado já é o padrão, e tanto
`padrao_extraido` quanto `teste_portabilidade` devem ser `null`.

## 2. `padrao_extraido` (só quando há artefato nomeado)

A regra estrutural que o artefato revela, em `{nome, mecanismo}`.

- `nome`: curto, até 80 caracteres, sem o nome próprio dos autores.
- `mecanismo`: uma frase, **impessoal**. Sem "você", sem verbo dirigido ao leitor.
  Descreve como a coisa funciona, não o que o leitor deve fazer.

## 3. `teste_portabilidade` (só quando há artefato nomeado)

Duas formas de reprovar, avaliadas sobre a frase que você acabou de escrever:

- `depende_do_nome_proprio`: `true` se a frase só se sustenta citando o
  framework/benchmark/ferramenta dos autores.
- `colapsa_em_generalidade`: `true` se a frase seria verdadeira de qualquer sistema
  do mesmo tipo — "iterar com feedback ajuda", "mais dado melhora o modelo".

`aprovado` é `true` somente quando os dois são `false`.

**Reprovou em qualquer um dos dois ⇒ `veredito` = `fora`**, independente do tipo de
conteúdo, com `regra_fora` = `portabilidade_reprovada` (a menos que uma regra de
conteúdo anterior na ordem já tenha batido) e `ficha` = `null`.

## 4. `criterios_veredito`, `veredito`, `regra_fora` e a justificativa

### 4.1 `criterios_veredito` — o que VALE

Liste **todos** os critérios que o paper satisfaz, e só eles. Para um paper que
vai ser aprovado, a lista tem **ao menos um** item; para `fora`, a lista é
**vazia**. Dois critérios podem coexistir (um dataset aberto que também é
benchmark tem `artefato_aberto` e `benchmark`). O "quase" não entra aqui — mora
em `fronteira_contraparte`.

**Critérios de ESTRITO** — entrega algo que o leitor adota sem treinar modelo:

- `padrao_arquitetural` — desenho reproduzível pela descrição, sem depender do
  código dos autores.
- `artefato_aberto` — biblioteca, modelo, dataset, checkpoint ou kernel aberto e
  usável.
- `invalida_pratica` — achado empírico que contradiz algo que o leitor **faz
  hoje**.
- `vulnerabilidade` — falha explorável com mecanismo descrito.
- `tecnica_de_avaliacao` — método de avaliação ou diagnóstico transferível para
  outro domínio.

**Critérios de AMPLO** — informa a decisão, não entrega o que adotar:

- `benchmark` — mede capacidade; o artefato é o instrumento de medida.
- `panorama` — sistematiza o que já existe (survey, taxonomia), sem propor nem
  medir nada novo.
- `framework_conceitual` — modelo mental sem instrumento.
- `principio_sem_o_como` — o padrão passou no teste de portabilidade, mas o paper
  não diz como implementar.
- `exige_acesso_interno` — técnica válida que pede ativações, engine de
  inferência, kernel ou retreino para ser adotada.

Três réguas para os casos difíceis:

- **Código aberto é um critério, não a régua.** Padrão arquitetural reproduzível
  pela descrição é `padrao_arquitetural` (estrito) mesmo sem código dos autores.
  "Não entrega biblioteca pronta" **não** é motivo para amplo.
- **Prática corrente é o que o leitor plausivelmente faz hoje.** Só um achado que
  contradiz isso é `invalida_pratica`. Conclusão de benchmark sobre uma prática
  que ainda não existe é contexto: o paper fica `benchmark`.
- **Treino como payload é FORA (`treino_ou_postreino`). Acesso interno como
  pré-requisito de adoção é AMPLO (`exige_acesso_interno`).** Um achado sobre
  inferência que só roda controlando a engine informa, mas não entrega.
  **`exige_acesso_interno` é excludente**: se ele vale, nenhum critério de
  estrito vale junto — estrito é "adota sem treinar e sem acesso interno". Um
  padrão "reproduzível pela descrição, mas que exige modificar o motor de
  inferência" é `exige_acesso_interno`, não `padrao_arquitetural`. Lista com
  os dois é resposta inválida e volta para você refazer.

### 4.2 `veredito` — decorre da lista

- **`estrito`** — a lista tem **qualquer** critério de estrito. Estrito
  prevalece: se entrega, entrega; o benchmark ao lado é contexto.
- **`amplo`** — a lista só tem critérios de amplo.
- **`fora`** — reprovou no teste de portabilidade, ou cai numa das regras de
  descarte. Lista de critérios vazia, `ficha` nula.

Veredito que contradiz a lista (critério de estrito com veredito `amplo`; só
critérios de amplo com veredito `estrito`; `fora` com critérios) é rejeitado e
volta para você refazer.

### 4.3 `regra_fora` — obrigatória em todo `fora`

Quando o veredito é `fora`, informe a **primeira** regra que bate, nesta ordem:
`treino_ou_postreino`, `geracao_de_midia`, `percepcao_robotica_embodied`,
`relatorio_tecnico_de_modelo`, `fora_de_escopo` (não é sobre LLM nem sobre
engenharia de sistemas com modelos de linguagem: econometria, ciência política,
dataset de fala de baixo nível), `portabilidade_reprovada` (reprovou no teste
do §3). Só uma, mesmo que mais de uma se aplique. `fora` sem regra é inválido.
Para `amplo` e `estrito`, `regra_fora` é `null`.

### 4.4 `justificativa_veredito` — aplica o critério ao paper

Escrita **depois** do veredito, nunca antes: linguagem simples e direta, no
máximo 2 frases e 300 caracteres, no mínimo 80 — resposta vazia, reticências ou
frase sem conteúdo é rejeitada e volta para você refazer. É para quem vai ler o
painel, e **aplica o critério ou a regra ao paper em vez de descrever o paper**:

- "AMPLO porque é benchmark: mede se agentes evoluem o próprio harness, não
  entrega um harness que o leitor adote."
- "ESTRITO por padrão arquitetural: a política de perguntar-ou-responder é
  reproduzível pela descrição, sem o código dos autores."
- "FORA por `treino_ou_postreino`: o payload é um objetivo de treino do modelo
  rascunho."

Quando o critério é `invalida_pratica`, **nomeie a prática invalidada** ("contradiz
monitorar o raciocínio para detectar desvio"). Não repita o Padrão Extraído nem
antecipe a ficha.

### 4.5 `decisao_fronteira` e `fronteira_contraparte`

`decisao_fronteira` é `true` quando o paper poderia legitimamente ter ido para o
outro lado — estrito↔amplo, aprovado→fora ou fora→aprovado. Quando `true`,
`fronteira_contraparte` é **obrigatória**: a regra de descarte ou o critério que
**quase venceu**, de lado **diferente** do veredito (estrito com contraparte
`benchmark`; amplo com contraparte `padrao_arquitetural` ou
`treino_ou_postreino`; fora com contraparte `exige_acesso_interno`). Quando
`false`, a contraparte é `null`. Dois lados em `criterios_veredito` **não**
obrigam fronteira: fronteira é o "quase", não a mistura. E a contraparte **não
pode estar** em `criterios_veredito` — a lista é o que vale, a contraparte é o
que quase valeu; o mesmo rótulo não é os dois.

## 5. `ficha` — obrigatória para `amplo` e `estrito`, `null` para `fora`

Quatro campos, cada um carregando uma coisa distinta. Teste de separação: **se o
texto do Padrão pudesse ser colado dentro da Implicação Prática sem soar repetido,
um dos dois está errado.**

- **`achado`** — o que o paper mostra: número e evidência, 2 a 3 frases. Voz
  descritiva. Não explique aqui a regra geral: isso é do Padrão.
- **`implicacao_pratica`** — o que muda no que a pessoa faz. Verbo de ação apontado
  para "você". Linguagem de conversa, sem jargão de ML; se um termo técnico for
  inevitável, defina-o na própria frase. Não pode ser a regra do Padrão reescrita
  com "você" na frente — precisa *aplicar* a regra a uma situação.
- **`exemplo_concreto`** — uma situação nomeada: sistema real, tarefa real, falha
  real, com o mecanismo da falha explicitado. Nunca "imagine um sistema que…".
- **`ressalva`** — onde não vale, o que não prova, a leitura errada mais provável.
  Quando o padrão passou só parcialmente, diga isso aqui explicitamente — é
  diferente de "não é código aberto" genérico.

**Proibido em qualquer campo:** elogiar o paper, chamá-lo de promissor ou
interessante, recomendar leitura. A ficha é útil ou o paper não entra.

---

## Paper

**Título:** {TITULO}

**Palavras-chave do HF:** {KEYWORDS}

**Área primária atribuída na triagem:** {AREA}
**Tópicos atribuídos na triagem:** {TOPICOS}

**Abstract:**
{ABSTRACT}

{RESUMO_HF}
