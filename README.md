# hf-papers-db

Camada de preparação de dados dos **Hugging Face Daily Papers**: coleta diária,
classificação por LLM em dois estágios, base SQLite e export em esquema estrela
para o Power BI. O Power BI é a interface de leitura; `relatorios/painel.html`
é a vitrine de distribuição.

## Instalação

Python 3.11+. Aqui o projeto roda no env conda `digest-hf`:

```bash
conda activate digest-hf            # ou: uv venv --python 3.12 && source .venv/bin/activate
uv pip install -e ".[dev]"
cp .env.example .env                # preencha OPENROUTER_API_KEY
python -m hfpapers doutor           # chave, API, banco e pendências
```

## Configuração

- `.env` — só segredos (`OPENROUTER_API_KEY`). Nunca é logado.
- `config.yaml` — todo o resto: caminhos, janelas de refresh, guardrails,
  tetos da taxonomia e IDs dos modelos.

Os IDs de modelo do OpenRouter mudam com frequência. Consulte o catálogo antes
de escrever no `config.yaml`, e prefira modelos com mais de um provedor:

```bash
python -m hfpapers modelos listar --max-preco 1.0
python -m hfpapers modelos listar --contem claude
```

## Comandos

```bash
python -m hfpapers run                          # pipeline completo do dia
python -m hfpapers run --data 2026-08-25        # força uma data
python -m hfpapers run --only coleta,export     # subconjunto de estágios
python -m hfpapers run --dry-run                # estima custo, não chama LLM
python -m hfpapers export                       # só exporta
python -m hfpapers reclassificar --data 2026-08-25 | --paper 2608.23552
python -m hfpapers reclassificar --tudo --concorrencia 4   # base inteira; teto 8
python -m hfpapers reclassificar --ids-arquivo ids.txt      # lista, um id por linha
python -m hfpapers reclassificar --tudo --retomar run-...   # continua a rodada que caiu
python -m hfpapers taxonomia listar | nao-encaixes | fundir | exportar | carregar
python -m hfpapers auditar-datas-arxiv [--aplicar] [--revalidar]
python -m hfpapers custos --mes 2026-08
python -m hfpapers doutor [--sem-rede]          # código 1 se houver erro
python -m hfpapers schema                       # DDL efetivo
```

## Agendamento (macOS, launchd)

Dois agentes em `~/Library/LaunchAgents/`:

- `com.samuelrochamotta.hfpapers-db` — `scripts/run_daily.sh`, todo dia às
  07:30. Log em `logs/run_*.log` (30 dias).
- `com.samuelrochamotta.hfpapers-painel` — `scripts/gerar_painel.sh`,
  disparado por `WatchPaths` em `marts/_manifest.json` (escrito por último no
  export), com rede de segurança às 08:30. Log em `logs/painel_*.log`.

```bash
launchctl print        gui/$(id -u)/com.samuelrochamotta.hfpapers-db
launchctl kickstart -k gui/$(id -u)/com.samuelrochamotta.hfpapers-db
tail -f logs/run_*.log
```

## Painel HTML

`scripts/gerar_painel.py` lê os Parquet e embute dados, `scripts/painel_app.js`
e CSS em um único HTML, sem dependência de rede. Três abas: **Aprovados**
(últimos 90 dias, um dia por página, ordenados por voto; colunas natureza,
título, marcas, área › sub-área e vertente; filtros de natureza, das marcas —
artefato aberto, contradiz prática, somente princípio —, área, vertente e busca
no texto da ficha), **Panorama** (lote diário por natureza, natureza ×
vertente, área por natureza, onde o pipeline corta, votos) e **Registro
histórico** (por trimestre já fora da janela, os 15 aprovados mais votados e os
5 descartados mais votados como auditoria). O pré-requisito, os perfis e o
Padrão Extraído continuam no banco e no Power BI, mas não aparecem no painel. O
corte do histórico é `refresh.janela_morna_dias`, não `--dias`.

```bash
python scripts/gerar_painel.py --force                         # após editar JS/CSS
python scripts/gerar_painel.py --dias 10 --force --destino /tmp/previa.html   # prévia
```

`gerar_painel.sh` faz commit e push de `relatorios/painel.html` para
`origin main` quando o HTML mudou e nenhuma opção de prévia (`--dias`,
`--dias-hall`, `--destino`) foi passada. O `.py` sai em no-op se o `run_id`
não mudou desde a última geração (`marts/.painel_run_id`).

## Testes

```bash
python -m pytest -q     # sem rede: fixtures em tests/fixtures/, transporte via respx
```

## Estrutura

```
src/hfpapers/
├── __main__.py         CLI (typer)
├── config.py           config.yaml + .env
├── db.py               conexão, migração, upserts, calendário
├── schema.sql
├── execucao.py         orquestra os 6 estágios e a reclassificação
├── auditoria_arxiv.py  verificação de v1 e relatórios de divergência
├── taxonomia.py        validação da grade, não-encaixes, fusão, export/carga
├── guardrails.py       avisos de volume
├── doutor.py           diagnóstico
├── log.py              logging com corte de segredo
├── fontes/             clientes HF/arXiv e catálogo de modelos
├── llm/                cliente OpenRouter, schemas, estágios A e B
└── estagios/           coleta, enriquecimento, classificação, refresh, export
scripts/
├── run_daily.sh        pipeline diário (launchd)
├── gerar_painel.sh     wrapper do painel (launchd)
├── gerar_painel.py     monta relatorios/painel.html a partir dos Parquet
├── painel_app.js       app do painel
├── coleta_retroativa.py  varre dias anteriores ao início do pipeline (sem LLM)
└── relatorio_massa.py    mede a grade: distribuição, checagens, roteamento
prompts/            regras versionadas
config/             taxonomia_inicial.json
docs/adr/           decisões, uma por arquivo
docs/specs/         desenhos entregues
docs/relatorios/    medições da base, uma por rodada (versionadas)
marts/              Parquet — o Power BI aponta para cá (não versionado)
relatorios/         painel.html (versionado); o resto não
data/               o banco SQLite — a fonte (não versionado)
```