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
python -m hfpapers doutor [--sem-rede]        # chave, API, banco e pendências de triagem
python -m hfpapers schema                     # DDL efetivo do banco
```

### Papers que chegam pelo refresh

O HF acrescenta paper ao daily de um dia **já passado**. Quem os encontra é o
refresh, que reconsulta as datas quentes e grava pelo mesmo caminho da coleta
(`refresh.py` → `coleta.gravar_itens`). Como o refresh é o estágio 4 e a
classificação é o 3, esse paper nasce depois da classificação da rodada que o
descobriu: entra na base sem veredito e só é classificado no dia seguinte —
a rodada seguinte varre **todo** pendente de qualquer dia, porque
`classificacao.selecionar` só filtra por data quando alguém passa `--data`.

É latência de um dia por desenho, não falha. Em 2026-09-03 eram 9 papers de
455 (2%), todos com `primeiro_visto_em` idêntico ao instante do refresh.
O mesmo vale para `enriquecido_em`: o enriquecimento também é anterior ao
refresh, e só alcança esses papers na segunda-feira, via
`refresh.enriquecimento_semanal`.

O que o `doutor` vigia é a diferença entre **esperar** e **falhar**:

| situação | estado | leitura |
|---|---|---|
| pendente visto depois da última classificação | `ok` | está na fila, entra amanhã |
| pendente que atravessou uma rodada de classificação | `aviso` | a repescagem teve chance e não pegou |

O corte é a última execução que classificou alguém — uma que não classificou
nada pode nem ter rodado o estágio 3 (`--only export`), e uma morta no meio
(`finalizado_em` nulo, como em 02/09) não prova chance nenhuma. O remédio que
o aviso imprime é `run --only classificacao,export`.

### Recuperação de lacuna

`run` compara `MAX(data_hf_daily)` com hoje. Se houver mais de um dia de
publicação em aberto (feriado, falha, máquina desligada), coleta **todos** os
dias faltantes na mesma rodada e registra `lacuna_recuperada: [datas]` nos avisos.
Fim de semana vazio é normal e não é erro.

## Agendamento (macOS, launchd)

`scripts/run_daily.sh` ativa o Python do projeto, roda `run`, escreve um log
rotativo em `logs/run_*.log` (30 dias) e propaga o código de saída.

O agente está registrado em `~/Library/LaunchAgents/com.samuelrochamotta.hfpapers-db.plist`,
rodando todo dia às 07:30 (depois de o HF ter publicado o dia anterior).
`RunAtLoad` é `false` — não dispara no login, só no horário marcado; se o Mac
estava desligado/dormindo às 07:30, o launchd roda assim que possível ao acordar,
e o próprio pipeline recupera os dias que ficaram faltando na mesma rodada.

Comandos úteis:

```bash
# status do agente (state, last exit status)
launchctl print gui/$(id -u)/com.samuelrochamotta.hfpapers-db

# rodar agora, fora do horário
launchctl kickstart -k gui/$(id -u)/com.samuelrochamotta.hfpapers-db

# desativar/reativar sem apagar o registro
launchctl bootout  gui/$(id -u) ~/Library/LaunchAgents/com.samuelrochamotta.hfpapers-db.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.samuelrochamotta.hfpapers-db.plist

