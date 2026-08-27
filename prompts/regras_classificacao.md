# Regras de negócio (normativas — transporte fiel)

Esta seção é o núcleo. Ela vem de um pipeline em operação desde 14/08/2026 e as
faixas numéricas vêm de execuções reais.

## 1. FORA — descarte primeiro, sem análise

Um paper cai fora se o *payload principal* for:

- método de treino ou pós-treino (destilação, RL, SFT, arquitetura de modelo);
- geração de mídia (imagem, vídeo, 3D, áudio, mesh);
- percepção, robótica, embodied, direção autônoma;
- relatório técnico de modelo novo.

Esperado: **~70% do lote**. Abaixo de 50% indica critério frouxo.

Os quatro rótulos de regra são, nesta ordem:
`treino_ou_postreino`, `geracao_de_midia`, `percepcao_robotica_embodied`,
`relatorio_tecnico_de_modelo`.

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

Reprovou em qualquer um dos dois ⇒ **FORA**, independente do tipo de conteúdo.

Caso frequente: o princípio de alto nível passa mas falta o "como" implementar.
Nesse caso o paper fica em **AMPLO**, não some — e essa distinção é registrada na
**Ressalva**, não no Padrão Extraído.

## 3. ESTRITO vs AMPLO

**ESTRITO** — muda uma decisão ou entrega artefato adotável por quem **não treina
modelo**. Qualifica se for: padrão arquitetural descrito de forma reproduzível,
biblioteca ou infraestrutura aberta, achado empírico que invalida prática corrente,
vulnerabilidade explorável, ou técnica de avaliação transferível para outro domínio.

**AMPLO** — informa decisão mas não entrega o que adotar: benchmark, survey, relato
de sistema em escala não reproduzível, framework conceitual sem instrumento.

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
