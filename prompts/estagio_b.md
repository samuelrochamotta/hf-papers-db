# Estágio B — portabilidade, veredito e ficha

Você avalia um paper que passou pela triagem barata. O leitor **usa** modelos de
linguagem em produção e **não treina** modelos. A pergunta é sempre a mesma:
*o que muda no trabalho dessa pessoa por causa deste paper?*

## A ordem do raciocínio é normativa

Emita os campos exatamente nesta ordem, porque ela reproduz a ordem em que a
decisão deve ser tomada:

1. `tem_artefato_nomeado`
2. `padrao_extraido`
3. `teste_portabilidade`
4. `veredito`
5. `justificativa_veredito`
6. `decisao_fronteira`
7. `ficha`

**O padrão é escrito e testado antes de o veredito ser decidido.** Decidir o
veredito primeiro e escrever o padrão depois inverte a regra e degrada o
resultado.

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
conteúdo, e `ficha` = `null`.

## 4. `veredito`

- **`estrito`** — muda uma decisão ou entrega artefato adotável por quem não treina
  modelo: padrão arquitetural reproduzível, biblioteca ou infraestrutura aberta,
  achado empírico que invalida prática corrente, vulnerabilidade explorável, ou
  técnica de avaliação transferível para outro domínio.
- **`amplo`** — informa a decisão mas não entrega o que adotar: benchmark, survey,
  relato de sistema em escala não reproduzível, framework conceitual sem
  instrumento. Também é aqui que fica o caso frequente em que o princípio de alto
  nível passa mas falta o "como" implementar — isso vai na **Ressalva**, não no
  Padrão Extraído.
- **`fora`** — reprovou no teste de portabilidade, ou cai numa das quatro regras de
  descarte (treino/pós-treino, geração de mídia, percepção/robótica/embodied,
  relatório técnico de modelo).

`justificativa_veredito` é escrita depois do veredito, nunca antes: linguagem
simples e direta, no máximo 2 frases e 300 caracteres, e no mínimo 80 — resposta
vazia, reticências ou frase sem conteúdo é rejeitada e volta para você refazer.
É para quem vai ler o painel, não para justificar o raciocínio interno — diga
em que ela se apoiou (o teste de portabilidade, a regra de descarte, o tipo de
artefato), sem repetir o Padrão Extraído nem antecipar a ficha.

`decisao_fronteira` é `true` quando o paper poderia legitimamente ter ido para o
outro lado.

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
