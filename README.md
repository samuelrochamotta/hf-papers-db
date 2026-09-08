# hf-papers-db

Camada de preparação de dados dos **Hugging Face Daily Papers**: coleta diária,
classificação por LLM, base SQLite viva e export em formato estrela para o Power BI.

Não gera digest em markdown, consolidação semanal nem e-mail — o Power BI é a
interface de leitura (o painel HTML é vitrine de distribuição, não substituto).
Semana é atributo de `dim_calendario` (`ano_semana_iso`), então "os aprovados da
semana 34" é um filtro, não um arquivo.

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

**Dia antigo é `run --data`.** Não existe carga histórica, comando especial nem
diretório de insumo: `daily_papers?date=` devolve qualquer data passada, e a
coleta trata 14/08 igual a ontem. Um dia que ficou de fora entra com
`python -m hfpapers run --data 2026-08-14`, pelos mesmos cinco estágios e com o
mesmo veredito que qualquer outro paper receberia. O único dado que já veio de
fora do pipeline é o vocabulário controlado, e ele hoje mora em
`config/taxonomia_inicial.json` (`taxonomia exportar|carregar`).

## Comandos

```bash
python -m hfpapers run                        # pipeline completo do dia
python -m hfpapers run --data 2026-08-25      # força uma data
python -m hfpapers run --only coleta,export   # subconjunto de estágios
python -m hfpapers run --dry-run              # estima custo, não chama LLM
python -m hfpapers run --force                # reclassifica quem já tem triagem
python -m hfpapers export
python -m hfpapers reclassificar --data 2026-08-25
python -m hfpapers reclassificar --paper 2608.23552
python -m hfpapers reclassificar --tudo                    # a base inteira, horas
python -m hfpapers reclassificar --tudo --concorrencia 4   # 1 = sequencial, teto 8
python -m hfpapers taxonomia listar
python -m hfpapers taxonomia nao-encaixes [--eixo area|subarea|vertente]
python -m hfpapers taxonomia fundir --de "X" --para "Y" --tipo topico
python -m hfpapers taxonomia exportar [--destino config/taxonomia_inicial.json]
python -m hfpapers taxonomia carregar [config/taxonomia_inicial.json]
python -m hfpapers modelos listar
python -m hfpapers custos --mes 2026-08       # quanto a LLM custou
python -m hfpapers doutor [--sem-rede]        # chave, API, banco e pendências de triagem
python -m hfpapers schema                     # DDL efetivo do banco
```

`reclassificar` roda só o estágio 3 sobre papers já vistos, incrementando
`revisao`. `--tudo` é exclusivo com `--data`/`--paper` — ou se varre a base
inteira, ou se dirige a varredura — e nos três modos a rodada entra em
`log_execucao`: rodada dirigida deixou de ser invisível para o `doutor` e para a
trava de `run_id` do painel. Quando o Estágio B cai nas duas passadas de um
paper, o comando imprime no fim a lista de `reclassificar --paper <id>` pronta
para colar.

`--concorrencia` mora no `reclassificar` e não no `run` de propósito: quem passa
horas em chamada sequencial é a varredura da base inteira; a rodada diária são
~30 papers e segue `llm.concorrencia` do `config.yaml` (padrão 1). O paralelismo
é só do I/O do OpenRouter — toda escrita no banco continua na thread principal e
na ordem original dos papers, então `--concorrencia 4` termina com o banco
idêntico ao de `--concorrencia 1` **na rodada que completa**. Valor fora da faixa
1–8 é cortado com aviso, não recusado (o porquê do teto está no
`docs/adr-001-fora-de-escopo-do-mapa.md`).

A ressalva importa porque a rodada total dura horas e pode cair no meio: **a
varredura que estoura não é equivalente**. Os workers vão adiante da thread
principal, então ficam papers já pagos que nunca chegam a ter triagem — medido
com `--concorrencia 4`, 2 triagens gravadas contra 10 papers já em `log_llm`.
Nenhuma linha se perde: o gasto desses papers está em `log_llm` e aparece em
`hfpapers custos`, mas fica **fora** de `log_execucao.custo_usd`, que conta só o
que virou triagem. Com `--concorrencia 1` nada é chamado adiante do paper que
estoura.

