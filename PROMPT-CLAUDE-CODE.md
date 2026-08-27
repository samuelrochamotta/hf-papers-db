# Projeto `hf-papers-db` — camada de preparação de dados dos HF Daily Papers

Você vai construir, do zero, um projeto Python que roda todo dia, coleta os papers
do Hugging Face Daily Papers, classifica cada um com LLM, mantém uma base de dados
viva de métricas e exporta tabelas para consumo no Power BI.

Leia este documento inteiro antes de escrever a primeira linha. Ele contém
contratos de API já verificados empiricamente — **não re-descubra o que já está
aqui, e não presuma campos que não estão listados.**

---

## 0. O que este projeto é e o que não é

**É** uma camada de preparação de dados. A entrega final é um banco SQLite + um
conjunto de arquivos Parquet em formato estrela, prontos para o Power BI.

**Não é** um gerador de relatório. Existia antes um pipeline que produzia um digest
em markdown por dia, uma consolidação semanal às sextas, um painel HTML e um e-mail.
**Nada disso continua.** Não gere markdown de digest, não gere consolidação semanal,
não gere HTML, não mande e-mail. O Power BI é a única interface de leitura.

Sobre a consolidação semanal em particular: ela existia porque o formato diário
fragmentava a leitura, e um índice de uma linha por paper aprovado na semana
resolvia isso. **Num modelo dimensional esse problema não existe** — semana é um
atributo de `dim_calendario` (`ano_semana_iso`), então "os aprovados da semana 34"
é um filtro, não um artefato a ser gerado e guardado. Não crie um estágio, uma
tabela nem um arquivo para isso.

O que se aproveita do pipeline antigo são as **regras de classificação** (seção 6).
Elas são o ativo real do projeto e devem ser transportadas com fidelidade.

---

## 1. Visão geral do pipeline

Cinco estágios, executados em sequência por `python -m hfpapers run`:

```
[1] COLETA        → busca dias novos no HF, insere papers inéditos
[2] ENRIQUECIMENTO→ para papers inéditos, busca campos do endpoint por-paper
[3] CLASSIFICAÇÃO → Estágio A (barato) em todos; Estágio B (forte) nos sobreviventes
[4] REFRESH       → re-consulta métricas vivas de papers já na base
[5] EXPORT        → materializa os Parquet do Power BI
```

Cada estágio é idempotente e pode rodar isolado (`python -m hfpapers run --only refresh`).
Uma execução parcial que falhe no estágio 3 não pode corromper o que o estágio 1 gravou.

---

## 2. Fontes de dados — contratos verificados

Base: `https://huggingface.co`. Sem autenticação. Sem rate limit documentado —
use no máximo 5 req/s e trate 429 com backoff exponencial.

### 2.1 `GET /api/daily_papers?date=YYYY-MM-DD`

Devolve uma lista de itens. Cada item é um envelope com um objeto `paper` dentro.

**Campos do envelope externo:**

| Campo | Tipo | Observação |
|---|---|---|
| `publishedAt` | str ISO | Deslocado por fuso; **não use**. Prefira `paper.publishedAt`. |
| `title` | str | Duplicado de `paper.title` |
| `summary` | str | Duplicado de `paper.summary` |
| `thumbnail` | str | URL da imagem social |
| `numComments` | int | **Só existe aqui.** Métrica viva. |
| `submittedBy` | dict | `{name, fullname, avatarUrl, isPro, ...}` |
| `organization` | dict | `{name, fullname, avatar}` — pode estar ausente |
| `isAuthorParticipating` | bool | |

**Campos de `item["paper"]`:**

| Campo | Tipo | Observação |
|---|---|---|
| `id` | str | ID arXiv, pode vir com sufixo de versão |
| `title` | str | |
| `summary` | str | Abstract completo |
| `authors` | list | `[{name, hidden, _id, user?}]` |
| `publishedAt` | str ISO | **Data de publicação no arXiv** |
| `submittedOnDailyAt` | str ISO | **Data em que entrou na lista diária do HF** |
| `submittedOnDailyBy` | dict | |
| `upvotes` | int | Métrica viva |
| `githubStars` | int | Métrica viva; ausente se não houver repo |
| `githubRepo` | str | URL; ausente se não houver |
| `githubRepoAddedBy` | str | `"user"` ou similar |
| `projectPage` | str | Ausente se não houver |
| `discussionId` | str | |
| `ai_summary` | str | Resumo gerado pelo HF |
| `ai_keywords` | list[str] | Palavras-chave geradas pelo HF |
| `ai_summary_model` | str | Modelo que gerou o resumo |
| `organization` | dict | |

> **Atenção às duas datas.** `publishedAt` e `submittedOnDailyAt` são diferentes e
> ambas importam. Exemplo real: o paper `2608.23552` tem `publishedAt =
> 2026-08-24` e `submittedOnDailyAt = 2026-08-25`. Medido no lote de 25/08:
> **as duas datas divergem em 35 de 35 papers** — não é caso de borda, é a regra.
> O estado antigo (`hf-digest-estado.json`) colapsava as duas num único campo
> `publicado`, e por isso a base histórica tem `publicado` cobrindo de 2026-06-30
> a 2026-08-25 de forma inconsistente. No modelo novo elas são colunas separadas,
> e a data que organiza a operação diária é `submittedOnDailyAt`.

#### Opcionalidade — medida no lote de 2026-08-25 (35 papers)

Vários campos faltam com frequência alta. **Todo acesso a estes deve ser opcional**
(`.get()`, `Optional[...]` no pydantic); tratá-los como obrigatórios quebra a
ingestão em ~1 dia a cada 3.

