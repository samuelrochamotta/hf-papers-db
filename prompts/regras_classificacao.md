# Regras de negócio (normativas — transporte fiel)

Esta seção é o núcleo. O regime vigente é o do ADR 004
(`docs/adr/004-natureza-e-prerequisito.md`), de 20/10/2026: o leitor tem
perfis diferentes — quem constrói produto com modelos de linguagem e quem treina
ou pesquisa modelos — e o pipeline não escolhe entre eles. Classifica o que o
paper entrega e o que é preciso ter para usá-lo; o perfil é um filtro de
leitura, fora do paper.

## 1. FORA — descarte primeiro, sem análise

Um paper cai fora se o *payload principal* for, **nesta ordem de teste**:

1. `geracao_de_midia` — gerar ou editar imagem, vídeo, 3D, mesh ou áudio; TTS e
   ASR quando a fala é o objeto do paper. Modelo omni com núcleo de modelo de
   linguagem **entra**.
2. `percepcao_robotica_embodied` — percepção, robótica, embodied, direção
   autônoma, visão discriminativa sem saída em linguagem (classificação,
   detecção, CLIP, aprendizado contínuo visual). Modelo multimodal que responde
   em texto **entra**; agente em jogo ou simulação só cai aqui com ação motora
   contínua.
3. `fora_de_escopo` — o modelo central não recebe nem produz linguagem natural e
   não é componente de pipeline com modelo de linguagem (embedder, reranker e
   parser de RAG são componentes, e entram).

**Todo `fora` tem exatamente uma regra.** A primeira que bate na ordem basta:
descarte é portão, não diagnóstico. `fora` sem regra é resposta inválida.

Treino, pós-treino, arquitetura de modelo e relatório técnico **não são
descarte** desde o ADR 004. Saíram também `portabilidade_reprovada` (o teste
virou validação do Padrão Extraído) e a meta de "~70% fora", que era do regime
anterior.

## 2. Natureza e pré-requisito — o que localiza um aprovado

**Natureza** — que tipo de afirmação o paper faz, pela contribuição que o
abstract anuncia:

| natureza | definição |
|---|---|
| `proposta` | algo adotável: método, sistema, ferramenta, benchmark, dataset, receita, modelo |
| `achado_empirico` | mostra ou mede algo; o método é veículo |
| `teoria` | modelo formal ou conceitual, sem instrumento |
| `panorama` | sistematiza o que existe: survey, taxonomia |

Desempate: o título nomeia um instrumento → `proposta`; nomeia uma pergunta ou
fenômeno → `achado_empirico`. Relatório técnico de modelo de fundação geral de
família nomeada → `achado_empirico`.

**Pré-requisito** — o caminho mais barato até o ganho principal. Escada de
capacidade: cada degrau implica os anteriores.

| degrau | o leitor precisa |
|---|---|
| `nenhum` | mudar decisão, prompt ou configuração, sem escrever código |
| `implementar` | escrever um componente pela descrição, ou rodar ferramenta, benchmark ou checkpoint de terceiros |
| `acesso_interno` | ativações, pesos internos, KV cache, decodificação própria, engine ou kernel |
| `treino` | atualização de gradiente: fine-tune, LoRA, RL, destilação |
| `sem_acao` | nada a adotar: muda o entendimento, não a prática |

Réguas que decidem os casos difíceis:

- Código novo além de cola é `implementar`; rodar ferramenta de terceiros também.
- Roda só via API de chat, com logprobs no máximo → no máximo `implementar`.
- Servir pesos abertos é `implementar`. Pesos liberados: ganho é usar o
  checkpoint → `implementar`; ganho é a receita → `treino`.
- Relatório técnico de modelo de fundação: `sem_acao`, ou `implementar` com
  pesos abertos.
- Achado que contradiz uma prática recebe o degrau necessário para aplicar a
  correção — não `sem_acao`.
- `teoria` e `panorama` são sempre `sem_acao`; `proposta` nunca é.

