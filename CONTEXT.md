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

### Operação

**Pendente**:
Paper na base sem linha em `fato_triagem`. Não é descartado: é fila. A rodada
seguinte o repesca.
_Avoid_: não classificado, sem veredito, falho

**Revisão** (`revisao`):
Quantas vezes o paper passou pela classificação: 1 na primeira, +1 a cada
reclassificação. Substitui a distinção "recente vs. backfill".
_Avoid_: recentes, backfill, herdado

**Reclassificação total**:
A rodada única que passa todos os papers da base pelo pipeline de novo, com o
vocabulário de critérios vigente. Depois dela, toda triagem que já existia tem
revisão ≥ 2. Roda com o vocabulário congelado: candidato novo é registrado, mas
promovido só depois, à mão.
_Avoid_: migração, backfill

**Concorrência** (`llm.concorrencia`, `--concorrencia`):
Quantas chamadas ao OpenRouter ficam no ar ao mesmo tempo dentro de uma rodada.
Só o I/O é paralelo; a escrita no banco segue na thread principal e na ordem
original dos papers, então o resultado não depende do valor.
_Avoid_: paralelizar o pipeline, rodar duas rodadas ao mesmo tempo

**Dia antigo**:
Dia de publicação anterior ao início do pipeline (26/08/2026). Entra pelo mesmo
caminho de qualquer dia: coleta por data. Não há carga especial.
_Avoid_: backfill, seed

**Digest**:
Os resumos diários de agosto/2026 produzidos antes do pipeline. Dado histórico,
sem leitor no código; não é régua de nada.