`taxonomia exportar` grava áreas e tópicos do banco (rótulo + definição, sem a
fila de revisão) no JSON versionado; `carregar` é o inverso, para banco vazio, e
é idempotente — rótulo que já existe não é tocado. `taxonomia nao-encaixes` lê a
fila de revisão da grade: os papers em que o Estágio A declarou que nenhuma
célula servia, com o eixo que falhou (`area`, `subarea` ou `vertente`) e a
justificativa. **Ninguém promove rótulo a partir dela dentro do pipeline**: a
classificação nunca cria vocabulário, e a promoção é da revisão da grade, por
quórum.

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
(`finalizado_em` nulo, como em 02/09) não prova chance nenhuma. O **instante**
do corte é o fim do estágio 3 dessa execução (o último `classificado_em` que
ela gravou), não o `finalizado_em`: este é carimbado depois do refresh, e o
refresh é justamente quem grava o paper novo — em 04/09 os 5 pendentes nasceram
4 s depois da última triagem e 29 s antes do fim da rodada. O remédio que o
aviso imprime é `run --only classificacao,export`.

Toda execução conta, sem lista de exceção. Não existe mais rodada dirigida
invisível: `reclassificar` (com `--data`, `--paper` ou `--tudo`) abre e fecha
linha em `log_execucao` como o `run`, e o que ela registra são as triagens que
ela própria gravou, não o retrato da tabela. O preço disso é que uma rodada
dirigida também pode virar o corte: `reclassificar --paper X` às 10h passa a ser
a última execução que classificou alguém, e um pendente mais velho que 10h aparece
como `aviso` embora aquela rodada nunca tenha olhado para ele. O aviso continua
apontando o remédio certo (`run --only classificacao,export`); é um falso
positivo de uma rodada, não um sintoma a investigar.

### O que o `doutor` reprova

`doutor` sai com código 1 se algum item for **erro**; aviso não bloqueia.

| item | estado | quando |
|---|---|---|
| `regra_fora` | erro | há `fora` com `regra_fora` nula |
| `vocabulario` | aviso | `dim_area` ou `dim_topico` sem linhas |
| `triagem` | aviso | pendente que atravessou uma rodada de classificação |
| `schema`, `integridade`, `chave`, `api_*` | erro | tabela faltando, FK violada, chave ausente, API fora |

`fora` sem regra é **erro**, e não aviso, porque um descarte sem motivo não se
explica no painel; o Estágio A e o Estágio B já recusam gravar um assim, então o
que sobra é linha antiga e o conserto é um comando (`reclassificar --tudo`).
Vocabulário vazio é só aviso: banco recém-criado passa por aí legitimamente, e a
saída aponta `taxonomia carregar`.

Esse erro esteve aceso até 07/09/2026, por 164 linhas antigas sem `regra_fora`,
e a rodada da seção seguinte o apagou. Se ele voltar, a leitura é outra: linha
sem regra não nasce mais do pipeline, então a origem é dado escrito por fora.

### Recuperação de lacuna

`run` compara `MAX(data_hf_daily)` com hoje. Se houver mais de um dia de
publicação em aberto (feriado, falha, máquina desligada), coleta **todos** os
dias faltantes na mesma rodada e registra `lacuna_recuperada: [datas]` nos avisos.
Fim de semana vazio é normal e não é erro.

## Reclassificação total (operação manual)

A base tem papers classificados antes de `regra_fora` e `criterios_veredito`
existirem. A rodada que os traz para o vocabulário vigente é **uma operação
manual, feita uma vez** — não entra no agendamento e não roda sozinha.

**Executada em 07/09/2026**, `run-20260907-182217`: 516 papers, 346 `fora`,
43 amplo, 127 estrito, 170 fichas, zero pendentes. Depois dela: zero `fora` sem
regra, zero aprovado sem critério, um `run_id` só em toda a `fato_triagem`, e o
`doutor` saindo com código 0.

Custo e tempo medidos, com `--concorrencia 4` e `glm-5.3-flash`: **47 minutos e
US$ 0,21** para os 516 papers. As estimativas anteriores (8–14 h sequencial,
US$ 1 a 2) foram feitas sobre o `qwen3.8-flash`, cujo provider único estrangulou
a operação — ver a nota de modelo abaixo. `custos --mes` dá o valor real.