| Campo | Presença | Como tratar |
|---|---|---|
| `id`, `title`, `summary`, `authors`, `publishedAt`, `submittedOnDailyAt`, `upvotes`, `discussionId`, `numComments` | 35/35 | Obrigatórios; falha aqui é erro de verdade |
| `ai_summary`, `ai_keywords`, `ai_summary_model` | 33/35 | Opcionais |
| `organization` | 24/35 | Opcional — `organizacao` fica NULL |
| `githubRepo`, `githubStars`, `githubRepoAddedBy` | 21/35 | Opcionais e correlacionados: sem repo, não há stars |
| `projectPage` | 12/35 | Opcional |

`tem_codigo_aberto` deriva de `githubRepo IS NOT NULL` — pelos números acima, gira
em torno de 60% do lote, e é um slicer útil no Power BI.

### 2.2 `GET /api/papers/{id}`

Aceita o id base sem versão. Devolve tudo de `item["paper"]` acima, **menos**
`numComments`, **mais**:

| Campo | Tipo |
|---|---|
| `linkedModels` | list |
| `numTotalModels` | int |
| `linkedDatasets` | list |
| `numTotalDatasets` | int |
| `linkedSpaces` | list |
| `numTotalSpaces` | int |
| `authors[].status` | str — `"claimed_verified"` quando o autor reivindicou o paper no HF |
| `authors[].user` | dict — perfil HF do autor, quando reivindicado |

### 2.3 A descoberta que define a estratégia de refresh

**Re-consultar uma data antiga devolve métricas atuais, não congeladas.** Isto foi
verificado: o paper `2608.13546`, gravado com 123 upvotes em 14/08, retorna 165
upvotes quando `?date=2026-08-14` é consultado hoje.

Consequência: para atualizar ~35 papers, **1 requisição por data** basta — não 35
requisições por paper. Uma janela quente de 30 dias custa ~22 requisições/dia
(só dias úteis têm publicação), não ~1.000.

Use `daily_papers` por data para o refresh de `upvotes`, `numComments` e
`githubStars`. Use `papers/{id}` só para os contadores de artefatos vinculados
(`numTotal*`), que mudam devagar.

### 2.4 Normalização obrigatória

- **ID base:** remova sufixo de versão com `re.sub(r'v\d+$', '', id)`. `2608.03451v2`
  e `2608.03451` são o mesmo paper. A chave primária é sempre o id base; nunca grave `v2`.
- **Fim de semana:** o feed não publica sábado e domingo. Dia vazio no fim de semana
  é normal e não é erro.
- **Volume:** 23 a 40 papers num dia útil é o normal. Menos de 15 num dia útil é
  suspeito — registre aviso e siga, não aborte.

---

## 3. Modelo de dados (SQLite)