**Dois textos**, que valem como fato e não decidem nada:

- `pratica_contradita` — a prática que o achado contradiz, **nomeada**: algo que
  o leitor plausivelmente faz hoje. Conclusão sobre prática que ainda não existe
  é contexto, não contradição.
- `falta_o_como` — o princípio é portável, mas o paper não diz como implementar.

**Artefato aberto** tem evidência externa — repositório no HF, link no abstract,
modelo ou dataset vinculado —, calculada em código. Só quando há evidência o
modelo responde se o artefato foi `liberado` ou só `prometido`.

**Justificativa.** Aplica a classificação ao paper ("Proposta que se adota só
implementando: …"; "FORA por `geracao_de_midia`: …"); não descreve o paper.

## 3. Perfil — fora do paper

Um perfil é um conjunto de degraus, configurado em `config.yaml` (produto:
`nenhum`, `implementar`; treino/pesquisa: `acesso_interno`, `treino`,
`sem_acao`). Nenhum estágio escolhe perfil, e mudar a divisão não reclassifica
nada.

## 4. Os campos da ficha

Cada um carrega uma coisa distinta. O teste de separação: **se o texto do Padrão
pudesse ser colado dentro da Implicação Prática sem soar repetido, um dos dois está
errado.**

| Campo | Carrega | Voz |
|---|---|---|
| **Achado** | O que o paper mostra: número e evidência, 2–3 frases | Descritiva. Não explique aqui a regra geral — isso é do Padrão. |
| **Padrão Extraído** *(só para `proposta`)* | A regra estrutural | **Impessoal. Sem verbo dirigido ao leitor.** Formato: `**Nome.** Mecanismo em uma frase.` |
| **O que muda para você** (`implicacao_pratica`) | O que muda no que a pessoa faz — ou, para `sem_acao`, no que ela entende | **Verbo de ação apontado para "você"**, aberto pelo perfil quando o ganho depende dele ("Se você treina…", "Se você usa via API…"). Linguagem de conversa; termo técnico inevitável é definido na frase. Não pode ser a regra do Padrão reescrita com "você" na frente — precisa *aplicar* a regra a uma situação. |
| **Exemplo Concreto** | Uma situação nomeada: sistema real, tarefa real, falha real, com o mecanismo da falha explicitado | Nunca "imagine um sistema que…". |
| **Ressalva** | Onde não vale, o que não prova, a leitura errada mais provável | Com pré-requisito `acesso_interno` ou `treino`, abre pelo que é preciso ter. Com `falta_o_como`, diz o que fica por conta de quem implementa. |

**Proibido em qualquer campo:** elogiar o paper, chamá-lo de promissor ou
interessante, recomendar leitura. A ficha é útil ou o paper não entra.

## 5. Guardrails de volume — validação, não decisão

Calculados em código depois da classificação. **Nenhum deles altera uma
classificação** — todos apenas gravam aviso na execução. As faixas de taxa de
FORA e de aprovados/dia são **provisórias** desde o ADR 004 (ver `config.yaml`)
e são recalibradas com a distribuição da reclassificação total.

| Condição | Aviso |
|---|---|
| Taxa de FORA abaixo do mínimo | `criterio_frouxo` |
| Aprovados fora da faixa normal | `volume_atipico` |
| Aprovados acima do teto | `volume_alto` |
| Dia útil com < 15 coletados | `coleta_suspeita` |
| Zero aprovados | `dia_sem_aprovados` — resultado válido, não é erro |
| `nenhum` acima de 40% dos aprovados (com ≥ 10) | `prerequisito_nenhum_alto` |

## 6. A regra do upvote

**Upvote não entra em nenhuma decisão de classificação.** Ele é métrica de saída.
Os papers mais úteis costumam ter poucos votos; usar upvote para filtrar
descartaria justamente eles. Upvote nunca aparece no prompt de nenhum estágio.
