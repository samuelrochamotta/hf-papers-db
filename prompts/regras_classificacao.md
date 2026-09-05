# Regras de negócio (normativas — transporte fiel)

Esta seção é o núcleo. Ela vem de um pipeline em operação desde 14/08/2026 e as
faixas numéricas vêm de execuções reais.

## 1. FORA — descarte primeiro, sem análise

Um paper cai fora se o *payload principal* for:

- método de treino ou pós-treino (destilação, RL, SFT, arquitetura de modelo);
- geração de mídia (imagem, vídeo, 3D, áudio, mesh);
- percepção, robótica, embodied, direção autônoma;
- relatório técnico de modelo novo;
- assunto fora do escopo: não é sobre LLM nem sobre engenharia de sistemas com
  modelos de linguagem (econometria, ciência política, dataset de fala de baixo
  nível, biologia sem modelo de linguagem…);
- padrão que reprovou no teste de portabilidade (§2) — só o Estágio B pode
  aplicar esta, porque só ele faz o teste.

Esperado: **~70% do lote**. Abaixo de 50% indica critério frouxo.

Os seis rótulos de regra são, **nesta ordem de teste**:
`treino_ou_postreino`, `geracao_de_midia`, `percepcao_robotica_embodied`,
`relatorio_tecnico_de_modelo`, `fora_de_escopo`, `portabilidade_reprovada`.

**Todo `fora` tem exatamente uma regra.** A primeira que bate na ordem basta:
descarte é portão, não diagnóstico. Um paper de treino que também reprovaria na
portabilidade é `treino_ou_postreino`. `fora` sem regra é resposta inválida.

**Exceção: componente adotável por quem não treina.** `treino_ou_postreino` e
`relatorio_tecnico_de_modelo` **não** valem quando o paper libera um componente
pronto para quem não treina — guard model, classificador, reranker, embedder,
dataset de avaliação. A regra de treino existe para cortar "como treinar", não
"aqui está um modelo para você usar". Esse paper passa como candidato e o
Estágio B decide entre `artefato_aberto` e fora. Relatório de modelo de
fronteira (Llama, GPT, Gemini…) continua fora: não é componente, é o modelo.

## 2. Teste de portabilidade — o filtro que faz o trabalho

Só se aplica quando o paper propõe ou usa **framework, sistema ou ferramenta com
nome próprio**. Achado puramente empírico (uma medição, uma vulnerabilidade sem
ferramenta) **não recebe** o campo Padrão Extraído — o achado já é o padrão.

Escreva a frase do padrão **antes** de decidir estrito/amplo. Duas formas de reprovar:

1. **A frase só existe apoiada no nome próprio** — você não consegue descrevê-la sem
   citar o framework/benchmark/ferramenta dos autores.
2. **A frase colapsa numa generalidade óbvia** — "iterar com feedback ajuda", "mais
   dado melhora o modelo". Se seria verdadeira de qualquer sistema do mesmo tipo,
   não veio do paper.

Reprovou em qualquer um dos dois ⇒ **FORA**, com a regra `portabilidade_reprovada`
(a menos que uma regra de conteúdo anterior na ordem já tenha batido),
independente do tipo de conteúdo.

Caso frequente: o princípio de alto nível passa mas falta o "como" implementar.
Nesse caso o paper fica em **AMPLO**, com o critério `principio_sem_o_como`, não
some — e essa distinção é registrada na **Ressalva**, não no Padrão Extraído.

## 3. ESTRITO vs AMPLO — por critério, não por impressão

O veredito de um aprovado é a consequência dos **critérios** que ele satisfaz.
Liste todos que valem (um ou mais); o veredito segue a lista: **qualquer
critério de estrito ⇒ estrito**; só critérios de amplo ⇒ amplo. A lista é só o
que **vale** — o "quase" mora na contraparte da fronteira (abaixo).

**ESTRITO** — entrega algo que o leitor adota sem treinar modelo:

| critério | definição |
|---|---|
| `padrao_arquitetural` | desenho reproduzível pela descrição, sem depender do código dos autores |
| `artefato_aberto` | biblioteca, modelo, dataset, checkpoint ou kernel aberto e usável |
| `invalida_pratica` | achado empírico que contradiz algo que o leitor faz hoje |
| `vulnerabilidade` | falha explorável com mecanismo descrito |
| `tecnica_de_avaliacao` | método de avaliação ou diagnóstico transferível para outro domínio |

**AMPLO** — informa a decisão, não entrega o que adotar:

| critério | definição |
|---|---|
| `benchmark` | mede capacidade; o artefato é o instrumento de medida |
| `panorama` | sistematiza o que já existe (survey, taxonomia), sem propor nem medir nada novo |
| `framework_conceitual` | modelo mental sem instrumento |
| `principio_sem_o_como` | o padrão passou no teste de portabilidade, mas o paper não diz como implementar |
| `exige_acesso_interno` | técnica válida que pede ativações, engine de inferência, kernel ou retreino para ser adotada |

