# hf-papers-db

Camada de dados dos Hugging Face Daily Papers: coleta, classificação por LLM em
dois estágios, base SQLite e export para o Power BI e o painel HTML.

## Language

### Classificação

**Veredito**:
O resultado da triagem de um paper: `aprovado` ou `fora`. Todo veredito sai do
pipeline (Estágio A + Estágio B); não existe outra origem. Desde o ADR 004 não
há mais grau de aprovação: o que distingue um aprovado de outro é a natureza e o
pré-requisito.
_Avoid_: estrito, amplo (regime anterior ao ADR 004), veredito herdado

**Regra de descarte** (`regra_fora`):
O motivo, único, pelo qual um paper saiu `fora`: `geracao_de_midia`,
`percepcao_robotica_embodied` ou `fora_de_escopo`, testadas nessa ordem. Todo
`fora` tem uma; a primeira que bate basta. Treino e relatório técnico deixaram
de ser descarte no ADR 004.
_Avoid_: motivo, categoria de descarte

**Natureza** (`natureza`):
Que tipo de afirmação um aprovado faz, pela contribuição que o abstract
anuncia: `proposta`, `achado_empirico`, `teoria` ou `panorama`. Não diz *o que*
o paper faz — isso é a vertente.
_Avoid_: tipo de paper, categoria, critério

**Pré-requisito** (`prerequisito`) e **degrau**:
O que o leitor precisa ter para obter o ganho principal de um aprovado. É uma
escada — `nenhum` < `implementar` < `acesso_interno` < `treino` — mais
`sem_acao`, quando não há nada a adotar. Cada valor é um **degrau**. A
contradição de uma prática recebe o degrau necessário para aplicar a correção.
_Avoid_: adoção, acionabilidade, estrito/amplo

**Perfil**:
Um conjunto de degraus em que um tipo de leitor consegue agir (produto:
`nenhum`, `implementar`; treino/pesquisa: `acesso_interno`, `treino`,
`sem_acao`). Fica **fora do paper**: vive em `config.yaml`, nenhum estágio o
escolhe, e mudar a divisão não reclassifica nada. "Dá para agir" é o paper cujo
degrau está no conjunto do perfil (`vw_paper_perfil`).
_Avoid_: público-alvo, leitor-alvo (no singular), perfil do paper

**"Treino", em quatro sentidos**:
A palavra aparece em quatro eixos e não é a mesma coisa em nenhum deles: a
vertente *Treinar* (o movimento que o paper faz), a área *Modelo & treino* (a
peça em que ele mexe), o degrau `treino` (o que o leitor precisa para adotá-lo)
e o perfil `pesquisa_treino` (quem lê). Coincidem muito, não sempre: um paper de
treino que libera o checkpoint é vertente Treinar e degrau `implementar`.

**Prática corrente** e **prática contradita** (`pratica_contradita`):
Algo que o leitor, de qualquer perfil, plausivelmente faz hoje. Um achado que a
contradiz grava a prática, nomeada, em `pratica_contradita`; conclusão sobre
prática que ainda não existe é contexto, não contradição.

**Falta o como** (`falta_o_como`):
O princípio é portável, mas o paper não diz como implementar. Texto, não
booleano: o booleano `como_incompleto` deriva dele no export.

**Evidência de artefato** e **artefato aberto**:
A evidência é externa e calculada em código (`vw_artefato`): repositório no HF,
link do GitHub ou do HF no abstract, modelo ou dataset vinculado em qualquer
snapshot. Só quando há evidência o Estágio B diz se o artefato foi `liberado` ou
só `prometido`; artefato aberto é evidência + `liberado`, e existe só na view.
_Avoid_: código aberto (era a coluna `tem_codigo_aberto`, que saiu)

**Padrão Extraído**:
A regra estrutural de uma `proposta`, impessoal e sem o nome próprio dos autores
(o que vem antes do ":" no título). O código recusa o padrão que cita o nome — é
o que sobrou do antigo teste de portabilidade, que o modelo autoavaliava.
_Avoid_: teste de portabilidade, portabilidade reprovada (regime anterior)

**Justificativa**:
A frase, para quem lê o painel, que aplica a classificação ao paper — por que
este degrau e esta natureza, ou por que esta regra de descarte. Não descreve o
paper.

### Taxonomia