> **Modelo**: a rodada foi feita com `z-ai/glm-5.3-flash` nos dois estágios.
> O `qwen/qwen3.8-flash` que estava no `config.yaml` tem **um único provider**
> no OpenRouter (Alibaba, pool compartilhado) e passou 07/09 em 429: a rodada
> diária levou 10h30 para 19 papers e falhou em 14 deles. Antes de trocar o
> modelo de qualquer estágio, olhe `GET /api/v1/models/<id>/endpoints` — um
> endpoint só é risco operacional, não detalhe de catálogo.

```bash
# 1. espere a rodada diária das 07:30 terminar (log_execucao com finalizado_em)
# 2. a varredura, em terminal que sobreviva (nohup, tmux). Acima de
#    --concorrencia 1, o Ctrl+C só age quando as chamadas em voo terminam (até
#    ~18 min no pior caso): espere, não mate o processo — kill no meio de uma
#    gravação é o único jeito de corromper esta rodada
python -m hfpapers reclassificar --tudo --concorrencia 4

# 3. os papers que o Estágio B derrubou nas duas passadas: o próprio comando
#    imprime a lista colável no fim
python -m hfpapers reclassificar --paper 2608.23552

# 4. o passo 2 imprime a conferência da rodada (zero triagens de outra rodada,
#    zero papers sem triagem); o doutor confirma o zero `fora` sem regra
python -m hfpapers doutor --sem-rede

# 5. ler a fila de revisão da grade que a rodada deixou — nenhum rótulo foi
#    criado por ela; quem promove é a revisão da grade, por quórum
python -m hfpapers taxonomia listar
python -m hfpapers taxonomia nao-encaixes --eixo subarea

# 6. publicar
python -m hfpapers export && scripts/gerar_painel.sh --force
```

O painel só é regenerado no passo 6: **não há transição visível** para quem lê.
Depois da rodada, a distinção entre paper recente e paper importado deixa de
existir também nos dados — e **a marca disso é o `run_id` compartilhado**, não
`revisao`: toda linha de `fato_triagem` passa a trazer o `run_id` da rodada, que
é justamente o critério de conclusão que o comando confere. `revisao` sobe 1 em
cada linha, o que leva as 242 linhas importadas de 0 para 1 — filtrar por
`revisao ≥ 2` deixaria de fora exatamente as linhas antigas que a rodada veio
consertar.

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
seções (01 volume e recência, 02 vocabulário e cruzamentos, 03 regras do corte,
04 atenção e adoção, 05 por que passou), filtro cruzado por dia, veredito, área,
tópico, organização, regra de descarte e critério de veredito. `gerar_painel.py`
não desenha nada: extrai os dados de `marts/`, serializa em `DADOS` e embute o
app.

**O gatilho é dependência real, não horário chutado.** O estágio de export
escreve `marts/_manifest.json` por último e de forma atômica (`os.replace`),
depois dos 13 Parquet — então a mudança desse arquivo *é* o sinal de "pipeline
terminou". O plist usa `WatchPaths` nele; medido, dispara ~1s após o export.

Três defesas contra o disparo repetido ou perdido:

- `gerar_painel.py` grava o `run_id` gerado em `marts/.painel_run_id` e sai em
  no-op se o `run_id` não mudou — `WatchPaths` pode disparar mais de uma vez
  para a mesma escrita;
- `ThrottleInterval` de 60s segura rajada;
- `StartCalendarInterval` às 08:30 é rede de segurança para o caso de o
  `WatchPaths` perder a notificação do `os.replace` (troca de inode). Se o
  gatilho já pegou, essa execução sai em no-op pela trava de `run_id`.

### O que o painel mostra

**Verde `#4ec07a` significa aprovado**, em todo o painel: a linha da taxa de
aprovação, a escala de aprovação do heatmap e a cor da matriz de áreas. O
amarelo (`ACCENT`) voltou a ser só link e destaque — ele já significou
"aprovado" nesses três lugares e brigava com o próprio papel de chamar atenção.
Estrito continua azul e amplo laranja na distribuição por veredito; a curva do
voto é roxa, porque não é nenhuma dessas coisas.

Na seção **03 · Regras do corte**, dois cards espelhados:

- **Onde o pipeline corta** (Pareto) — motivos de descarte em ordem de volume,
  cada barra rotulada "n · % dos descartados". A linha do acumulado saiu: com
  seis regras ela era decorativa. A barra "regra não registrada" continua no
  código mesmo tendendo a zero — categoria que some quando zera esconde o dia em
  que ela deixar de ser zero.
- **Por que o pipeline aprova** (card novo) — uma barra horizontal por critério
  de veredito, empilhada por veredito do paper (estrito no verde escuro, amplo
  no verde claro), com separador entre o bloco dos critérios de estrito e o dos
  de amplo. A contagem é **por ocorrência**: paper com dois critérios entra nas
  duas barras, e a soma passa do total de aprovados — o subtítulo diz isso e
  mostra a cobertura de critério do recorte. Clicar numa barra filtra o painel
  inteiro, como no Pareto.

Na seção **02 · Vocabulário e cruzamentos**, o heatmap Tópico × tempo tem três
vistas com **uma escala cada**, porque a vista troca a medida da célula e não só
a ordem das linhas: `volume` (sequencial azul), `crescimento` (divergente —
vermelho caiu, cinza estável, verde cresceu) e `aprovação` (sequencial verde). A
matriz área primária × secundária virou matriz de bolhas: cor é a taxa de
aprovação, tamanho é o total. Grande e verde é muito e muito aprovado; grande e
cinza é muito e pouco.

Na ficha do paper, a linha do veredito traz os critérios em português
("ESTRITO · artefato aberto + benchmark"); quando há contraparte de fronteira,
um selo ao lado diz `fronteira: quase <contraparte>` — linha antiga, gravada
antes de a contraparte existir, mostra só "decisão de fronteira". Nenhuma
justificativa é mais escondida pela origem do veredito: ou ela aparece, ou
aparece o aviso de que o pipeline não registrou motivo (linha antiga) ou de que
o Estágio B não concluiu.

### As duas abas

**Janela** — os últimos 90 dias (`--dias N` muda), com o filtro cruzado e as
cinco seções. Sem recorte o arquivo cresceria para sempre: entram ~30 papers por
dia de publicação.

**Registro histórico** — de cada trimestre já fora da janela, os **10 aprovados
mais votados** com a ficha inteira e os **10 descartados mais votados** com a
regra e a justificativa que os tiraram. A série completa continua nos Parquet e
no banco; o painel mostra a janela mais esse resumo.

Paper sem linha em `fato_triagem` (o Estágio A ou o Estágio B falhou nele,
inclusive depois da segunda passada do Estágio B) não é o mesmo que descartado:
fica fora das duas listas e das duas contagens, e aparece só como `nx` no
subtítulo da segunda seção. Entrasse como `amplo` ou `fora`, um timeout de
infraestrutura viraria veredito — apareceria aprovado, ou no pódio dos
descartados com o campo da justificativa em branco.

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
em disco, sem estágio novo no pipeline, sem chamada de LLM e sem requisição ao HF.

O corte da aba histórica vem de `refresh.janela_morna_dias`, **não** de `--dias`.
É o ponto em que o pipeline para de atualizar os votos, então é onde um ranking
pode congelar sem mentir. A consequência prática: `--dias` continua sendo a
válvula para encolher o arquivo — baixar o valor mostra menos, não empurra
papers para o histórico.

Congelar aos 90 dias não perde quase nada, e isso foi medido em `fato_metrica`
(idade contada a partir de `data_hf_daily`, não do índice do snapshot — os
snapshots não começam no dia da publicação). Recalculado em 04/09/2026 sobre a
coorte de 185 papers com 14 dias ou mais de idade — 184 entram na conta, porque
um deles tem voto final zero e não admite normalização —, tomando como valor do
corte o último snapshot **até** aquele dia:

| corte | mediana upvote/final | ainda crescem >10% depois |
|---|---|---|
| dia +2 | 0,81 | 76,6% |
| dia +5 | 0,83 | 70,1% |
| dia +7 | 0,91 | 48,9% |
| dia +10 | 1,00 | 17,4% |
| dia +14 | 1,00 | 9,2% |
| dia +18 | 1,00 | 0,0% |