# acompanhar a execução mais recente
tail -f logs/run_*.log
```

`logs/launchd.out.log` e `logs/launchd.err.log` só capturam problema do próprio
agendamento (script não encontrado, permissão); a saída real do pipeline vai
para `logs/run_*.log`.

## Painel HTML de distribuição

Segundo agente, separado do primeiro: `com.samuelrochamotta.hfpapers-painel`.
Gera `relatorios/painel.html` — arquivo único, sem dependência de rede, que abre
em qualquer visualizador de HTML (Teams, e-mail, navegador).

Não substitui o Power BI, que continua sendo a interface de leitura. O painel é
a vitrine para quem não vai abrir o Power BI.

O desenho é o do Artifact **Painel Daily Papers**, que nasceu como artboard da
Claude Design. Aquele arquivo só roda dentro do runtime do canvas;
`scripts/painel_app.js` é o mesmo layout portado para JS de navegador — cinco
seções (volume, vocabulário, votos, adoção, fichas), filtro cruzado por dia,
veredito, área, tópico e organização. `gerar_painel.py` não desenha nada:
extrai os dados de `marts/`, serializa em `DADOS` e embute o app.

**O gatilho é dependência real, não horário chutado.** O estágio de export
escreve `marts/_manifest.json` por último e de forma atômica (`os.replace`),
depois dos 12 Parquet — então a mudança desse arquivo *é* o sinal de "pipeline
terminou". O plist usa `WatchPaths` nele; medido, dispara ~1s após o export.

Três defesas contra o disparo repetido ou perdido:

- `gerar_painel.py` grava o `run_id` gerado em `marts/.painel_run_id` e sai em
  no-op se o `run_id` não mudou — `WatchPaths` pode disparar mais de uma vez
  para a mesma escrita;
- `ThrottleInterval` de 60s segura rajada;
- `StartCalendarInterval` às 08:30 é rede de segurança para o caso de o
  `WatchPaths` perder a notificação do `os.replace` (troca de inode). Se o
  gatilho já pegou, essa execução sai em no-op pela trava de `run_id`.

### As duas abas

**Janela** — os últimos 90 dias (`--dias N` muda), com o filtro cruzado e as
cinco seções. Sem recorte o arquivo cresceria para sempre: entram ~28 papers/dia.

**Registro histórico** — de cada trimestre já fora da janela, os **10 aprovados
mais votados** com a ficha inteira e os **10 descartados mais votados** com a
regra e a justificativa que os tiraram. A série completa continua nos Parquet e
no banco; o painel mostra a janela mais esse resumo.

Paper sem linha em `fato_triagem` (o Estágio A falhou nele) não é o mesmo que
descartado: fica fora das duas listas e das duas contagens, e aparece só como
`nx` no subtítulo da segunda seção. Entrasse como `fora`, apareceria no pódio
dos descartados com o campo da justificativa em branco.

Três coisas que essa aba **não** é, e vale ter escrito:

- **Não preserva dado contra perda.** Nada é apagado — nem do banco, nem dos
  Parquet. A janela de 90 dias sempre foi recorte de renderização, não deleção.
  O que a aba resolve é visibilidade: impedir que o recorte esconda para sempre
  o que a comunidade mais votou.
- **Não precisa de deduplicação.** `data_hf_daily` é imutável, então cada paper
  pertence a exatamente um trimestre, para sempre. Não há chave de dedupe nem
  reconciliação entre períodos.
- **Não precisa de "selagem".** O ranking de um trimestre congela sozinho:
  quando o último dia dele cruza o corte, nem entram papers novos no grupo nem
  os votos se mexem — o refresh para de reconsultá-los na mesma marca de dias.
  Até lá o trimestre aparece marcado como *em consolidação*.

Por isso ela é derivada dos Parquet a cada geração: sem tabela nova, sem estado
em `data/estado/`, sem estágio novo no pipeline, sem chamada de LLM e sem
requisição ao HF.

O corte da aba histórica vem de `refresh.janela_morna_dias`, **não** de `--dias`.
É o ponto em que o pipeline para de atualizar os votos, então é onde um ranking
pode congelar sem mentir. A consequência prática: `--dias` continua sendo a
válvula para encolher o arquivo — baixar o valor mostra menos, não empurra
papers para o histórico.

Congelar aos 90 dias não perde quase nada, e isso foi medido em `fato_metrica`
(idade contada a partir de `data_hf_daily`, não do índice do snapshot — os
snapshots não começam no dia da publicação):

| corte | mediana upvote/final | ainda crescem >10% depois |
|---|---|---|
| dia +2 | 0,89 | 58,6% |
| dia +5 | 0,96 | 41,0% |
| dia +7 | 1,00 | 26,5% |
| dia +10 | 1,00 | 7,6% |
| dia +14 | 1,00 | 0,7% |
| dia +18 | 1,00 | 0,0% |

A mediana atinge o valor final **no dia +6** e o movimento residual acaba por
volta do **dia +14** — tudo dentro da janela quente de 30 dias, com folga de ~6x
até o corte de 90 dias. O maior salto tardio observado foi 286 → 339 votos.

### Tamanho

O peso vem do texto das fichas embutido em `DADOS`, não de HTML por card.
Medido: **681 KB para 455 papers e 155 fichas**, dos quais 322 KB são fichas
(~2,1 KB cada) e 196 KB são os papers (~440 B cada).

O custo por entrada do histórico é assimétrico de propósito — é o que permite as
duas listas terem tamanhos diferentes:

| Lista | Conteúdo | Por entrada | Por trimestre |
|---|---|---|---|
| 10 aprovados | ficha inteira (5 campos) | ~2,3 KB | ~23 KB |
| 10 descartados | regra + justificativa | ~0,4 KB | ~4 KB |

**~27 KB por trimestre, ~110 KB por ano** — contra os **~860 KB/mês** que a
janela viva acumularia se não fosse recortada (os 455 papers de 21 dias corridos
pesam 603 KB de payload). Se doer, `--dias` é o botão para girar.

Vale lembrar que `painel.html` é commitado e empurrado todo dia (168 KB
comprimido, ~60 MB/ano de repositório): cada KB adicionado se multiplica por 365.
Por isso o ranking desempata por `paper_id` — sem critério estável, dois papers
empatados em votos trocariam de lugar entre rodadas e o commit diário ganharia
diff sem significado.

```bash
# gerar na mão
scripts/gerar_painel.sh                 # janela padrão (90 dias)
scripts/gerar_painel.sh --force         # ignora a trava de run_id