Arquivo: `data/hfpapers.db`. Esquema estrela: um fato de métricas ao longo do tempo,
um fato de triagem, e dimensões/pontes ao redor.

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ══════════════ DIMENSÃO PRINCIPAL ══════════════
CREATE TABLE IF NOT EXISTS dim_paper (
    paper_id                TEXT PRIMARY KEY,          -- id base, sem versão
    titulo                  TEXT NOT NULL,
    abstract                TEXT,
    ai_summary              TEXT,
    ai_summary_model        TEXT,
    data_arxiv              DATE,        -- paper.publishedAt
    data_hf_daily           DATE,        -- paper.submittedOnDailyAt  (organiza a operação)
    url_arxiv               TEXT,        -- derivado: https://arxiv.org/abs/{id}
    url_hf                  TEXT,        -- derivado: https://huggingface.co/papers/{id}
    project_page            TEXT,
    github_repo             TEXT,
    github_repo_added_by    TEXT,
    tem_codigo_aberto       INTEGER,     -- 0/1, derivado de github_repo IS NOT NULL
    discussion_id           TEXT,
    thumbnail_url           TEXT,
    organizacao             TEXT,        -- organization.name
    organizacao_nome_longo  TEXT,        -- organization.fullname
    submetido_por           TEXT,        -- submittedOnDailyBy.user
    submetido_por_nome      TEXT,
    autor_participa         INTEGER,     -- isAuthorParticipating
    qtd_autores             INTEGER,
    qtd_autores_verificados INTEGER,     -- authors[].status == 'claimed_verified'
    primeiro_visto_em       TIMESTAMP NOT NULL,
    enriquecido_em          TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_paper_data_hf ON dim_paper(data_hf_daily);

-- ══════════════ FATO: MÉTRICAS VIVAS (série temporal) ══════════════
CREATE TABLE IF NOT EXISTS fato_metrica (
    paper_id        TEXT NOT NULL REFERENCES dim_paper(paper_id),
    data_snapshot   DATE NOT NULL,
    upvotes         INTEGER,
    comentarios     INTEGER,
    github_stars    INTEGER,
    qtd_modelos     INTEGER,   -- numTotalModels    (só atualizado no enriquecimento)
    qtd_datasets    INTEGER,   -- numTotalDatasets
    qtd_spaces      INTEGER,   -- numTotalSpaces
    origem          TEXT NOT NULL,   -- 'daily' | 'por_paper' | 'backfill'
    PRIMARY KEY (paper_id, data_snapshot)
);
CREATE INDEX IF NOT EXISTS ix_metrica_data ON fato_metrica(data_snapshot);

-- ══════════════ FATO: TRIAGEM ══════════════
CREATE TABLE IF NOT EXISTS fato_triagem (
    paper_id                TEXT PRIMARY KEY REFERENCES dim_paper(paper_id),
    veredito                TEXT NOT NULL CHECK (veredito IN ('fora','amplo','estrito')),
    regra_fora              TEXT,     -- qual regra da seção 6.1 disparou; NULL se aprovado
    justificativa           TEXT,
    tem_artefato_nomeado    INTEGER,  -- 0/1
    portabilidade_aprovada  INTEGER,  -- 0/1/NULL (NULL = não chegou a ser testada)
    portab_depende_nome     INTEGER,  -- 0/1/NULL — falha tipo 1
    portab_generalidade     INTEGER,  -- 0/1/NULL — falha tipo 2
    decisao_fronteira       INTEGER DEFAULT 0,  -- 1 se o modelo marcou como poderia ter ido para o outro lado
    classificado_em         TIMESTAMP NOT NULL,
    run_id                  TEXT NOT NULL,
    revisao                 INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS ix_triagem_veredito ON fato_triagem(veredito);

-- ══════════════ DIMENSÃO: FICHA (só aprovados) ══════════════
CREATE TABLE IF NOT EXISTS dim_ficha (
    paper_id            TEXT PRIMARY KEY REFERENCES dim_paper(paper_id),
    achado              TEXT NOT NULL,
    padrao_nome         TEXT,     -- NULL quando o achado é puramente empírico
    padrao_mecanismo    TEXT,
    implicacao_pratica  TEXT NOT NULL,
    exemplo_concreto    TEXT NOT NULL,
    ressalva            TEXT NOT NULL,
    gerada_em           TIMESTAMP NOT NULL,
    modelo_usado        TEXT NOT NULL,
    run_id              TEXT NOT NULL
);

-- ══════════════ VOCABULÁRIO CONTROLADO ══════════════
CREATE TABLE IF NOT EXISTS dim_area (
    area        TEXT PRIMARY KEY,
    definicao   TEXT NOT NULL,
    desde       DATE
);
CREATE TABLE IF NOT EXISTS dim_topico (
    topico      TEXT PRIMARY KEY,
    definicao   TEXT NOT NULL,
    desde       DATE
);
CREATE TABLE IF NOT EXISTS ponte_paper_area (
    paper_id    TEXT NOT NULL REFERENCES dim_paper(paper_id),
    area        TEXT NOT NULL REFERENCES dim_area(area),
    is_primaria INTEGER NOT NULL,   -- 1 = área primária, 0 = secundária
    PRIMARY KEY (paper_id, area)
);
CREATE TABLE IF NOT EXISTS ponte_paper_topico (
    paper_id    TEXT NOT NULL REFERENCES dim_paper(paper_id),
    topico      TEXT NOT NULL REFERENCES dim_topico(topico),
    PRIMARY KEY (paper_id, topico)
);
CREATE TABLE IF NOT EXISTS tax_candidato (
    rotulo      TEXT NOT NULL,
    tipo        TEXT NOT NULL CHECK (tipo IN ('area','topico')),
    definicao   TEXT NOT NULL,
    papers      TEXT NOT NULL,   -- JSON array de paper_id
    promovido   INTEGER NOT NULL DEFAULT 0,
    criado_em   TIMESTAMP NOT NULL,
    PRIMARY KEY (rotulo, tipo)
);

-- ══════════════ FACETA NÃO CONTROLADA (keywords do HF) ══════════════
CREATE TABLE IF NOT EXISTS ponte_paper_keyword (
    paper_id    TEXT NOT NULL REFERENCES dim_paper(paper_id),
    keyword     TEXT NOT NULL,
    PRIMARY KEY (paper_id, keyword)
);

-- ══════════════ AUTORES ══════════════
CREATE TABLE IF NOT EXISTS ponte_paper_autor (
    paper_id    TEXT NOT NULL REFERENCES dim_paper(paper_id),
    ordem       INTEGER NOT NULL,
    autor       TEXT NOT NULL,
    hf_user     TEXT,
    verificado  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (paper_id, ordem)
);

-- ══════════════ OPERAÇÃO ══════════════
CREATE TABLE IF NOT EXISTS log_execucao (
    run_id              TEXT PRIMARY KEY,
    iniciado_em         TIMESTAMP NOT NULL,
    finalizado_em       TIMESTAMP,
    status              TEXT NOT NULL,   -- 'ok' | 'parcial' | 'erro'
    dias_cobertos       TEXT,            -- JSON array de datas
    qtd_coletados       INTEGER,
    qtd_novos           INTEGER,
    qtd_ja_vistos       INTEGER,
    qtd_fora            INTEGER,
    qtd_amplo           INTEGER,
    qtd_estrito         INTEGER,
    taxa_fora           REAL,
    qtd_refresh         INTEGER,
    tokens_entrada      INTEGER,
    tokens_saida        INTEGER,
    custo_usd           REAL,
    avisos              TEXT             -- JSON array de strings
);

CREATE TABLE IF NOT EXISTS log_llm (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL,
    paper_id        TEXT,
    etapa           TEXT NOT NULL,       -- 'estagio_a' | 'estagio_b'
    modelo          TEXT NOT NULL,
    tokens_entrada  INTEGER,
    tokens_saida    INTEGER,
    custo_usd       REAL,
    latencia_ms     INTEGER,
    tentativas      INTEGER NOT NULL DEFAULT 1,
    erro            TEXT,
    criado_em       TIMESTAMP NOT NULL
);

-- ══════════════ CALENDÁRIO (o Power BI precisa) ══════════════
CREATE TABLE IF NOT EXISTS dim_calendario (
    data            DATE PRIMARY KEY,
    ano             INTEGER, mes INTEGER, dia INTEGER,
    nome_mes        TEXT,
    trimestre       INTEGER,
    semana_iso      INTEGER,
    ano_semana_iso  TEXT,      -- '2026-W34'
    dia_semana      INTEGER,   -- 1=segunda
    nome_dia_semana TEXT,
    eh_dia_util     INTEGER
);
```

### Regra sobre `fato_metrica`

Um snapshot por paper por dia, no máximo. Se o pipeline rodar duas vezes no mesmo
dia, o segundo `UPSERT` sobrescreve o valor daquele dia — não cria linha nova. A
granularidade é diária de propósito: é o que o Power BI precisa para plotar
trajetória de adoção.

`qtd_modelos`/`qtd_datasets`/`qtd_spaces` só são preenchidos nos snapshots de
origem `por_paper`. Nos snapshots de origem `daily` eles ficam NULL — no export,
propague o último valor conhecido (`LAST_VALUE ... IGNORE NULLS`) para não criar
buracos no gráfico.

---

## 4. Camada LLM — OpenRouter, dois níveis

### 4.1 Acesso

OpenRouter é compatível com a API da OpenAI. Use o SDK `openai` apontando a base:

```python
from openai import OpenAI
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
    default_headers={
        "HTTP-Referer": "https://github.com/<usuario>/hf-papers-db",
        "X-Title": "hf-papers-db",
    },
)
```

Chave em `.env` (`OPENROUTER_API_KEY`), carregada com `python-dotenv`.
**`.env` no `.gitignore`.** Nunca logue a chave, nem em mensagem de erro.

### 4.2 Escolha dos modelos — NÃO invente IDs

Os identificadores de modelo do OpenRouter mudam com frequência e **não devem ser
chutados**. Antes de fixar qualquer coisa:

1. `GET https://openrouter.ai/api/v1/models` e liste o que está disponível hoje,
   com preço por milhão de tokens de entrada/saída.
2. Filtre por `supported_parameters` contendo `response_format` / `structured_outputs` —
   os dois estágios dependem de saída estruturada.
3. Escreva os IDs escolhidos em `config.yaml`, **nunca no código**.

```yaml
llm:
  estagio_a:
    modelo: "PREENCHER"       # barato e rápido; roda em ~35 papers/dia
    temperatura: 0.0
    max_tokens: 1200
  estagio_b:
    modelo: "PREENCHER"       # forte; roda só nos sobreviventes (~10/dia)
    temperatura: 0.2
    max_tokens: 3000
  provider:
    require_parameters: true  # só roteia para provedores com saída estruturada
  retry:
    tentativas: 3
    backoff_inicial_s: 2
```

Passe `provider: {"require_parameters": true}` no corpo da requisição para o
OpenRouter não cair num provedor que ignore o `response_format`.

Implemente um `--dry-run` que estima o custo da rodada a partir da tabela de preços
consultada, sem chamar os modelos.

### 4.3 Estágio A — triagem barata + classificação taxonômica

Roda em **todos** os papers do dia, inclusive os que serão descartados. É ele que
garante que o Power BI tenha área e tópico para 100% da base, não só para os
aprovados.

Entrada: título + abstract + `ai_keywords` + o vocabulário controlado inteiro
(áreas e tópicos com suas definições, vindo de `dim_area`/`dim_topico`).

Saída (JSON Schema estrito):

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["veredito_preliminar","regra_fora","justificativa",
               "area_primaria","areas_secundarias","topicos","candidato_novo_rotulo"],
  "properties": {
    "veredito_preliminar": {"type":"string","enum":["fora","candidato"]},
    "regra_fora": {
      "type":["string","null"],
      "enum":["treino_ou_postreino","geracao_de_midia","percepcao_robotica_embodied",
              "relatorio_tecnico_de_modelo", null]
    },
    "justificativa": {"type":"string","maxLength":300},
    "area_primaria": {"type":"string","enum": ["<INJETAR AS ÁREAS VIGENTES>"]},
    "areas_secundarias": {"type":"array","maxItems":3,
                          "items":{"type":"string","enum":["<INJETAR>"]}},
    "topicos": {"type":"array","minItems":1,"maxItems":5,
                "items":{"type":"string","enum":["<INJETAR OS TÓPICOS VIGENTES>"]}},
    "candidato_novo_rotulo": {
      "type":["object","null"],
      "additionalProperties": false,
      "required":["rotulo","tipo","definicao"],
      "properties":{
        "rotulo":{"type":"string"},
        "tipo":{"type":"string","enum":["area","topico"]},
        "definicao":{"type":"string"}
      }
    }
  }
}
```

Os `enum` de área e tópico são **injetados em tempo de execução** a partir do banco.
Isso é o que impede a LLM de inventar rótulo e fragmentar os filtros do Power BI.

### 4.4 Estágio B — portabilidade, veredito e ficha

Roda só nos papers com `veredito_preliminar == "candidato"` (~10/dia).

A **ordem dos campos na saída é normativa**, porque reproduz a ordem do raciocínio:
o padrão é escrito e testado *antes* de o veredito ser decidido. Declare as
propriedades do schema nessa ordem e instrua explicitamente o modelo a emiti-las
nessa ordem. Não aceite uma implementação que decida o veredito primeiro e escreva
o padrão depois — isso inverte a regra da seção 6.2 e o resultado degrada.

```json
{
  "type":"object",
  "additionalProperties": false,
  "required":["tem_artefato_nomeado","padrao_extraido","teste_portabilidade",
              "veredito","justificativa_veredito","decisao_fronteira","ficha"],
  "properties":{
    "tem_artefato_nomeado":{"type":"boolean"},
    "padrao_extraido":{
      "type":["object","null"],
      "additionalProperties": false,
      "required":["nome","mecanismo"],
      "properties":{
        "nome":{"type":"string","maxLength":80},
        "mecanismo":{"type":"string"}
      }
    },
    "teste_portabilidade":{
      "type":["object","null"],
      "additionalProperties": false,
      "required":["depende_do_nome_proprio","colapsa_em_generalidade","aprovado"],
      "properties":{
        "depende_do_nome_proprio":{"type":"boolean"},
        "colapsa_em_generalidade":{"type":"boolean"},
        "aprovado":{"type":"boolean"}
      }
    },
    "veredito":{"type":"string","enum":["fora","amplo","estrito"]},
    "justificativa_veredito":{"type":"string"},
    "decisao_fronteira":{"type":"boolean"},
    "ficha":{
      "type":["object","null"],
      "additionalProperties": false,
      "required":["achado","implicacao_pratica","exemplo_concreto","ressalva"],
      "properties":{
        "achado":{"type":"string"},
        "implicacao_pratica":{"type":"string"},
        "exemplo_concreto":{"type":"string"},
        "ressalva":{"type":"string"}
      }
    }
  }
}
```

Validações pós-resposta, em código (não confie só no schema):

- `veredito == "fora"` ⇒ `ficha` deve ser `null`.
- `veredito in ("amplo","estrito")` ⇒ `ficha` obrigatória, todos os quatro campos não vazios.
- `tem_artefato_nomeado == false` ⇒ `padrao_extraido` e `teste_portabilidade` devem ser `null`.
- `tem_artefato_nomeado == true` e `teste_portabilidade.aprovado == false` ⇒ `veredito` deve ser `"fora"`.
- Se `padrao_extraido.mecanismo` contiver verbo em segunda pessoa ("você"), rejeite e re-peça:
  o Padrão é impessoal por definição (seção 6.4).

Qualquer violação: uma retentativa com a mensagem de erro anexada. Na segunda
falha, grave o paper com `veredito` do Estágio A e registre aviso na execução —
não aborte a rodada inteira por um paper.

---

## 5. Governança da taxonomia

Transportada do `taxonomia.json` e agora aplicada em código, não por convenção.

| Limite | Valor |
|---|---|
| Máximo de áreas | 10 |
| Máximo de tópicos | 24 |
| Papers distintos para promover um candidato | 2 |
| Máximo de tópicos por paper | 5 |

Fluxo quando o Estágio A devolve `candidato_novo_rotulo`:

1. Registre em `tax_candidato`, acrescentando o `paper_id` ao array `papers`.
2. O paper **ainda assim** recebe os rótulos vigentes mais próximos — nunca fica sem classificação.
3. Quando um candidato atinge 2 papers distintos **e** há folga no teto, promova-o
   para `dim_area`/`dim_topico` com `desde = hoje` e marque `promovido = 1`.
4. Se o teto estourar, **não promova**: registre aviso pedindo fusão manual de dois
   rótulos existentes. Vocabulário grande demais deixa de separar qualquer coisa.

A promoção é automática; a fusão de rótulos é manual e exige comando explícito
(`python -m hfpapers taxonomia fundir --de X --para Y`), que reescreve as pontes.

---

## 6. Regras de negócio (normativas — transporte fiel)

Esta seção é o núcleo. Ela vem de um pipeline em operação desde 14/08/2026 e as
faixas numéricas vêm de execuções reais. Coloque o texto destas regras em
`prompts/` como arquivos versionados, não embutido em f-strings no meio do código.

### 6.1 FORA — descarte primeiro, sem análise

Um paper cai fora se o *payload principal* for:

- método de treino ou pós-treino (destilação, RL, SFT, arquitetura de modelo);
- geração de mídia (imagem, vídeo, 3D, áudio, mesh);
- percepção, robótica, embodied, direção autônoma;
- relatório técnico de modelo novo.

Esperado: **~70% do lote**. Abaixo de 50% indica critério frouxo.

### 6.2 Teste de portabilidade — o filtro que faz o trabalho

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

### 6.3 ESTRITO vs AMPLO

**ESTRITO** — muda uma decisão ou entrega artefato adotável por quem **não treina
modelo**. Qualifica se for: padrão arquitetural descrito de forma reproduzível,
biblioteca ou infraestrutura aberta, achado empírico que invalida prática corrente,
vulnerabilidade explorável, ou técnica de avaliação transferível para outro domínio.

**AMPLO** — informa decisão mas não entrega o que adotar: benchmark, survey, relato
de sistema em escala não reproduzível, framework conceitual sem instrumento.

### 6.4 Os cinco campos da ficha

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

### 6.5 Guardrails de volume — validação, não decisão

Calculados em código depois da classificação. **Nenhum deles altera um veredito** —
todos apenas gravam aviso em `log_execucao.avisos`:

| Condição | Aviso |
|---|---|
| Taxa de FORA entre 60% e 80% | (nenhum — normal) |
| Taxa de FORA < 50% | `criterio_frouxo` — o filtro afrouxou, revisar prompt |
| Aprovados fora da faixa 4–9 | `volume_atipico` |
| Aprovados > 12 | `volume_alto` — checar se há agrupamento temático |
| Dia útil com < 15 coletados | `coleta_suspeita` |
| Zero aprovados | `dia_sem_aprovados` — resultado válido, não é erro |

A taxa de FORA é a verificação mais confiável: se estiver entre 60% e 80%, o filtro
opera normalmente **mesmo com muitos aprovados**.

### 6.6 A regra do upvote

**Upvote não entra em nenhuma decisão de classificação.** Ele é métrica de saída,
guardada em `fato_metrica` para você descobrir depois, no Power BI, se upvote
prediz aprovação. Os papers mais úteis costumam ter poucos votos; usar upvote para
filtrar descartaria justamente eles.

Não passe `upvotes` no prompt de nenhum dos dois estágios.

---

## 7. Refresh escalonado

```yaml
refresh:
  janela_quente_dias: 30    # todo dia
  janela_morna_dias: 90     # semanal (segunda-feira)
  # acima de 90 dias: congelado, sem refresh
  enriquecimento_semanal: true   # numTotal* da janela quente, via papers/{id}