A mediana atinge o valor final **no dia +10** e o movimento residual acaba por
volta do **dia +18** — ainda dentro da janela quente de 30 dias, com folga de ~5x
até o corte de 90 dias. O maior salto tardio observado foi 286 → 340 votos, depois
do dia +10.

Uma armadilha da tabela, que o dado atual expõe: **as idades +1 a +4 não têm
snapshot nenhum** — o refresh não mede todo dia da primeira semana. As linhas
+2 e +5 não medem aqueles dias; elas carregam para frente o valor do dia 0
(mediana 0,805), e é por isso que sobem tão devagar.

O card *Como o voto amadurece* usa outra régua e por isso dá outro número: ele
marca o primeiro dia **medido** em que a mediana cruza **90%** do voto final, e
em 04/09/2026 esse dia é o **+5** ("estabiliza por volta do dia +5"). Não é
contradição com a tabela: aqui a pergunta é quando a mediana chega a 90%, lá é
quando chega a 100% (que também é o dia +10 na régua do card). O card só desenha
idades com pelo menos 5 papers medidos — o subtítulo dele diz isso — então os
dias +1 a +4 ficam sem ponto e o +5 é o primeiro candidato depois do dia 0, com a
amostra que essa régua tem naquela idade: 26 papers no dia +5, contra 184 no dia
0. A coorte é a mesma da tabela — 185 papers com 14 dias ou mais, dos quais 184
com razão utilizável.

### Tamanho

O peso vem do texto das fichas embutido em `DADOS`, não de HTML por card.
Medido em 07/09/2026, depois da reclassificação total: **856 KB para 516 papers
e 170 fichas**, dos quais 293 KB são fichas (~1,8 KB cada), 276 KB são os papers
(~548 B cada) e 131 KB é a série de métricas.

O custo por entrada do histórico é assimétrico de propósito — é o que permite as
duas listas terem tamanhos diferentes:

| Lista | Conteúdo | Por entrada | Por trimestre |
|---|---|---|---|
| 10 aprovados | ficha inteira (5 campos) | ~2,5 KB | ~25 KB |
| 10 descartados | regra + justificativa | ~0,3 KB | ~3 KB |

**~28 KB por trimestre, ~115 KB por ano** — contra os **~932 KB/mês** que a
janela viva acumularia se não fosse recortada (os 516 papers pesam 705 KB de
payload). Se doer, `--dias` é o botão para girar. O custo do descartado deixou
de ser piso otimista: com a reclassificação total, todo descartado do histórico
já carrega regra e justificativa de verdade.

Vale lembrar que `painel.html` é commitado e empurrado todo dia (217 KB
comprimido, ~77 MB/ano de repositório): cada KB adicionado se multiplica por 365.
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

# a mesma aba como ficará depois que o trimestre fechar, sem o aviso de
# consolidação. O `=` é obrigatório: sem ele o argparse lê -30 como opção.
scripts/gerar_painel.sh --dias 10 --dias-hall=-30 --force --destino /tmp/fechado.html