Três réguas que decidem os casos difíceis:

- **Código aberto é um critério, não a régua.** Padrão arquitetural reproduzível
  pela descrição é estrito mesmo sem código dos autores — o leitor escreve o
  código dele; o que precisa é o desenho.
- **Prática corrente é o que o leitor plausivelmente faz hoje.** Só um achado
  que contradiz isso é `invalida_pratica`; conclusão de benchmark sobre prática
  que ainda não existe é contexto, e o paper fica `benchmark`. Quando usar
  `invalida_pratica`, **nomeie a prática invalidada** na justificativa.
- **Treino como payload é FORA (regra 1). Acesso interno como pré-requisito de
  adoção é AMPLO** (`exige_acesso_interno`): achado sobre inferência que só roda
  controlando a engine, o kernel ou as ativações informa, mas não entrega.
  **`exige_acesso_interno` é excludente**: se a adoção exige acesso interno,
  nenhum critério de estrito vale ao mesmo tempo — estrito é "adota sem treinar
  e sem acesso interno". Um padrão "reproduzível pela descrição, mas que exige
  modificar o motor de inferência" é `exige_acesso_interno`, não
  `padrao_arquitetural`.

Dois lados na lista (`artefato_aberto` + `benchmark`) dão estrito e **não**
obrigam fronteira: se entrega, entrega; o benchmark é contexto.

**Fronteira.** `decisao_fronteira` é verdadeira quando o veredito poderia
legitimamente ter ido para o outro lado — estrito↔amplo, aprovado→fora ou
fora→aprovado. Sempre acompanhada de **`fronteira_contraparte`**: a regra de
descarte ou o critério que quase venceu, obrigatoriamente de lado **diferente**
do veredito (estrito com contraparte `benchmark`; amplo com contraparte
`padrao_arquitetural` ou `treino_ou_postreino`; fora com contraparte
`exige_acesso_interno`). Sem fronteira, a contraparte é nula. A contraparte
**não está** em `criterios_veredito`: a lista é o que vale, a contraparte é o
que quase valeu — o mesmo rótulo não pode ser os dois.

**Justificativa.** A justificativa **aplica o critério ou a regra ao paper**
("AMPLO porque é benchmark: mede X, não entrega Y"; "FORA por
`treino_ou_postreino`: o payload é a receita de RL"); não descreve o paper.

## 4. Os cinco campos da ficha

Cada um carrega uma coisa distinta. O teste de separação: **se o texto do Padrão
pudesse ser colado dentro da Implicação Prática sem soar repetido, um dos dois está
errado.**

| Campo | Carrega | Voz |
|---|---|---|
| **Achado** | O que o paper mostra: número e evidência, 2–3 frases | Descritiva. Não explique aqui a regra geral — isso é do Padrão. |
| **Padrão Extraído** *(condicional)* | A regra estrutural | **Impessoal. Sem verbo dirigido ao leitor.** Formato: `**Nome.** Mecanismo em uma frase.` |
| **Implicação Prática** | O que muda no que a pessoa faz | **Verbo de ação apontado para "você".** Linguagem de conversa, sem jargão de ML; se um termo técnico for inevitável, defina-o na frase. Não pode ser a regra do Padrão reescrita com "você" na frente — precisa *aplicar* a regra a uma situação. |
| **Exemplo Concreto** | Uma situação nomeada: sistema real, tarefa real, falha real, com o mecanismo da falha explicitado | Nunca "imagine um sistema que…". |
| **Ressalva** | Onde não vale, o que não prova, a leitura errada mais provável | Quando o padrão passou só parcialmente, diga isso aqui explicitamente — é diferente de "não é código aberto" genérico. |

**Proibido em qualquer campo:** elogiar o paper, chamá-lo de promissor ou
interessante, recomendar leitura. A ficha é útil ou o paper não entra.

## 5. Guardrails de volume — validação, não decisão

Calculados em código depois da classificação. **Nenhum deles altera um veredito** —
todos apenas gravam aviso na execução:

| Condição | Aviso |
|---|---|
| Taxa de FORA entre 60% e 80% | (nenhum — normal) |
| Taxa de FORA < 50% | `criterio_frouxo` |
| Aprovados fora da faixa 4–9 | `volume_atipico` |
| Aprovados > 12 | `volume_alto` |
| Dia útil com < 15 coletados | `coleta_suspeita` |
| Zero aprovados | `dia_sem_aprovados` — resultado válido, não é erro |

A taxa de FORA é a verificação mais confiável: se estiver entre 60% e 80%, o filtro
opera normalmente **mesmo com muitos aprovados**.

## 6. A regra do upvote

**Upvote não entra em nenhuma decisão de classificação.** Ele é métrica de saída.
Os papers mais úteis costumam ter poucos votos; usar upvote para filtrar
descartaria justamente eles. Upvote nunca aparece no prompt de nenhum estágio.