```

Algoritmo diário:

1. Selecione as datas `data_hf_daily` distintas dentro da janela quente.
2. Uma requisição `daily_papers?date=` por data.
3. `UPSERT` em `fato_metrica` com `data_snapshot = hoje`, `origem = 'daily'`,
   gravando `upvotes`, `comentarios`, `github_stars`.
4. Se for segunda-feira, repita para a janela morna.
5. Se `enriquecimento_semanal` e for segunda: para cada paper da janela quente,
   `papers/{id}` e atualize `qtd_modelos/datasets/spaces` num snapshot
   `origem = 'por_paper'`.

Papers que saírem do feed (raro, mas acontece) não devem ser apagados — apenas
param de receber snapshots novos.

---

## 8. Export para o Power BI

Comando: `python -m hfpapers export`. Escreve em `marts/`, um Parquet por tabela,
sobrescrevendo. Use `pyarrow`. Gere também `.csv` se `export.csv: true` no config
(útil para depurar, mas o Power BI deve ler o Parquet).

| Arquivo | Grão | Papel no modelo |
|---|---|---|
| `dim_paper.parquet` | 1 linha / paper | Dimensão principal |
| `fato_metrica.parquet` | 1 linha / paper / dia | Fato — série temporal |
| `fato_triagem.parquet` | 1 linha / paper | Fato — veredito |
| `dim_ficha.parquet` | 1 linha / paper aprovado | Textos das fichas |
| `dim_area.parquet`, `dim_topico.parquet` | 1 linha / rótulo | Dimensões de vocabulário |
| `ponte_paper_area.parquet`, `ponte_paper_topico.parquet`, `ponte_paper_keyword.parquet`, `ponte_paper_autor.parquet` | pontes | Relações muitos-para-muitos |
| `dim_calendario.parquet` | 1 linha / dia | Inteligência temporal |
| `fato_execucao.parquet` | 1 linha / rodada | Saúde do pipeline |

Regras de export:

- **Datas como `date`, não string.** O Power BI precisa disso para o relacionamento
  com `dim_calendario`.
- **Não pré-agregue.** Exporte o grão fino; a agregação é papel do DAX.
- Em `fato_metrica`, propague `qtd_modelos/datasets/spaces` para frente com o último
  valor não nulo, para não abrir buraco nos gráficos.
- Acrescente em `dim_paper` colunas derivadas prontas para slicer:
  `dias_desde_publicacao`, `tem_codigo_aberto`, `tem_project_page`, `faixa_upvotes_atual`
  (bucket: 0, 1–9, 10–49, 50–99, 100+).
- Acrescente em `fato_metrica`: `upvotes_delta_dia` (diferença para o snapshot
  anterior do mesmo paper) — é o que revela quando um paper "pega tração".
- Gere `marts/_manifest.json` com a data/hora do export, o `run_id` e a contagem de
  linhas de cada arquivo, para você conferir no Power BI que está lendo dado fresco.

O Power BI Desktop lê Parquet de pasta local nativamente (Obter Dados → Parquet).
No modelo, marque `dim_calendario` como tabela de datas e relacione
`fato_metrica[data_snapshot]` → `dim_calendario[data]` e
`fato_metrica[paper_id]` → `dim_paper[paper_id]`.

---

## 9. Backfill

Comando: `python -m hfpapers backfill --seed ./seed`.

Roda uma vez. É **idempotente** — rodar de novo não duplica nada.

Ordem:

1. **Vocabulário primeiro.** Carregue `seed/taxonomia.json` → `dim_area`, `dim_topico`,
   `tax_candidato`. Os limites e definições vêm daí.
2. **Classificações à mão são autoritativas.** Todas as entradas de
   `taxonomia.json > classificacoes` vão direto para `ponte_paper_area` /
   `ponte_paper_topico`, com `is_primaria = 1` para `area` e `0` para cada uma de
   `areas_secundarias`. **Não regenere estas com LLM.** Note que elas cobrem
   sobretudo os aprovados — a maioria dos FORA não tem classificação e cai na
   etapa 6.
3. **Lista de trabalho — união das três fontes, não só o estado.** Monte o conjunto
   de ids a partir de `hf-digest-estado.json` ∪ `taxonomia.json > classificacoes` ∪
   ids extraídos dos `**arXiv:**` das fichas em `seed/digests/*.md`.

   | Fonte | ids |
   |---|---|
   | `hf-digest-estado.json` | 241 (159 fora, 28 amplo, 54 estrito) |
   | `taxonomia.json` | 83 |
   | fichas nos 8 digests | 83 |
   | **união** | **242** |

   > **Furo conhecido na base histórica.** O paper **`2608.14577`** ("HarmProfile:
   > Characterizing Harmful Distributions in Frontier LLMs") tem ficha no digest de
   > 18/08 e classificação no `taxonomia.json`, mas **falta no `estado.json`** — a
   > rodada daquele dia gravou o digest e perdeu o id ao atualizar o estado. Não
   > corrija o `estado.json` (ele é registro histórico, mantido verbatim); apenas
   > garanta que a união o recupere. Trate-o como `estrito`, conforme a seção em
   > que a ficha aparece no digest.
   >
   > Para ids que venham só dos digests, o `veredito` sai da seção onde a ficha
   > está (`## 3.` ⇒ estrito, `## 4.` ⇒ amplo) e `upvotes_dia1` sai do cabeçalho
   > `**Upvotes:**` da própria ficha.

   Números finais esperados: **242 papers, 83 aprovados** (55 estrito + 28 amplo),
   taxa de FORA histórica de 66%. Use-os como asserção — contagem diferente
   significa import errado.
4. **Hidratação.** Para cada id, `GET /api/papers/{id}` e preencha `dim_paper`
   completo + `ponte_paper_autor` + `ponte_paper_keyword`. ~241 requisições, uma vez.
   Grave um snapshot `origem='backfill'` com as métricas atuais na data de hoje, e
   **um segundo snapshot histórico** com `upvotes = upvotes_dia1` na data
   `submittedOnDailyAt` — assim a série temporal começa com dois pontos reais em vez
   de um.
5. **Triagem.** Importe o `veredito` do estado para `fato_triagem`, com
   `run_id = 'backfill'` e `revisao = 0`. Os campos de portabilidade ficam NULL
   (não foram registrados na época).
6. **Papers sem classificação taxonômica** (os que estão no estado mas não em
   `classificacoes` — em geral os FORA) passam pelo Estágio A, só para ganhar
   área e tópico. Não passam pelo Estágio B.
7. **Fichas.** Rode o Estágio B nos **83 aprovados** (28 amplo + 55 estrito) para
   preencher `dim_ficha`. É o único gasto significativo de LLM do backfill.
8. **Validação contra o histórico.** Os 8 digests em `seed/digests/` trazem **83
   fichas** escritas pelo pipeline antigo, já revisadas. Compare as regeneradas com
   elas: mesmo veredito? mesma presença/ausência de Padrão Extraído? mesmo nome de
   padrão? Escreva `relatorios/validacao_backfill.md` com as divergências.
   **Isto não corrige nada automaticamente** — é o instrumento para julgar se o
   prompt novo reproduz a qualidade do antigo antes de você confiar nele. Se
   divergir muito, o problema está no prompt do Estágio B, não nas fichas antigas.

   Cada digest é internamente consistente (o número de blocos `###` bate com
   `Amplo + Estrito` da sua tabela de Operação) — use isso como teste do parser:
   se a contagem não fechar para algum dia, o parser está errado, não o arquivo.

### Gramática dos digests históricos (para o parser da etapa 8)

Cinco seções `##` numeradas: `## 1. Operação` … `## 5. Avisos`.
A seção 1 tem uma tabela de uma linha com colunas
`Dia coberto | Coletados | Descartados por estado | FORA | Amplo | Estrito`.
Fichas ficam em `## 3. Critério estrito` e `## 4. Critério amplo`, cada uma com:

```
### <título completo>
**arXiv:** 2608.06867 | **Data:** 2026-08-14 | **Upvotes:** 103

**ACHADO:** …
**PADRÃO EXTRAÍDO:** **<nome>.** <mecanismo>     ← campo opcional, pode não existir
**IMPLICAÇÃO PRÁTICA:** …
**EXEMPLO CONCRETO:** …
**RESSALVA:** …
```

O parser deve tolerar a ausência do bloco **PADRÃO EXTRAÍDO** — é condicional por
desenho, e um dos papers de 14/08 (`2608.12440`) legitimamente não o tem.

---

## 10. Execução, configuração e agendamento

### CLI

```
python -m hfpapers run                  # pipeline completo do dia
python -m hfpapers run --data 2026-08-25    # força uma data específica
python -m hfpapers run --only coleta,export  # subconjunto de estágios
python -m hfpapers run --dry-run        # estima custo, não chama LLM
python -m hfpapers backfill --seed ./seed
python -m hfpapers export
python -m hfpapers reclassificar --data 2026-08-25 [--paper 2608.23552]
python -m hfpapers taxonomia listar|fundir
python -m hfpapers doutor              # diagnóstico: chave ok? API ok? banco íntegro?
```

### Recuperação de lacuna

Compare `MAX(data_hf_daily)` no banco com hoje. Se houver mais de um dia de
publicação descoberto (feriado, falha, máquina desligada), colete **todos** os dias
faltantes na mesma rodada e trate como lote único. Registre
`lacuna_recuperada: [datas]` nos avisos.

### Agendamento (Windows)

Gere `scripts/run_daily.ps1` que ativa o venv, roda `python -m hfpapers run`, e
escreve o código de saída num log rotativo em `logs/`. Documente no README o
comando `schtasks` para registrar a tarefa diária. Sugestão de horário: início da
manhã, depois de o HF ter publicado o dia anterior.

O script deve sair com código != 0 quando o estágio de coleta falhar, para que o
Agendador de Tarefas marque a execução como falha e você perceba.

---

## 11. Qualidades não funcionais

**Idempotência.** Rodar duas vezes no mesmo dia não pode duplicar linha nem
re-cobrar LLM de paper já classificado. `fato_triagem` e `dim_ficha` só são
reescritos com `--force` ou pelo comando `reclassificar` (que incrementa `revisao`).

**Falha parcial não corrompe.** Cada estágio commita sua própria transação. Se o
Estágio B estourar no paper 7 de 10, os 6 primeiros ficam gravados e a execução
termina com `status = 'parcial'`.

**Custo visível.** Toda chamada de LLM grava tokens e custo em `log_llm`. O resumo
por rodada vai para `log_execucao` e para o `stdout` ao final. Você deve conseguir
responder "quanto custou este mês" com uma query.

**Concorrência com o Power BI.** O Power BI pode estar com os Parquet abertos.
Escreva em arquivo temporário e renomeie (`os.replace`) — atômico no Windows para
arquivos no mesmo volume.

**Logging.** `structlog` ou `logging` com formato legível no console e JSON em
arquivo. Nunca logue a chave da API.

---

## 12. Estrutura sugerida

```
hf-papers-db/
├── pyproject.toml
├── README.md
├── .env.example              # OPENROUTER_API_KEY=
├── .gitignore                # .env, data/, marts/, logs/
├── config.yaml
├── src/hfpapers/
│   ├── __main__.py           # CLI (typer)
│   ├── config.py             # pydantic-settings
│   ├── db.py                 # conexão, migrações, upserts
│   ├── schema.sql
│   ├── fontes/
│   │   ├── hf_client.py      # httpx + retry + rate limit
│   │   └── modelos.py        # pydantic dos payloads do HF
│   ├── llm/
│   │   ├── cliente.py        # OpenRouter, retry, contabilidade de custo
│   │   ├── estagio_a.py
│   │   ├── estagio_b.py
│   │   └── schemas.py        # os JSON Schemas
│   ├── estagios/
│   │   ├── coleta.py
│   │   ├── enriquecimento.py
│   │   ├── classificacao.py
│   │   ├── refresh.py
│   │   └── export.py
│   ├── taxonomia.py          # governança, promoção de candidatos
│   ├── guardrails.py         # seção 6.5
│   └── backfill.py
├── prompts/
│   ├── estagio_a.md
│   ├── estagio_b.md
│   └── regras_classificacao.md   # seção 6 deste documento, verbatim
├── seed/
├── data/hfpapers.db
├── marts/                    # ← o Power BI aponta para cá
├── logs/
├── scripts/run_daily.ps1
└── tests/
    ├── fixtures/             # respostas reais gravadas do HF
    └── test_*.py
```

Dependências: `httpx`, `pydantic`, `pydantic-settings`, `typer`, `pyarrow`,
`python-dotenv`, `openai`, `pyyaml`, `pytest`, `respx` (mock de httpx).

Python 3.11+.

---

## 13. Testes e critérios de aceite

Grave fixtures reais (`daily_papers?date=2026-08-25` e `papers/2608.23552`) em
`tests/fixtures/` e teste contra elas com `respx` — sem rede nos testes.

O projeto está pronto quando:

1. `pytest` passa, com cobertura dos parsers, do dedup de versão, dos guardrails e
   das validações pós-LLM da seção 4.4.
2. `python -m hfpapers backfill --seed ./seed` popula o banco com **242 papers**
   (159 fora / 28 amplo / 55 estrito) e **83 fichas**, e é seguro rodar duas vezes:
   a segunda execução não altera nenhuma contagem nem gera chamada de LLM.
   Um teste deve verificar explicitamente que `2608.14577` está presente — é o id
   que só existe fora do `estado.json` e o primeiro a sumir se a união falhar.
3. `python -m hfpapers run` num dia já processado não cria linha nova em
   `fato_triagem` nem chama LLM — só acrescenta o snapshot de métricas do dia.
4. `python -m hfpapers run --dry-run` imprime a estimativa de custo sem gastar token.
5. `python -m hfpapers export` gera todos os Parquet da seção 8 e o `_manifest.json`.
6. Abrir os Parquet no Power BI, relacionar com `dim_calendario` e conseguir plotar:
   trajetória de upvotes de um paper ao longo dos dias; contagem de aprovados por
   área e por mês; taxa de FORA por dia; e a lista de fichas filtrada por tópico.
7. Um teste garante que **`upvotes` não aparece em nenhum prompt** enviado à LLM
   (seção 6.6). Faça-o de verdade: monte o payload e faça asserção sobre o texto.

---

## 14. Armadilhas — não faça

- **Não invente IDs de modelo do OpenRouter.** Consulte `/api/v1/models` e escreva no config.
- **Não use `upvotes` para classificar nem para ordenar o que entra.** Só para análise posterior.
- **Não use `publishedAt` do envelope externo** do `daily_papers` — tem deslocamento
  de fuso. Use `paper.publishedAt` e `paper.submittedOnDailyAt`.
- **Não grave id com sufixo de versão** em lugar nenhum.
- **Não deixe a LLM criar rótulo de área ou tópico livremente.** Enum injetado do banco.
- **Não decida o veredito antes de escrever o Padrão Extraído** no Estágio B.
- **Não regenere as classificações taxonômicas curadas** que vêm do `taxonomia.json`.
- **Não faça refresh paper a paper** quando refresh por data resolve — é ~45x mais requisições.
- **Não gere markdown de digest, consolidação semanal, HTML de painel nem e-mail.**
  Esse pipeline foi aposentado inteiro; semana é slicer de `dim_calendario`.
- **Não aborte a rodada inteira** por causa de um paper que falhou na LLM: registre e siga.

---

## 15. Por onde começar

Sugestão de ordem, cada passo entregando algo verificável:

1. Esqueleto + `config.py` + `db.py` + `schema.sql` + `doutor`.
2. `hf_client.py` + `coleta.py`, com fixtures. Ainda sem LLM: já dá para popular
   `dim_paper` e `fato_metrica` de um dia.
3. `refresh.py` + `export.py`. **Neste ponto já dá para abrir o Power BI** e validar
   o modelo estrela com dados reais, antes de gastar um centavo de LLM.
4. `llm/` + Estágio A. Rode com `--dry-run` primeiro.
5. Estágio B + validações da seção 4.4.
6. `taxonomia.py` (governança) + `guardrails.py`.
7. `backfill.py` + o relatório de validação.
8. `run_daily.ps1` + agendamento.

Comece pelo passo 1 e me mostre o esquema do banco criado antes de seguir para o 2.