**Grade**:
O vocabulário controlado vigente, inteiro: as áreas com suas sub-áreas e as
vertentes. Tem versão (v1, v2) e a versão avança por **medição**, não por
opinião. Vive no banco e é exportável para `config/taxonomia_inicial.json`.
_Avoid_: taxonomia (quando o assunto é o conteúdo e não o módulo), vocabulário
(ambíguo com as keywords do HF)

**Faceta**:
Um dos dois eixos ortogonais que localizam um paper. Área responde *em que peça
do sistema o trabalho mexe*; vertente responde *que movimento ele faz com essa
peça*. Nenhuma coordenada é dedutível da outra — é esse o teste que a grade de
tópicos falhava.
_Avoid_: dimensão, campo, tag

**Área** e **sub-área**:
Os dois níveis do eixo hierárquico, na mesma tabela: área raiz tem `area_pai`
nulo, sub-área aponta para a sua área. Uma sub-área é filha de **exatamente
uma** área. As dez áreas raiz são decisão de desenho; as sub-áreas são hipóteses
que a medição confirma ou funde.
_Avoid_: categoria, tema, tópico (o tópico era o campo que a faceta substituiu)

**Par**:
A coordenada de área de um paper: área > sub-área. O **primário** é obrigatório
e único; o **secundário** é opcional e pode repetir a área do primário desde que
a sub-área difira.
_Avoid_: área primária sozinha (o par é que localiza; a área sozinha não)

**Vertente**:
O eixo transversal, plano, que atravessa todas as áreas. Um paper recebe uma ou
duas, **ordenadas**: a de ordem 1 é a **dominante**, e é a que responde quando
um ranking precisa de uma resposta só. O teto de duas é aplicado na
persistência, não só pedido no prompt.
_Avoid_: tópico, verbo, ação

**Não-encaixe** (`tax_nao_encaixe`):
A declaração do Estágio A de que nenhuma célula da grade servia, com o **eixo**
em que o encaixe falhou (`area`, `subarea` ou `vertente`) e a justificativa. É
fila de revisão, não recusa de classificar: o paper sai com par e vertente
mesmo assim. **A classificação nunca cria rótulo**; quem promove é a revisão da
grade, por quórum. Substituiu o candidato, que pedia um nome inventado e
acumulou sinônimos.
_Avoid_: candidato, rótulo sugerido, novo tópico

### Operação

**Pendente**:
Paper na base sem linha em `fato_triagem`. Não é descartado: é fila. A rodada
seguinte o repesca.
_Avoid_: não classificado, sem veredito, falho

**Revisão** (`revisao`):
Quantas vezes o paper passou pela classificação: 0 na linha de veredito
importado, que nunca passou; 1 na primeira passagem, +1 a cada reclassificação.
Substitui a distinção "recente vs. backfill". Desde a reclassificação total de
07/09/2026 nenhuma linha está em 0 — as importadas chegaram a 1, não a 2.
_Avoid_: recentes, backfill, herdado

**Reclassificação total**:
A rodada que passa todos os papers da base pelo pipeline de novo, com o
vocabulário vigente. Se cair no meio, `reclassificar --retomar <run_id>` a
continua com o mesmo `run_id`. A marca dela é o `run_id` compartilhado por toda linha de
`fato_triagem` — não `revisao`, que sobe 1 em cada linha e deixa a importada em
1. Roda com a grade congelada: o não-encaixe é registrado, e nenhum rótulo nasce
dela.
_Avoid_: migração, backfill, "revisão ≥ 2"

**Concorrência** (`llm.concorrencia`, `--concorrencia`):
Quantas chamadas ao OpenRouter ficam no ar ao mesmo tempo dentro de uma rodada.
Só o I/O é paralelo; a escrita no banco segue na thread principal e na ordem
original dos papers, então a rodada **que completa** dá o mesmo banco em
qualquer valor. A que estoura no meio, não: os workers vão adiante e deixam
papers já pagos sem triagem.
_Avoid_: paralelizar o pipeline, rodar duas rodadas ao mesmo tempo

**Dia antigo**:
Dia de publicação anterior ao início do pipeline (26/08/2026). Entra pelo mesmo
caminho de qualquer dia: coleta por data. Não há carga especial.
_Avoid_: backfill, seed

**Digest**:
Os resumos diários de agosto/2026 produzidos antes do pipeline. Dado histórico,
sem leitor no código; não é régua de nada.