# status / disparo manual do agente
launchctl print    gui/$(id -u)/com.samuelrochamotta.hfpapers-painel
launchctl kickstart -k gui/$(id -u)/com.samuelrochamotta.hfpapers-painel
```

Por que o corte negativo: `--dias-hall` positivo puxa o corte para trás de hoje,
e um trimestre só perde o selo de consolidação quando `fim >= corte` deixa de
valer. Como o trimestre corrente termina no futuro, **nenhum valor positivo
mostra a aba no estado final** — só o corte adiantado consegue. Fora dessa
inspeção o valor negativo não faz sentido nenhum, e a geração diária (sem
argumentos) nunca chega perto dele.

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
| `fato_triagem` | veredito (`fora`/`amplo`/`estrito`), regra de descarte, teste de portabilidade, fronteira e sua contraparte |
| `dim_ficha` | os cinco campos da ficha, só para aprovados |
| `dim_area`, `dim_topico`, `dim_vertente` | vocabulário controlado (área hierárquica, tópico da grade antiga, vertente) |
| `tax_nao_encaixe` | fila de revisão da grade: paper, eixo em que o encaixe falhou, justificativa |
| `ponte_paper_*` | área, tópico, critério de veredito, keyword, autor (muitos-para-muitos) |
| `log_execucao`, `log_llm` | operação, tokens e custo |
| `dim_calendario` | inteligência temporal do Power BI |

Duas datas, separadas de propósito: `data_arxiv` (`paper.publishedAt`) e
`data_hf_daily` (`paper.submittedOnDailyAt`). Elas divergem em 35 de 35 papers no
lote de 25/08 — a operação diária é organizada pela segunda.

### O que mudou para quem monta o Power BI

Três coisas novas, todas já nos Parquet de `marts/`:

- **`ponte_paper_criterio`** (`paper_id`, `criterio`) — os critérios que
  sustentam o veredito de um aprovado, do enum de dez (cinco de estrito, cinco
  de amplo; ver *Regras de classificação*). **É um-para-muitos**: um paper
  aprovado pode se qualificar por mais de um critério (já há caso com dois), e
  cruzar essa ponte com `dim_paper` **multiplica as linhas**. Contar papers pede
  `DISTINCTCOUNT(paper_id)`; `COUNTROWS` conta ocorrências, que é outra medida
  (legítima — é a que o card *Por que o pipeline aprova* do painel usa — mas não
  é "quantos papers"). Descarte não tem critério: a tabela só traz aprovados.
- **`fato_triagem[fronteira_contraparte]`** (texto, nulo sem fronteira) — quando
  `decisao_fronteira` é verdadeira, guarda o que quase venceu: a regra de
  descarte ou o critério do lado oposto ao veredito. Serve para achar as
  decisões apertadas sem reabrir veredito nenhum.
- **`fato_triagem[revisao]` e `fato_triagem[run_id]`** — `revisao` conta quantas
  vezes o paper passou pela classificação: 1 na primeira, +1 a cada
  reclassificação, e **0 nas linhas que entraram como veredito importado**, que
  nunca passaram por ela. Antes da rodada total (04/09/2026): 242 linhas com 0
  (as importadas, todas de uma carga histórica só), 224 com 1, 9 com 2, 2 com 3.
  Depois dela (07/09/2026): 245 com 1, 248 com 2, 21 com 3, 2 com 4 — nenhuma
  com 0, porque toda linha passou pela classificação ao menos uma vez.
  **A marca da reclassificação total é o `run_id`, não `revisao`**, e a
  distribuição acima mostra por quê: as 242 importadas chegaram a **1**, não a
  2, então o filtro `revisao ≥ 2` teria deixado de fora justamente as linhas que
  a rodada veio consertar — nelas estavam 159 dos 164 `fora` sem `regra_fora`
  (os outros 5 vinham de rodadas normais anteriores à regra obrigatória). O que
  fecha a rodada é o `run_id` único em toda a `fato_triagem`.

Não há `.pbix` no repositório: o Power BI lê os Parquet e o modelo vive fora do
git (`docs/adr-001-fora-de-escopo-do-mapa.md`, decisão 2). Estas três colunas são
o contrato; montar as visuais é trabalho manual no Desktop.

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

São 13 arquivos (um por tabela), `ponte_paper_criterio.parquet` incluído.

No Power BI Desktop: Obter Dados → Parquet, apontar para `marts/`. Marcar
`dim_calendario` como tabela de datas e relacionar
`fato_metrica[data_snapshot] → dim_calendario[data]`,
`fato_metrica[paper_id] → dim_paper[paper_id]` e
`ponte_paper_criterio[paper_id] → dim_paper[paper_id]` (muitos-para-um, com a
armadilha de contagem descrita em *Modelo de dados*).

## Regras de classificação

As regras vivem em `prompts/`, versionadas — não embutidas em f-strings:

- `prompts/regras_classificacao.md` — as regras normativas (FORA, teste de
  portabilidade, critérios de estrito vs amplo, os cinco campos da ficha,
  guardrails);
- `prompts/estagio_a.md` — triagem barata + classificação taxonômica, com o
  vocabulário injetado do banco;
- `prompts/estagio_b.md` — portabilidade, critérios, veredito e ficha.

O veredito é estruturado, não impressão:

- **Todo `fora` tem exatamente uma regra de descarte** (`regra_fora`), a
  primeira que bate nesta ordem: `treino_ou_postreino`, `geracao_de_midia`,
  `percepcao_robotica_embodied`, `relatorio_tecnico_de_modelo`,
  `fora_de_escopo`, `portabilidade_reprovada`. O Estágio A só emite as cinco de
  conteúdo; a última é do Estágio B, que é quem aplica o teste.
- **Todo aprovado tem ao menos um critério de veredito** (`criterios_veredito`,
  gravados em `ponte_paper_criterio`), de um enum de dez — cinco de estrito
  (`padrao_arquitetural`, `artefato_aberto`, `invalida_pratica`,
  `vulnerabilidade`, `tecnica_de_avaliacao`) e cinco de amplo (`benchmark`,
  `panorama`, `framework_conceitual`, `principio_sem_o_como`,
  `exige_acesso_interno`). O veredito decorre da lista: qualquer critério de
  estrito ⇒ estrito. A justificativa aplica o critério ao paper em vez de
  descrevê-lo.
- **Fronteira tem contraparte.** `decisao_fronteira` verdadeira exige
  `fronteira_contraparte`: a regra ou o critério que quase venceu, de lado
  diferente do veredito. Mistura de lados na lista não é fronteira.

Quatro validações em código guardam isso (`llm/estagio_a.py`,
`llm/estagio_b.py`), porque o JSON Schema garante forma, não coerência:

1. `fora` sem regra ⇒ rejeitado, o modelo refaz; esgotadas as tentativas, o
   paper fica pendente (nunca um `fora` sem motivo).
2. aprovado sem critério ⇒ idem.
3. veredito incoerente com a lista (critério de estrito com `amplo`, só amplo
   com `estrito`, `fora` com critérios) ⇒ idem: veredito íntegro é essencial.
4. fronteira sem contraparte, ou contraparte do mesmo lado ⇒ refaz **uma vez**;
   se persistir, grava como veio com o aviso `fronteira_incoerente:<paper_id>`.
   A flag nunca vira `false` pela nossa mão; contraparte sem fronteira é
   descartada com aviso.

Três invariantes que os testes cobrem:

1. **Upvote não entra em decisão nenhuma** e não aparece em prompt nenhum. É
   métrica de saída, guardada em `fato_metrica` para você descobrir depois se
   prediz aprovação. A aba histórica do painel ordena por upvote, mas isso é
   exibição, não decisão: o veredito já foi dado e não é reaberto. A lista de
   descartados existe justamente para medir a divergência — no lote atual, 13
   dos 20 papers mais votados são `fora`.
2. **O Padrão Extraído é escrito e testado antes do veredito.** A ordem das
   propriedades no schema do Estágio B é normativa.
3. **A LLM não cria rótulo, e não propõe nenhum.** O enum é injetado do banco;
   quando nada serve, ela declara em qual dos três eixos o encaixe falhou e por
   quê, e isso vai para `tax_nao_encaixe`. Mesmo assim o paper sai com par e
   vertente: não-encaixe é fila de revisão, não recusa de classificar.

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
├── execucao.py     orquestra os 5 estágios, a reclassificação e log_execucao
├── taxonomia.py    governança do vocabulário: promoção, fusão, export/carga
├── guardrails.py   avisos de volume
├── doutor.py       diagnóstico
├── log.py          logging com corte de segredo
├── fontes/         hf_client.py (httpx, retry, rate limit) + modelos.py (pydantic)
├── llm/            cliente OpenRouter, schemas, estágios A e B
└── estagios/       coleta, enriquecimento, classificação, refresh, export
scripts/
├── run_daily.sh        pipeline diário (launchd, 07:30)
├── gerar_painel.sh     wrapper do painel (launchd, WatchPaths em _manifest.json)
├── gerar_painel.py     monta relatorios/painel.html a partir dos Parquet
└── painel_app.js       app do painel (porte do artboard da Claude Design)
prompts/            regras versionadas
config/             taxonomia_inicial.json — o vocabulário de bootstrap
docs/               spec do mapa e ADRs
marts/              ← o Power BI aponta para cá
relatorios/         artefatos de leitura: painel.html
data/               o banco SQLite
```

`relatorios/`, `marts/`, `data/` e `logs/` não são versionados. A diferença entre
eles: `relatorios/` e `marts/` regeneram do banco; `data/` **é** a fonte.