# inspecionar a aba histórica antes de o primeiro trimestre fechar.
# SEMPRE com --destino: o painel publicado não é rascunho.
scripts/gerar_painel.sh --dias 10 --dias-hall 10 --force --destino /tmp/previa.html

# status / disparo manual do agente
launchctl print    gui/$(id -u)/com.samuelrochamotta.hfpapers-painel
launchctl kickstart -k gui/$(id -u)/com.samuelrochamotta.hfpapers-painel
```

Duas defesas contra publicar rascunho por engano, porque `--dias` e `--dias-hall`
mudam **o que** o painel mostra (com `--dias 10` são 270 papers em vez de 455, e
os 185 que sobram não aparecem em aba nenhuma):

- `gerar_painel.sh` não commita nem empurra quando recebe `--dias`, `--dias-hall`
  ou `--destino` — só a geração diária, sem argumentos, publica;
- `gerar_painel.py` só carimba `marts/.painel_run_id` quando escreveu no destino
  padrão. Sem isso, uma prévia em `/tmp` deixaria a geração seguinte do painel de
  verdade saindo em no-op, e nem a rede de segurança das 08:30 desfaria.

Log em `logs/painel_*.log` (rotação de 30 dias, igual ao pipeline).

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

`janela_morna_dias` tem um segundo consumidor: é o corte da aba histórica do
painel. Mexer nele move as duas coisas junto, e isso é de propósito — o
histórico congela ranking exatamente onde o refresh para de atualizar voto.

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
   prediz aprovação. A aba histórica do painel ordena por upvote, mas isso é
   exibição, não decisão: o veredito já foi dado e não é reaberto. A lista de
   descartados existe justamente para medir a divergência — no lote atual, 14
   dos 20 papers mais votados são `fora`.
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
`data/estado/vereditos_estagio_b.json`, e é dele que sai a comparação — sem esse
registro o relatório compararia o histórico contra ele mesmo e daria sempre 100%
de concordância.

Por isso ele mora em `data/estado/` e não em `relatorios/`: é **entrada** de uma
etapa seguinte, não artefato de leitura. Apagar `relatorios/` é inócuo (regenera);
apagar `data/estado/` não quebra o relatório — faz ele mentir.

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
├── digests.py      parser dos digests históricos (conjunto de validação)
├── taxonomia.py    governança do vocabulário, promoção e fusão
├── guardrails.py   avisos de volume
├── doutor.py       diagnóstico
├── backfill/       carga histórica a partir de seed/ — um módulo por etapa
│   ├── __init__.py     rodar(): a única coisa que conhece a ordem das etapas
│   ├── tipos.py        ResultadoBackfill, ItemTrabalho, RUN_ID
│   ├── lista.py        a união das três fontes do seed
│   ├── hidratacao.py   busca cada paper no HF
│   ├── importacao.py   triagem histórica + as 83 classificações curadas
│   ├── regeneracao.py  Estágios A e B pelo pipeline novo + vereditos regenerados
│   └── validacao.py    monta relatorios/validacao_backfill.md
├── fontes/         hf_client.py (httpx, retry, rate limit) + modelos.py (pydantic)
├── llm/            cliente OpenRouter, schemas, estágios A e B
└── estagios/       coleta, enriquecimento, classificação, refresh, export
scripts/
├── run_daily.sh        pipeline diário (launchd, 07:30)
├── gerar_painel.sh     wrapper do painel (launchd, WatchPaths em _manifest.json)
├── gerar_painel.py     monta relatorios/painel.html a partir dos Parquet
└── painel_app.js       app do painel (porte do artboard da Claude Design)
prompts/            regras versionadas
seed/               insumos do backfill + conjunto de validação (versionado)
marts/              ← o Power BI aponta para cá
relatorios/         artefatos de leitura: painel.html, validacao_backfill.md
data/               banco + estado/ (cache dos vereditos regenerados)
```

`relatorios/`, `marts/`, `data/` e `logs/` não são versionados. A diferença entre
eles: `relatorios/` e `marts/` regeneram do banco; `data/` **é** a fonte.
