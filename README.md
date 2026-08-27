# hf-papers-db

Camada de preparação de dados dos **Hugging Face Daily Papers**: coleta diária,
classificação por LLM, base SQLite viva e export em formato estrela para o Power BI.

Não gera digest em markdown, consolidação semanal, painel HTML nem e-mail — o
Power BI é a única interface de leitura. Semana é atributo de `dim_calendario`
(`ano_semana_iso`), então "os aprovados da semana 34" é um filtro, não um arquivo.

## Instalação

Python 3.11+. Neste ambiente o projeto está instalado no env conda `digest-hf`
(Python 3.13):

```bash
conda activate digest-hf
uv pip install -e ".[dev]"
cp .env.example .env             # e preencha OPENROUTER_API_KEY
```

Sem conda, um venv serve igual:

```bash
uv venv --python 3.12 && source .venv/bin/activate
uv pip install -e ".[dev]"
```

Confira tudo com `python -m hfpapers doutor`.

## Configuração

- `.env` — só segredos (`OPENROUTER_API_KEY`). Está no `.gitignore`, nunca é
  logado (o handler de log corta qualquer coisa com cara de chave).
- `config.yaml` — todo o resto: caminhos, janelas de refresh, guardrails, tetos
  da taxonomia e os IDs dos modelos.

**Os IDs de modelo do OpenRouter não são chutados.** Eles mudam com frequência;
consulte o catálogo vivo e escreva a escolha no `config.yaml`:

```bash
python -m hfpapers modelos listar --max-preco 1.0
python -m hfpapers modelos listar --contem claude
```

O filtro já mostra só modelos com saída estruturada (`response_format` /
`structured_outputs`), que é do que os dois estágios dependem.

## Pipeline

Cinco estágios, em sequência, cada um idempotente e com transação própria:

```
[1] COLETA        → busca dias novos no HF, insere papers inéditos
[2] ENRIQUECIMENTO→ para papers inéditos, busca campos do endpoint por-paper
[3] CLASSIFICAÇÃO → Estágio A (barato) em todos; Estágio B (forte) nos sobreviventes
[4] REFRESH       → re-consulta métricas vivas de papers já na base
[5] EXPORT        → materializa os Parquet do Power BI
```

Falha no estágio 3 não corrompe o que o 1 gravou: a rodada termina com
`status = 'parcial'` e os avisos dizem onde doeu.

## Comandos

```bash
python -m hfpapers run                        # pipeline completo do dia
python -m hfpapers run --data 2026-08-25      # força uma data
python -m hfpapers run --only coleta,export   # subconjunto de estágios
python -m hfpapers run --dry-run              # estima custo, não chama LLM
python -m hfpapers backfill --seed ./seed     # carga histórica (idempotente)
python -m hfpapers backfill --seed ./seed --pular-llm
python -m hfpapers export
python -m hfpapers reclassificar --data 2026-08-25 [--paper 2608.23552]
python -m hfpapers taxonomia listar
python -m hfpapers taxonomia fundir --de "X" --para "Y" --tipo topico
python -m hfpapers modelos listar
python -m hfpapers custos --mes 2026-08       # quanto a LLM custou
python -m hfpapers doutor [--sem-rede]        # chave ok? API ok? banco íntegro?
python -m hfpapers schema                     # DDL efetivo do banco
```

### Recuperação de lacuna

`run` compara `MAX(data_hf_daily)` com hoje. Se houver mais de um dia de
publicação em aberto (feriado, falha, máquina desligada), coleta **todos** os
dias faltantes na mesma rodada e registra `lacuna_recuperada: [datas]` nos avisos.
Fim de semana vazio é normal e não é erro.

## Agendamento (Windows)

`scripts/run_daily.ps1` ativa o Python do projeto, roda `run`, escreve um log
rotativo em `logs/` e propaga o código de saída — código != 0 faz o Agendador
marcar a execução como falha.

Registrar a tarefa diária (07:30, depois de o HF ter publicado o dia anterior):

```powershell
schtasks /Create `
  /TN "hf-papers-db diario" `
  /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\caminho\hf-papers-db\scripts\run_daily.ps1" `
  /SC DAILY /ST 07:30 /RL LIMITED /F
