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
  tetos da taxonomia e IDs dos modelos. A calibração de cada chave está em
  comentário no próprio arquivo; o porquê de `prazo_total_s`,
  `esforco_raciocinio` e da coluna `log_llm.provedor` está em
  `docs/adr/003-tres-chaves-do-openrouter.md`.

Os IDs de modelo do OpenRouter mudam com frequência. Consulte o catálogo antes
de escrever no `config.yaml`, e prefira modelos com mais de um provedor:

```bash
python -m hfpapers modelos listar --max-preco 1.0
python -m hfpapers modelos listar --contem claude
```

## Pipeline

Seis estágios, em ordem, com persistência incremental:

```
[1] COLETA         dias novos no HF → papers inéditos
[2] ENRIQUECIMENTO campos do endpoint por-paper
[3] CLASSIFICAÇÃO  Estágio A (barato) em todos; Estágio B (forte) nos sobreviventes
[4] REFRESH        métricas vivas de papers já na base
[5] DATAS_ARXIV    verifica a submissão v1 dos papers pendentes
[6] EXPORT         Parquet do Power BI em marts/
```

Falha no estágio 3 não corrompe o que o 1 gravou: a rodada fecha com
`status = 'parcial'`. Dias faltantes (feriado, máquina desligada) são
recuperados na mesma rodada. Dia antigo é `run --data AAAA-MM-DD`; não há
carga histórica especial. Paper que o HF acrescenta a um dia passado entra
pelo refresh e é classificado na rodada seguinte, por desenho.

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

`reclassificar --tudo` é operação manual, dura de duas a três horas com
`--concorrencia 4` e não entra no agendamento. Rode em terminal que sobreviva
(`nohup`, `tmux`) e não mate o processo: Ctrl+C só age quando as chamadas em
voo terminam. No fim, o comando imprime a lista de papers em que o Estágio B
falhou, pronta para `reclassificar --paper`. Depois: `doutor --sem-rede`,
`export` e `python scripts/gerar_painel.py --force`.

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

## Modelo de dados

Esquema estrela em `data/hfpapers.db` (DDL em `src/hfpapers/schema.sql`,
aplicado a cada conexão, tudo `IF NOT EXISTS`):

| Tabela | Papel |
|---|---|
| `dim_paper` | 1 linha por paper (id base, sem versão) |
| `fato_metrica` | 1 linha por paper por dia: upvotes, comentários, stars, artefatos |
| `fato_triagem` | veredito (`aprovado`/`fora`), `regra_fora`, natureza, pré-requisito, prática contradita, falta o como, status do artefato, `revisao`, `run_id` |
| `dim_ficha` | os campos da ficha, só para aprovados |
| `dim_natureza`, `dim_prerequisito` | vocabulário fixo dos dois eixos de um aprovado; `ordem` é a ordenação |
| `dim_perfil`, `ponte_perfil_prerequisito` | perfis de leitura, espelhados de `config.yaml` a cada conexão |
| `vw_artefato`, `vw_paper_perfil` | views: evidência e artefato aberto; "dá para agir" por perfil |
| `dim_area` | áreas e sub-áreas numa tabela: `area_pai` nulo é raiz |
| `dim_vertente` | eixo transversal: que movimento o paper faz |
| `tax_nao_encaixe` | fila de revisão da grade: paper, eixo, justificativa |
| `ponte_paper_*` | área (`is_primaria`), vertente (`ordem`), keyword, autor |
| `log_execucao`, `log_llm` | operação, tokens, custo e provedor do OpenRouter |
| `dim_calendario` | inteligência temporal do Power BI |

**Taxonomia facetada** (`docs/specs/taxonomia-facetada.md`): dois eixos
ortogonais. **Área** é hierárquica (raiz > sub-área); **vertente** é plana e
transversal (Medir, Treinar, Baratear, Endurecer, Confiabilizar, Automatizar,
Explicar, Especificar, Adaptar, Escalar). Cada paper recebe um par primário,
no máximo um secundário e uma ou duas vertentes ordenadas; os `fora` também.
A grade vigente (10 áreas, 64 sub-áreas, 10 vertentes) está em
`config/taxonomia_inicial.json`. A LLM nunca cria rótulo: quando nada serve,
declara o eixo que falhou e o paper vai para `tax_nao_encaixe`.

**Datas**: `data_hf_daily` (entrada no HF Daily), `data_arxiv_informada_hf`
(`publishedAt` do HF, pode ser revisão; `data_arxiv` é alias legado) e
`data_arxiv_v1` (submissão inicial verificada na API arXiv, nunca sobrescrita).
A defasagem auditada é `data_hf_daily - data_arxiv_v1`.

## Export para o Power BI

`export` escreve 17 Parquet em `marts/`, um por tabela ou view, com escrita
atômica, e apaga os de tabelas que saíram (`ponte_paper_criterio`).
`fato_triagem` sai com os booleanos já derivados (`contradiz_pratica`,
`como_incompleto`, `artefato_aberto`) e `ponte_paper_perfil` com o "dá para
agir" pronto, para o Power BI não reimplementar regra nenhuma.
Datas como `date32`, grão fino, sem pré-agregação. `marts/_manifest.json`
registra `run_id`, hora e contagem de linhas.

## Regras de classificação

Vivem em `prompts/`, versionadas: `regras_classificacao.md` (normas),
`estagio_a.md` (triagem barata + taxonomia) e `estagio_b.md` (natureza,
pré-requisito e ficha). O regime é o do ADR 004
(`docs/adr/004-natureza-e-prerequisito.md`; desenho em
`docs/specs/natureza-prerequisito.md`):

- todo `fora` tem exatamente uma `regra_fora`, a primeira que bate na ordem
  `geracao_de_midia`, `percepcao_robotica_embodied`, `fora_de_escopo`; treino e
  relatório técnico não são descarte;
- todo aprovado tem `natureza` (proposta, achado empírico, teoria, panorama) e
  `prerequisito` (nenhum < implementar < acesso interno < treino; sem ação);
  teoria e panorama são `sem_acao`, proposta nunca é;
- o perfil de leitura é um conjunto de degraus em `config.yaml`, fora do paper.

Validações em `llm/estagio_a.py` e `llm/estagio_b.py` rejeitam `fora` sem
regra, aprovado sem natureza ou ficha, natureza incoerente com o pré-requisito e
Padrão Extraído que cita o nome próprio dos autores; o paper fica pendente em
vez de gravado errado. Upvote não entra em decisão nenhuma nem em prompt.

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

Histórico das medições, calibração do OpenRouter e razões das decisões:
`docs/adr/`, `docs/relatorios/` e os comentários do `config.yaml`.