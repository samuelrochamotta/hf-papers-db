# hf-papers-db

Camada de dados dos Hugging Face Daily Papers: coleta, classificação por LLM em
dois estágios, base SQLite e export para o Power BI e o painel HTML.

## Language

### Classificação

**Veredito**:
O resultado da classificação de um paper: `fora`, `amplo` ou `estrito`. Todo
veredito sai do pipeline (Estágio A + Estágio B); não existe outra origem.
_Avoid_: veredito herdado, veredito do digest, veredito importado (o backfill
não classifica mais — o digest é conjunto de validação, não fonte)

**Regra de descarte** (`regra_fora`):
O motivo, único, pelo qual um paper saiu `fora`. Todo `fora` tem uma; a
primeira que bate na ordem basta.
_Avoid_: motivo, categoria de descarte, regra (sozinho, quando pode confundir
com critério)

**Critério de veredito** (`criterios_veredito`):
Por que um paper aprovado é estrito ou amplo. É uma lista com ao menos um item;
um paper pode se qualificar por mais de um. Estrito prevalece quando os lados
se misturam.
_Avoid_: leque, tipo de artefato, motivo do veredito

**Prática corrente**:
Algo que o leitor-alvo plausivelmente faz hoje. É a régua do critério
`invalida_pratica`: conclusão sobre prática que ainda não existe é contexto,
não achado.

**Justificativa**:
A frase, para quem lê o painel, que aplica a regra de descarte ou o critério de
veredito ao paper. Não descreve o paper; explica o veredito.

**Teste de portabilidade**:
A prova a que o Padrão Extraído é submetido antes do veredito: reprova se só
existe apoiado no nome próprio ou se colapsa em generalidade. Reprovar é
descarte com regra `portabilidade_reprovada`.

**Decisão de fronteira**:
Veredito que poderia legitimamente ter ido para o outro lado — estrito↔amplo,
ou aprovado↔fora. Sempre acompanhada da **contraparte**: a regra de descarte ou
o critério que quase venceu.
_Avoid_: caso limite, borderline

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
vocabulário vigente. A marca dela é o `run_id` compartilhado por toda linha de
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