```

Conferir e rodar na mão:

```powershell
schtasks /Query /TN "hf-papers-db diario" /V /FO LIST
schtasks /Run   /TN "hf-papers-db diario"
```

## Modelo de dados

Esquema estrela em `data/hfpapers.db` (DDL em `src/hfpapers/schema.sql`, aplicado
a cada abertura de conexão — tudo `IF NOT EXISTS`):

| Tabela | Papel |
|---|---|
| `dim_paper` | dimensão principal, 1 linha por paper (id base, sem sufixo de versão) |
| `fato_metrica` | série temporal: 1 linha por paper por dia (upvotes, comentários, stars, artefatos) |
| `fato_triagem` | veredito (`fora`/`amplo`/`estrito`) + teste de portabilidade |
| `dim_ficha` | os cinco campos da ficha, só para aprovados |
| `dim_area`, `dim_topico`, `tax_candidato` | vocabulário controlado e candidatos |
| `ponte_paper_*` | área, tópico, keyword, autor (muitos-para-muitos) |
| `log_execucao`, `log_llm` | operação, tokens e custo |
| `dim_calendario` | inteligência temporal do Power BI |

Duas datas, separadas de propósito: `data_arxiv` (`paper.publishedAt`) e
`data_hf_daily` (`paper.submittedOnDailyAt`). Elas divergem em 35 de 35 papers no
lote de 25/08 — a operação diária é organizada pela segunda.

## Refresh escalonado

Re-consultar `daily_papers?date=` de uma data antiga devolve as métricas
**atuais**, não congeladas. Por isso o refresh é por data, não por paper: ~22
requisições/dia para uma janela quente de 30 dias, em vez de ~1.000.

- janela quente (30 dias): todo dia
- janela morna (90 dias): segunda-feira
- acima de 90 dias: congelado
- `numTotal*` (modelos/datasets/spaces): semanal, via `papers/{id}`

## Export para o Power BI

`python -m hfpapers export` escreve em `marts/`, um Parquet por tabela, com
escrita atômica (`os.replace`) — pode rodar com o Power BI aberto.

- datas como `date32`, não string;
- grão fino, sem pré-agregação (a agregação é papel do DAX);
- `fato_metrica` traz `upvotes_delta_dia` e propaga `qtd_modelos/datasets/spaces`
  para frente com o último valor não nulo;
- `dim_paper` traz `dias_desde_publicacao`, `tem_codigo_aberto`,
  `tem_project_page`, `faixa_upvotes_atual`, `upvotes_atual`;
- `marts/_manifest.json` registra data/hora, `run_id` e a contagem de linhas de
  cada arquivo — é como conferir no Power BI que o dado é fresco.

No Power BI Desktop: Obter Dados → Parquet, apontar para `marts/`. Marcar
`dim_calendario` como tabela de datas e relacionar
`fato_metrica[data_snapshot] → dim_calendario[data]` e
`fato_metrica[paper_id] → dim_paper[paper_id]`.

## Regras de classificação

As regras vivem em `prompts/`, versionadas — não embutidas em f-strings:

- `prompts/regras_classificacao.md` — as regras normativas (FORA, teste de
  portabilidade, estrito vs amplo, os cinco campos da ficha, guardrails);
- `prompts/estagio_a.md` — triagem barata + classificação taxonômica, com o
  vocabulário injetado do banco;
- `prompts/estagio_b.md` — portabilidade, veredito e ficha.

Três invariantes que os testes cobrem:

1. **Upvote não entra em decisão nenhuma** e não aparece em prompt nenhum. É
   métrica de saída, guardada em `fato_metrica` para você descobrir depois se
   prediz aprovação.
2. **O Padrão Extraído é escrito e testado antes do veredito.** A ordem das
   propriedades no schema do Estágio B é normativa.
3. **A LLM não cria rótulo de área ou tópico.** O enum é injetado do banco;
   rótulo novo vira candidato em `tax_candidato` e só é promovido com 2 papers
   distintos e folga no teto.

## Backfill

`python -m hfpapers backfill --seed ./seed` (idempotente; a segunda execução não
altera contagem nem chama LLM).

A lista de trabalho é a **união de três fontes** — `hf-digest-estado.json`,
`taxonomia.json > classificacoes` e os ids das fichas dos 8 digests. Só o estado
produziria 241 papers e 82 fichas, e estaria errado: `2608.14577` tem ficha e
classificação mas sumiu do estado. Resultado correto: **242 papers, 83 aprovados**,
taxa de FORA histórica de 66%.

Ao final, `relatorios/validacao_backfill.md` compara as fichas regeneradas com as
83 históricas (mesmo veredito? mesma presença de Padrão Extraído? mesmo nome?).
O relatório não corrige nada — é o instrumento para julgar se o prompt novo
reproduz a qualidade do antigo.

O veredito histórico não é reaberto pelo backfill: ele fica em `fato_triagem` como
registro. O veredito que o Estágio B devolve na regeneração vai para
`relatorios/vereditos_estagio_b.json`, e é dele que sai a comparação — sem esse
registro o relatório compararia o histórico contra ele mesmo e daria sempre 100%
de concordância.

## Testes

```bash
python -m pytest -q
```

Sem rede: as respostas reais do HF estão gravadas em `tests/fixtures/` e o
transporte é interceptado com `respx`.

## Estrutura

```
src/hfpapers/
├── __main__.py     CLI (typer)
├── config.py       config.yaml + .env
├── db.py           conexão, migração, upserts idempotentes, calendário
├── schema.sql
├── execucao.py     orquestra os 5 estágios e grava log_execucao
├── backfill.py     carga histórica a partir de seed/
├── digests.py      parser dos digests históricos (conjunto de validação)
├── taxonomia.py    governança do vocabulário, promoção e fusão
├── guardrails.py   avisos de volume
├── doutor.py       diagnóstico
├── fontes/         hf_client.py (httpx, retry, rate limit) + modelos.py (pydantic)
├── llm/            cliente OpenRouter, schemas, estágios A e B
└── estagios/       coleta, enriquecimento, classificação, refresh, export
prompts/            regras versionadas
seed/               insumos do backfill
marts/              ← o Power BI aponta para cá
```
