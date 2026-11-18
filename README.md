# hf-papers-db

Camada de preparação de dados dos **Hugging Face Daily Papers**: coleta diária,
classificação por LLM em dois estágios, base SQLite e export em esquema estrela
em Parquet. A interface de leitura é o painel feito por código,
`relatorios/painel/` (site estático no GitHub Pages), gerado de `marts/` por
`scripts/gerar_painel.py`.

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

Um site estático, sem servidor, publicado no GitHub Pages. `scripts/gerar_painel.py`
lê os Parquet e grava `relatorios/painel/`:

| arquivo | o que é |
|---|---|
| `index.html` | a página, com o CSS, o app (`scripts/painel_app.js`) e um resumo em texto para buscador e prévia de link |
| `dados.json` | o que a primeira pintura precisa: papers da janela, vocabulário, registro histórico e os votos já pré-agregados |
| `fichas.json` | o texto das fichas, buscado depois da primeira pintura (é a maior parte do peso) |
| `echarts.painel.min.js` | Apache ECharts só com os módulos usados (build em `scripts/echarts/`) |

Três abas: **Aprovados** (últimos 90 dias, um dia por página, ordenados por voto;
colunas natureza, título, marcas, área › sub-área e vertente; filtros de
natureza, das marcas — artefato aberto, contradiz prática, somente princípio —,
área, vertente e busca no texto da ficha), **Panorama** (lote diário por
natureza, natureza × vertente, área por natureza ou por sub-área, onde o
pipeline corta, votos) e **Registro histórico** (por trimestre já fora da janela,
os 15 aprovados mais votados e os 5 descartados mais votados como auditoria).

Os gráficos do Panorama são **interligados**: clicar num dia, numa célula da
matriz, numa área, sub-área ou regra recorta o painel inteiro, como as pílulas.
O recorte fica no endereço (`#aba=panorama&area=...`), então um link abre a mesma
visão; o botão *copiar link* copia esse endereço, e `#paper=<id>` abre direto
um card. Cada gráfico tem título, um resumo em texto do que mostra (também
usado como descrição acessível) e a tabela dos números. A paleta das naturezas
é segura para daltonismo (validada com o cinza do `fora`, todos os pares). O
layout se ajusta ao celular.

O pré-requisito, os perfis e o Padrão Extraído continuam no banco, mas não
aparecem no painel (os perfis não são mais exportados; ADR 005). O corte do
histórico é `refresh.janela_morna_dias`, não `--dias`.

```bash
python scripts/gerar_painel.py --force                         # após editar JS/CSS
python scripts/gerar_painel.py --dias 10 --force --destino /tmp/previa.html   # prévia
python -m http.server -d relatorios/painel 8000                # ver o site local
```

`--destino` terminado em `.html` gera um **arquivo único** com dados, fichas e
ECharts embutidos, que abre offline (prévia, e-mail). Sem `.html`, é a pasta.

`gerar_painel.sh` primeiro alinha a `main` local com `origin/main`
(`pull --rebase`), para o painel sair do código que está no GitHub. Depois,
faz commit só de `relatorios/painel/` e dá push para `origin main`, desde que
quatro condições valham:
- algo mudou;
- o checkout está em `main`;
- não há mudança rastreada fora do painel (trabalho em andamento);
- nenhuma opção de prévia (`--dias`, `--dias-hall`, `--destino`) foi passada.

Quando alguma dessas condições falha, a rodada não publica e deixa um `AVISO`
no log.

O push dispara o deploy do Pages. Se ele falhar, o script desfaz o commit do
painel, descarta o painel e apaga o carimbo de `run_id`, e a rodada seguinte
refaz o painel do zero. Fora isso, o `.py` sai em no-op se o `run_id` não
mudou desde a última geração (`marts/.painel_run_id`).

## Painel v2 (em construção)

Classifica os papers pelo que eles provam, lido do **texto completo** pelo
Claude Haiku 5.5 (ADR 007, especificação em `docs/specs/painel-v2.md`). Nasce
ao lado do v1, em `relatorios/painel-v2/`, publicado em `/v2/` no Pages.

```bash
hfpapers ler --dias 7 --limite 30                 # Haiku 5.5 pelo OpenRouter (mesma chave)
python scripts/gerar_painel_v2.py --dias 14       # grava relatorios/painel-v2/dados.json
cd painel-v2 && npm ci && npm run build           # só quando o front-end muda
```

O front-end é Svelte 5 + Apache ECharts 6 (`painel-v2/`). O build fica
versionado com nomes fixos, então a rodada diária só troca o `dados.json`.

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
├── gerar_painel.py     monta relatorios/painel/ a partir dos Parquet
├── painel_app.js       app do painel (gráficos em ECharts)
├── echarts/            build do ECharts só com os módulos usados
├── vendor/             saída desse build (versionada)
├── coleta_retroativa.py  varre dias anteriores ao início do pipeline (sem LLM)
└── relatorio_massa.py    mede a grade: distribuição, checagens, roteamento
prompts/            regras versionadas
config/             taxonomia_inicial.json
docs/adr/           decisões, uma por arquivo
docs/specs/         desenhos entregues
docs/relatorios/    medições da base, uma por rodada (versionadas)
marts/              Parquet — o painel lê daqui (não versionado)
relatorios/         painel/ (versionado, é o site); o resto não
data/               o banco SQLite — a fonte (não versionado)
```