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

### Três chaves que existem por causa do OpenRouter

O `config.yaml` carrega a calibração de cada uma em comentário, com as medições.
O que segue é por que elas existem — a leitura, não o número.

**`llm.prazo_total_s` (90 s) — o teto que o `timeout_s` não é.** `llm.timeout_s`
é read timeout do httpx: ele conta o tempo desde o último byte recebido. O
OpenRouter manda linhas de keep-alive `: OPENROUTER PROCESSING` enquanto o
provedor pensa, e **cada uma reinicia esse relógio**. O resultado é o modo de
falha mais caro que este projeto encontrou: uma chamada de 409,8 s atravessa um
teto de 180 s **sem erro, sem retentativa e sem linha em `log_llm`** — a rodada
fica pendurada em silêncio, e a única evidência é o ritmo caindo. Foi assim que a
primeira tentativa da rodada 1 morreu: quatro threads em voo, sete minutos, zero
chamadas concluídas.

`prazo_total_s` é um prazo de ponta a ponta nosso: a chamada roda numa thread e é
abandonada aos 90 s, caindo na retentativa que já existia. O valor foi calibrado
medindo, não chutado — em 201 chamadas com provedor registrado (as quatro
rodadas de validação de 15:06–15:12 mais a rodada de 30 papers que expôs a cauda)
o pior caso legítimo foi 55,5 s no Estágio A e 13,8 s no Estágio B, e o valor
seguinte depois de 55,5 s era 409,8 s: o teto cai no vazio entre os dois. Na
rodada 2 ele pegou **7 chamadas em 4.407 (0,16%), todas recuperadas na
retentativa**. `0` desliga, para quando o modelo mudar e a
distribuição junto.

Duas consequências que valem para conferir a fatura: a chamada abandonada
**continua sendo cobrada** (~US$ 0,0004) e sai com uso zero, porque os tokens
vinham na resposta que nunca foi lida — então `log_llm` **subestima** o gasto
exatamente nessas linhas. Conte-as com `erro LIKE 'ErroPrazo%'`.

**`log_llm.provedor` — a coluna sem a qual a lentidão não tem réu.** O OpenRouter
roteia entre ~24 endpoints do mesmo modelo, e eles não se comportam igual: numa
medição de 171 chamadas, Together deu média de 3,3 s (pior 13,8 s) e Sail
Research 14,6 s, com pior caso de 55,5 s. A chamada de 195 s que motivou a coluna
não está em `log_llm`: ela veio de uma sonda com o payload real do Estágio A,
disparada fora do pipeline (ticket 07, *Rodada 1, tentativa 1*). Sem a coluna,
"a rodada ficou 9x mais lenta" é uma frase sem sujeito. Com ela, o relatório de
massa sai por provedor (seção 6 dos relatórios em `docs/`) e a cauda ganha dono —
ou não ganha, que é informação igual: quem morre antes de responder não informa
quem era, e essas chamadas ficam numa linha
*(não registrado)* em vez de acusarem um inocente. Foi essa coluna que mostrou
que trocar de endpoint trata a mediana e não a cauda: **a pior chamada do dia,
409,8 s, saiu do Together**, o endpoint de melhor mediana do catálogo.

**`llm.esforco_raciocinio` (`medium`) — porque o GLM raciocina de qualquer
jeito.** O `z-ai/glm-5.3-flash` raciocina de forma obrigatória: `reasoning.enabled:
false` volta HTTP 400. Com o prompt da grade facetada ele gastava **2.343 tokens
de rascunho para produzir 540 caracteres de JSON**. Passar `effort` derruba a
saída para ~220 tokens e a latência de 174 s para 12 s — 14x — **sem mexer na
classificação**: medido em 420 chamadas, `low` e `medium` concordam entre si em
87% do par área > sub-área, mais do que `low` concorda **consigo mesmo** (82%).
Esse 82% é a origem do número de ~19% de instabilidade intrínseca da grade que
aparece nos relatórios de massa: a diferença entre dois níveis de esforço é menor
que o ruído do modelo consigo mesmo, então o esforço não é onde a grade perde
precisão.

## Pipeline

Seis estágios, executados nesta ordem, com persistência incremental:

```
[1] COLETA        → busca dias novos no HF, insere papers inéditos
[2] ENRIQUECIMENTO→ para papers inéditos, busca campos do endpoint por-paper
[3] CLASSIFICAÇÃO → Estágio A (barato) em todos; Estágio B (forte) nos sobreviventes
[4] REFRESH       → re-consulta métricas vivas de papers já na base
[5] DATAS_ARXIV   → verifica a submissão v1 dos papers ainda pendentes de auditoria
[6] EXPORT        → materializa os Parquet do Power BI
```

Falha no estágio 3 não corrompe o que o 1 gravou: a rodada termina com
`status = 'parcial'` e os avisos dizem onde doeu.

**Dia antigo é `run --data`.** Não existe carga histórica, comando especial nem
diretório de insumo: `daily_papers?date=` devolve qualquer data passada, e a
coleta trata 14/08 igual a ontem. Um dia que ficou de fora entra com
`python -m hfpapers run --data 2026-08-14`, pelos mesmos seis estágios e com o
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
python -m hfpapers export                     # só exporta, sem consultas externas
python -m hfpapers auditar-datas-arxiv         # relatório de toda a base, sem alterar o banco
python -m hfpapers auditar-datas-arxiv --aplicar
python -m hfpapers run --only datas_arxiv,export  # verifica v1 pendentes e exporta
python -m hfpapers reclassificar --data 2026-08-25
python -m hfpapers reclassificar --paper 2608.23552
python -m hfpapers reclassificar --tudo                    # a base inteira, horas
python -m hfpapers reclassificar --tudo --so-estagio-a       # só taxonomia/Estágio A
python -m hfpapers reclassificar --tudo --concorrencia 4   # 1 = sequencial, teto 8
python -m hfpapers taxonomia listar
python -m hfpapers taxonomia nao-encaixes [--eixo area|subarea|vertente]
python -m hfpapers taxonomia fundir --de "X" --para "Y"   # duas sub-áreas irmãs
python -m hfpapers taxonomia exportar [--destino config/taxonomia_inicial.json]
python -m hfpapers taxonomia carregar [config/taxonomia_inicial.json]
python -m hfpapers modelos listar
python -m hfpapers custos --mes 2026-08       # quanto a LLM custou
python -m hfpapers doutor [--sem-rede]        # chave, API, banco e pendências de triagem
python -m hfpapers schema                     # DDL efetivo do banco
```

`--so-estagio-a` encerra a reclassificação antes do Estágio B: candidatos não
recebem novo veredito nem nova ficha. Serve para medir a grade, não para
substituir a reclassificação completa.

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
`docs/adr/001-fora-de-escopo-do-mapa.md`).

A ressalva importa porque a rodada total dura horas e pode cair no meio: **a
varredura que estoura não é equivalente**. Os workers vão adiante da thread
principal, então ficam papers já pagos que nunca chegam a ter triagem — medido
com `--concorrencia 4`, 2 triagens gravadas contra 10 papers já em `log_llm`.
Nenhuma linha se perde: o gasto desses papers está em `log_llm` e aparece em
`hfpapers custos`, mas fica **fora** de `log_execucao.custo_usd`, que conta só o
que virou triagem. Com `--concorrencia 1` nada é chamado adiante do paper que
estoura.

`taxonomia exportar` grava áreas, sub-áreas e vertentes do banco (rótulo +
definição, sem a fila de revisão) no JSON versionado, com a sub-área aninhada sob
a sua área; `carregar` é o inverso, para banco vazio, e é idempotente — rótulo
que já existe não é tocado. `taxonomia fundir` funde **duas sub-áreas do mesmo
pai** e reescreve a ponte; não há parâmetro de tipo nem de nível, porque só existe
um vocabulário hierárquico desde a contração da grade antiga e só um nível funde.
Ele recusa três coisas, com código 2 e mensagem: fundir um rótulo nele mesmo (que
apagava todas as pontes do rótulo em silêncio), rótulos que não são irmãos, e
**área raiz** — a grade de dez raízes é trava do ticket 08, e a regra 2 funde na
irmã sub-área. `taxonomia nao-encaixes` lê a fila de revisão da grade: os
papers em que o Estágio A declarou que nenhuma célula servia, com o eixo que
falhou (`area`, `subarea` ou `vertente`) e a justificativa. **Ninguém promove
rótulo a partir dela dentro do pipeline**: a classificação nunca cria
vocabulário, e a promoção é da revisão da grade, por quórum.

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
| `vocabulario` | aviso | `dim_area` ou `dim_vertente` sem linhas |
| `triagem` | aviso | pendente que atravessou uma rodada de classificação |
| `schema`, `integridade`, `chave`, `api_*` | erro | tabela faltando, FK violada, chave ausente, API fora |

`fora` sem regra é **erro**, e não aviso, porque um descarte sem motivo não se
explica no painel; o Estágio A e o Estágio B já recusam gravar um assim, então o
que sobra é linha antiga e o conserto é um comando (`reclassificar --tudo`).
Vocabulário vazio é só aviso: banco recém-criado passa por aí legitimamente, e a
saída aponta `taxonomia carregar`. A área que o check conta é a **da grade que o
Estágio A oferece** — raiz com ao menos uma sub-área —, e não `dim_area` inteira:
raiz sem filha não forma célula, e contá-la faria o diagnóstico dizer que há
vocabulário onde a classificação não acha par nenhum. A linha de `ok` diz os três
números: `10 areas com 64 sub-areas, 10 vertentes`.

Esse erro esteve aceso até 07/09/2026, por 164 linhas antigas sem `regra_fora`,
e a rodada da seção seguinte o apagou. Se ele voltar, a leitura é outra: linha
sem regra não nasce mais do pipeline, então a origem é dado escrito por fora.

### Recuperação de lacuna

`run` compara `MAX(data_hf_daily)` com hoje. Se houver mais de um dia de
publicação em aberto (feriado, falha, máquina desligada), coleta **todos** os
dias faltantes na mesma rodada e registra `lacuna_recuperada: [datas]` nos avisos.
Fim de semana vazio é normal e não é erro.

## Reclassificação total (operação manual)

A rodada que traz a base inteira para o vocabulário vigente é **uma operação
manual** — não entra no agendamento e não roda sozinha. Ela já foi feita três
vezes, e as três estão medidas.

| rodada | `run_id` | base | chamadas | custo | parede | ritmo |
|---|---|---:|---:|---:|---:|---:|
| critérios de veredito, 07/09 | `run-20260907-182217` | 516 | — | US$ 0,21 | 47 min | — |
| grade v1, só Estágio A, 08/09 | `run-20260908-162429` | 3.166 | 3.169 | **US$ 1,2326** | 31 min | 101,2 ch/min |
| grade v2, A e B, 08/09 | `run-20260908-173724` | 3.166 | 4.407 | **US$ 2,0406** | 61,5 min | 71,7 ch/min |

Com `--concorrencia 4` e `glm-5.3-flash` nas três. Três leituras que valem para
a próxima:

- **A estimativa por chamada é confiável e a de tempo não é.** A rodada 1 previu
  US$ 1,2300 e gastou US$ 1,2326 — 0,2% de erro. A mesma estimativa previu 1,4 h
  e a rodada levou 0,52 h, porque o ritmo usado era de antes do
  `esforco_raciocinio` (36,6 contra 101,2 chamadas/min). Custo escala com token,
  que se conta; tempo escala com o endpoint que o OpenRouter sortear.
- **A rodada 2 custou 66% mais que a 1 por dois motivos somados**, não um: a
  grade v2 tem 64 sub-áreas em vez de 47 e o prompt do Estágio A cresceu ~26%,
  e o Estágio B entrou (1.235 chamadas, US$ 0,5707). Sozinho, o Estágio A subiu
  de US$ 1,2326 para US$ 1,4968.
- **`log_execucao.custo_usd` e `log_llm` não batem, e é de propósito.** A rodada 2
  fechou com US$ 2,0406 em `log_execucao` e US$ 2,0675 somando `log_llm`. A
  diferença de US$ 0,0269 são as 66 chamadas que erraram e foram refeitas: elas
  foram cobradas e não viraram triagem. `custos --mes` lê `log_llm`, que é o
  número da fatura; `log_execucao` conta o que virou dado.

> **Modelo**: as rodadas foram feitas com `z-ai/glm-5.3-flash` nos dois estágios.
> O `qwen/qwen3.8-flash` que estava no `config.yaml` tem **um único provider**
> no OpenRouter (Alibaba, pool compartilhado) e passou 07/09 em 429: a rodada
> diária levou 10h33 para 19 papers e falhou em 7 deles (`log_execucao.avisos`,
`run-20260907-073150`: 7 `estagio_a_falhou`; foram 43 chamadas com erro no
Estágio A, e é esse número maior que a versão anterior deste texto reportava). Antes de trocar o
> modelo de qualquer estágio, olhe `GET /api/v1/models/<id>/endpoints` — um
> endpoint só é risco operacional, não detalhe de catálogo.

O que cada rodada deixou na base: a de 07/09 fechou 516 papers em 346 `fora`,
43 amplo e 127 estrito, com 170 fichas — zero `fora` sem regra, zero aprovado sem
critério, um `run_id` só em toda a `fato_triagem`. A de 08/09 fechou **3.166
papers em 2.073 `fora`, 348 amplo e 745 estrito, com 1.093 fichas** — zero
aprovado sem ficha, zero ficha órfã, zero pendente, e o `doutor` saindo com
código 0 nas duas.

```bash
# 1. espere a rodada diária das 07:30 terminar (log_execucao com finalizado_em)
# 2. a varredura, em terminal que sobreviva (nohup, tmux). Acima de
#    --concorrencia 1, o Ctrl+C só age quando as chamadas em voo terminam:
#    llm.retry.tentativas × llm.prazo_total_s + backoff = 3 × 90 s + 2 s + 4 s
#    ≈ 4,6 min por estágio, ≈ 9,2 min se o paper já estiver no Estágio B (a
#    thread faz A e depois B). Com `prazo_total_s: 0` o teto de ponta a ponta
#    sai e volta a valer `llm.timeout_s`: a espera dobra, ≈ 9,1 min por estágio
#    e ≈ 18 min no Estágio B. Espere, não mate o processo — kill no meio de uma
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

# 6. exportar e gerar o painel localmente
python -m hfpapers export
python scripts/gerar_painel.py --force
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
seções (01 volume e seletividade, 02 vocabulário da grade, 03 regras do corte,
04 atenção e adoção, 05 por que passou), filtro cruzado por dia, veredito, área,
vertente dominante, organização, regra de descarte e critério de veredito.
`gerar_painel.py` extrai os dados de `marts/`, serializa em `DADOS` e embute
o JavaScript e os estilos em um único HTML.

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

As cores têm significados constantes: **azul `#3987e5` para estrito**, **laranja
`#d95926` para amplo**, **cinza `#6b7480` para fora** e **verde `#4ec07a` para
a taxa ou o total de aprovados**. Roxo `#9085e9` identifica a curva de votos;
âmbar `#d9a441` marca seleção e destaque.

**Barra de recorte** — os números da barra descrevem o **recorte em vigor**,
não a janela inteira: marcado `estrito`, o menu de área passa a dizer 7 em
"Modelo & treino" (que tem 524 papers na janela) e as áreas sem nenhum estrito
caem para o fim da lista, com zero. Cada seletor se conta com a **sua própria**
dimensão solta — senão marcar a primeira área zeraria as demais linhas do
próprio menu e a segunda ficaria inalcançável. Vale igual para os chips de
veredito, que por isso continuam mostrando o tamanho dos três baldes quando um
deles está marcado.

Área, sub-área, vertente e dia mantêm no menu a linha que zerou, com o zero
visível: ali o zero é informação de grade — diz que aquela célula do
vocabulário não produz estrito nenhum. Organização é a exceção: são 564 nomes
na janela, dos quais 368 zeram só de o recorte virar estrito, e a lista de
zeros não informa nada que a busca do menu já não resolva. Some — menos a que
estiver marcada, que nunca sai do próprio menu.

**01 · Volume e seletividade** — volume por dia ou semana, dividido por
veredito, e taxa de aprovação. Os controles permitem explorar o lote e sua
seletividade no recorte ativo.

**02 · Vocabulário da grade** — o card **Área primária** tem duas vistas,
com as áreas ordenadas por volume:

- **Distribuição:** largura proporcional ao número de papers, segmentos por
  veredito e total com percentual aprovado. Clicar na área filtra o painel.
- **Sub-áreas:** cada barra vale 100%, com fatias em ordem decrescente. Nomes e
  percentuais aparecem abaixo da barra; o tooltip traz definição e contagem.
  A composição usa marfim, areia e taupe (`#E8E0D4`, `#CFC0AD`, `#B3A18D`,
  `#95816F`, `#786454`), com hachuras para ampliar a distinção entre fatias.
  Esses estilos identificam segmentos localmente; não representam vereditos.

Fatias pequenas, abaixo de 2%, podem ser agrupadas em **outras**, que tem
contorno e padrão próprios; o tooltip lista os membros e suas contagens. A
cauda com um único membro mantém o nome dele. O agrupamento também limita a
quantidade de estilos distintos na barra.

A vista e o botão **Vertentes** foram removidos desse card. A vertente
**dominante** continua disponível no filtro geral e nas fichas: é a primeira
atribuição do paper, equivalente a `ponte_paper_vertente.ordem = 1`. Filtrar por
ela é diferente de contar qualquer atribuição primária ou secundária. A matriz
área primária × secundária e o heatmap Tópico × tempo também não fazem parte
do painel atual.

**03 · Regras do corte** — dois cards com a mesma altura e rolagem interna:

- **Por que o pipeline aprova:** uma barra por critério, empilhada pelo
  veredito final em azul/laranja. A contagem é por ocorrência: um paper com
  dois critérios aparece em duas barras. Clicar filtra pelo critério.
- **Onde o pipeline corta:** motivos de descarte em ordem de volume, com
  contagem e percentual dos descartados. Barras e legenda usam o mesmo cinza
  de `fora`. Clicar filtra pela regra; dados sem regra têm categoria própria.

**04 · Atenção e adoção** — três gráficos:

- **Os 10 papers que mais ganharam votos:** até dez papers, ordenados pelo
  ganho absoluto entre a primeira e a última medição disponíveis nos últimos
  sete dias, até a data de geração. Exige duas medições em datas distintas e
  crescimento positivo; empate usa `paper_id`. Círculo vazio marca o valor
  inicial e círculo cheio o final, ligados por uma linha em escala comum de
  votos absolutos. O ganho aparece à direita, e os valores e datas abaixo.
  As cores indicam veredito; o título abre o paper. O intervalo pode variar
  entre papers, portanto o ranking não mede votos por dia.
- **Quando os votos chegam a 90%?:** curva roxa da mediana do percentual
  `votos na medição / último total observado do paper`, com faixa P25–P75 e
  referência de 90%. O indicador D+ mostra a primeira idade medida em que a
  mediana chega a 90%; **papers com histórico elegível** conta a coorte total.
  Entram apenas papers com pelo menos duas medições, primeira no dia 0 ou 1
  desde o HF Daily, última aos 14 dias ou depois e último total positivo.
  Cada ponto usa somente as observações daquela idade, até o dia 30, e exige
  ao menos cinco papers. A amostra varia entre pontos; lacunas não são
  interpoladas. O último total ainda pode crescer: atingir 90% não confirma
  estabilização definitiva.
- **Upvotes no HF × stars no GitHub:** dispersão em escalas logarítmicas dos
  papers com repositório, com cores por veredito e indicação de página de
  projeto. Papers sem repositório ficam fora; zero stars fica na base do eixo.

O gráfico de defasagem arXiv → HF Daily foi removido. As datas verificadas,
o cálculo e a auditoria continuam disponíveis no banco, nos Parquet e no
comando `auditar-datas-arxiv` (ver a seção de auditoria).

**05 · Por que passou, e o que ficou registrado** — lista dos aprovados com
justificativa da decisão, critérios e ficha, aberta ao clicar no paper.

Na ficha do paper, a linha do veredito traz os critérios em português
("ESTRITO · artefato aberto + benchmark"); quando há contraparte de fronteira,
um selo ao lado diz `fronteira: quase <contraparte>` — linha antiga, gravada
antes de a contraparte existir, mostra só "decisão de fronteira". Nenhuma
justificativa é mais escondida pela origem do veredito: ou ela aparece, ou
aparece o aviso de que o pipeline não registrou motivo (linha antiga) ou de que
o Estágio B não concluiu.

### As três abas

**Aprovados** — a tabela dos aprovados dos últimos 90 dias (`--dias N` muda),
com a decisão e a ficha de cada um. É a aba inicial: abre ordenada por dia, com
10 linhas e um "mostrar mais" para abrir as 10 seguintes, o resto de uma vez, ou
recolher.

**Panorama** — os tiles e as quatro seções de gráficos sobre a mesma janela:
volume e seletividade, vocabulário da grade, regras do corte, atenção e adoção.

As duas dividem a barra de filtro e o mesmo estado: o recorte escolhido numa
vale na outra. Sem a janela o arquivo cresceria para sempre: entram ~30 papers
por dia de publicação.

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

Uma medição histórica do movimento dos votos foi feita em `fato_metrica`
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

Naquela amostra, a mediana atingiu o último valor observado **no dia +10** e
o movimento residual observado terminou por volta do **dia +18** — ainda dentro da janela quente de 30 dias, com folga de ~5x
até o corte de 90 dias. O maior salto tardio observado foi 286 → 340 votos, depois
do dia +10.

Uma limitação daquela medição histórica: **as idades +1 a +4 não têm
snapshot nenhum** naquela amostra; não se pode supor observação diária. As linhas
+2 e +5 não medem aqueles dias; elas carregam para frente o valor do dia 0
(mediana 0,805), e é por isso que sobem tão devagar.

A tabela acima é uma medição histórica de 04/09/2026, com carregamento do
último valor disponível até cada corte; não descreve a coorte atual do painel.
O gráfico **Quando os votos chegam a 90%?** usa apenas medições reais por idade,
sem carregar valores para dias sem observação, e os critérios descritos acima.
Seu indicador e sua amostra são recalculados a cada geração e filtro.

### Tamanho

O HTML incorpora os papers, fichas, séries de métricas, resumo histórico,
JavaScript e CSS. Na conferência de 08/09/2026, a versão atual ocupa cerca de
**2,48 MB (2,36 MiB)** e inclui os **1.970 papers da janela de 90 dias**.
O tamanho varia com o acervo e com os textos das fichas; números de versões
anteriores nos relatórios de medição são retratos históricos.

`--dias` reduz a janela viva sem apagar dados do banco ou dos Parquet. O
histórico leva as fichas dos dez aprovados e as justificativas dos dez
excluídos mais votados por trimestre, em vez de toda a série daquele período.
O ranking desempata por `paper_id` para evitar reordenação arbitrária no HTML.

Para gerar ou revisar localmente, use o gerador Python. O wrapper
`gerar_painel.sh` também cuida de logs e publicação: quando não recebe opções
de prévia e o HTML mudou, ele faz commit e push para `origin main`.

```bash
# gerar localmente, sem commit ou push
python scripts/gerar_painel.py          # janela padrão (90 dias)
python scripts/gerar_painel.py --force  # necessário após editar JS/CSS sem novo run_id

# inspecionar a aba histórica antes de o primeiro trimestre fechar.
# SEMPRE com --destino: o painel publicado não é rascunho.
python scripts/gerar_painel.py --dias 10 --dias-hall 10 --force --destino /tmp/previa.html

# a mesma aba como ficará depois que o trimestre fechar, sem o aviso de
# consolidação. O `=` é obrigatório: sem ele o argparse lê -30 como opção.
python scripts/gerar_painel.py --dias 10 --dias-hall=-30 --force --destino /tmp/fechado.html

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
mudam **o que** o painel mostra (medido em 04/09/2026, com `--dias 10` eram 270
papers em vez de 455, e os 185 que sobravam não apareciam em aba nenhuma; hoje a
janela padrão traz 1.970 e o desconto é proporcionalmente maior):

- `gerar_painel.sh` não commita nem empurra quando recebe `--dias`, `--dias-hall`
  ou `--destino`; sem essas opções, inclusive com `--force`, ele pode fazer
  commit e push de `relatorios/painel.html` para `origin main`;
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
| `dim_area` | vocabulário controlado dos dois níveis de área, numa tabela só: `area_pai` nulo é área raiz, preenchido é sub-área |
| `dim_vertente` | vocabulário controlado do eixo transversal: que movimento o paper faz |
| `tax_nao_encaixe` | fila de revisão da grade: paper, eixo em que o encaixe falhou, justificativa |
| `ponte_paper_*` | área (par > sub-área), vertente (com ordem), critério de veredito, keyword, autor (muitos-para-muitos) |
| `log_execucao`, `log_llm` | operação, tokens e custo; `log_llm.provedor` guarda qual endpoint do OpenRouter atendeu (nulo quando a chamada morreu antes da resposta) |
| `dim_calendario` | inteligência temporal do Power BI |

As datas têm papéis distintos:

- `data_hf_daily`: entrada no HF Daily; organiza a coleta e a idade das métricas.
- `data_arxiv_informada_hf`: `paper.publishedAt` recebido do HF, que pode apontar
  para uma revisão. `data_arxiv` é seu alias legado, mantido por compatibilidade.
- `data_arxiv_v1`: submissão inicial verificada no arXiv, com a proveniência
  temporal em `arxiv_v1_verificado_em`. Revisões recebidas do HF não a sobrescrevem.

A defasagem auditada usa `data_hf_daily - data_arxiv_v1`. A API arXiv fornece a
data de submissão, que não é necessariamente a data do anúncio público.

### A taxonomia facetada

Dois eixos ortogonais, e nenhuma coordenada é dedutível da outra. Spec em
`docs/specs/taxonomia-facetada.md`, implementada em 08/09/2026.

- **ÁREA — em que peça do sistema o trabalho mexe.** Hierárquica em dois níveis:
  uma área raiz e uma sub-área sob ela.
- **VERTENTE — que movimento o paper faz com essa peça.** Plana e transversal a
  todas as áreas: qualquer peça pode ser medida, barateada, endurecida, treinada.

O teste que a grade anterior falhava e esta passa: `MemUse` e `LycheeMemory V2`
vivem na mesma sub-área e antes eram indistinguíveis; com a vertente, um **mede**
e o outro **barateia**.

**Cardinalidade esperada.** Um paper recebe exatamente um par primário (área > sub-área),
no máximo um par secundário e de uma a duas vertentes ordenadas. **Toda a base
recebe as três facetas, inclusive os `fora`** — é o que torna a regra de descarte
revisável com dado em vez de memória ("Geração de mídia > World models
generativos, descartado 95 vezes" é uma frase que a base sabe dizer).

A persistência valida o parentesco área > sub-área. Um par inválido é rejeitado
e registrado em `tax_nao_encaixe`; se o secundário for válido, ele vira primário.
Se nenhum par sobreviver, a triagem permanece, mas o paper fica sem área até a
revisão. Esse caso exige inspecionar e reclassificar o paper; não é uma categoria
nova nem uma correção automática da taxonomia.

Três decisões de schema, todas em `src/hfpapers/schema.sql`:

| Peça | O que é, e por quê |
|---|---|
| `dim_area.area_pai` | A hierarquia mora na auto-referência, não numa tabela irmã: área e sub-área são o mesmo tipo de coisa, e uma tabela só evita duas definições divergentes. Sub-área é filha de **exatamente uma** área. |
| `ponte_paper_area (paper_id, area, subarea)` | A sub-área entra na **chave primária**. Com a chave `(paper_id, area)` o par secundário de mesma área e sub-área diferente era proibido, e ele é caso real. `is_primaria` distingue os dois pares. |
| `ponte_paper_vertente.ordem` | `1` é a dominante, `2` a secundária. Sem a ordem as duas seriam intercambiáveis e nenhum ranking teria resposta única. O teto de duas é aplicado **na persistência**, não só pedido no prompt. |

**A grade vigente** (`config/taxonomia_inicial.json`, recarregável com
`taxonomia carregar`): **10 áreas raiz, 64 sub-áreas, 10 vertentes**. As dez
áreas nasceram do desenho e não se mexeram; as 64 sub-áreas e a décima vertente
saíram de medição, não de leitura de título — `docs/relatorios/grade-v2-resumo.md` conta a
passagem da v1 para a v2, rótulo a rótulo.

```
Medir ......... cria o instrumento: benchmark, protocolo, métrica, auditoria
Treinar ....... muda os pesos para a peça ficar melhor: pós-treino, RL, destilação
Baratear ...... reduz custo, latência, memória ou tokens
Endurecer ..... sustenta o comportamento sob ataque, ruído ou entrada fora da distribuição
Confiabilizar . reduz o erro silencioso: alucinação, calibração, atribuição
Automatizar ... tira o humano do laço: auto-evolução, síntese, busca automática
Explicar ...... torna legível o que já acontece: interpretabilidade, sondas, causalidade
Especificar ... formaliza o que se quer antes de executar: contrato, verificação, política
Adaptar ....... ajusta a um contexto, usuário ou domínio sem retreinar
Escalar ....... faz funcionar maior: horizonte, contexto, número de agentes
```

`Treinar` é a décima, e a razão de ela existir está em
`docs/adr/002-a-lista-de-vertentes.md`: o desenho previa que a lista **perderia**
duas vertentes e ela ganhou uma.

#### Medições da grade e revisão posterior

Medição completa em `docs/relatorios/massa-grade-v2.md`
(`run-20260908-173724`, 3.166 papers). O retrato histórico dessa rodada:

| | |
|---|---|
| cobertura | 3.162 papers com par primário (99,9%), 583 com par secundário (18,4%), 4 sem faceta nenhuma, 3.166 com ao menos uma vertente (100%), 680 com duas (21,5%) |
| áreas maiores | Modelo & treino 872 · Geração de mídia 577 · Avaliação & instrumentação 495 · Percepção & robótica 358 |
| vertentes maiores | Treinar 45,3% · Medir 31,8% · Baratear 16,6% |
| fila de revisão | 81 não-encaixes (2,6% da base): 49 de sub-área, 30 de área, **2 de vertente** |

Depois dessa medição, quatro papers tiveram a classificação revisada na rodada
`run-20260908-225106`. Na conferência de 08/09/2026, os **3.166 papers têm par
primário**, 585 têm par secundário e 681 têm uma segunda vertente. Não há paper
sem área primária. Os relatórios da rodada anterior preservam os números
originais para rastreabilidade.

**As duas checagens da spec continuam falhando, e isso está registrado, não
esquecido:**

- **Checagem A** — nenhuma sub-área acima de ~25% da sua área: **FALHA**, 7
  acima do teto (eram 15 na v1). A pior é *Internos do modelo >
  Interpretabilidade & sondas*, com 63,0% — e o que está estreito ali é a
  **área**, não a sub-área: "os pesos como objeto de estudo" quer dizer
  interpretabilidade.
- **Checagem B** — nenhuma vertente abaixo de ~2%: **FALHA**, 2 abaixo do piso.
  *Adaptar* 1,2% e *Especificar* 1,1%. É a pendência declarada do ADR 002; as
  duas são as primeiras candidatas de uma v3, e nenhuma foi absorvida ainda
  porque absorver reescreve pontes e exige rodada de reclassificação.

A grade tem **~19% de instabilidade intrínseca**: o mesmo paper, mesma
configuração, temperatura 0, recebe pares diferentes em cerca de uma rodada em
cada cinco (81-82% de auto-concordância, três medições em 08/09/2026). É o número
que impede tratar qualquer rótulo a poucos pontos de um limiar pelo valor seco.

#### Como medir a grade de novo

```bash
# O arquivo de saída é obrigatório: o script recusa rodar sem ele. Tinha
# default para docs/relatorios/massa-grade-v1.md e sobrescrevia em silêncio o
# relatório da v1 — a causa registrada da grade v2, que o banco de hoje já não
# reproduz. `-` no lugar do run_id usa o log inteiro.
/opt/miniconda3/envs/digest-hf/bin/python scripts/relatorio_massa.py \
    run-AAAAMMDD-HHMMSS docs/relatorios/massa-grade-v3.md
```

O relatório traz cobertura, distribuição por área e sub-área com o veredito de
cada regra, distribuição por vertente com a coluna de dominantes, não-encaixes
por eixo, custo real contra o estimado, roteamento por provedor e a lista de
rótulos perto de um limiar. As duas checagens saem calculadas.

#### O que ficou de fora, e por quê

O filtro por vertente dominante já está implementado no painel; a remoção da
vista Vertentes de Área primária não remove esse filtro nem a faceta dos dados.
Duas decisões de escopo permanecem:

- **Versionamento da taxonomia antiga.** Decidido contra, pelo princípio do
  ADR 001: uma fonte de verdade por decisão. A grade de tópicos foi **removida**
  do banco em vez de conviver com uma coluna de versão — conviver custaria um
  filtro permanente em toda consulta, para sempre, por causa de dado que ninguém
  vai querer. A rastreabilidade vem do `run_id` em `fato_triagem` e do histórico
  de `config/taxonomia_inicial.json` no git.
- **Terceira faceta de domínio de aplicação.** Avaliada e recusada: o único
  domínio recorrente na base é código, e ele já cai em *Harness & orquestração >
  Engenharia de código com agente*. Uma faceta cujo único valor recorrente é
  dedutível de outra não é eixo, é redundância — o erro que a própria spec veio
  consertar. A fila de não-encaixe sustenta a recusa por outro lado: as famílias
  que pediram vocabulário novo pediram **área** (neurociência e sinal biomédico,
  finanças, ciência natural fora de LLM), e nenhuma pediu domínio de aplicação.

### O que mudou para quem monta o Power BI

Seis coisas novas, todas já nos Parquet de `marts/`:

- **`ponte_paper_area`** (`paper_id`, `area`, `subarea`, `is_primaria`) —
  substitui a ponte de área plana. **É um-para-muitos**: um paper pode ter par
  primário e secundário, e o secundário pode repetir a área do primário com
  sub-área diferente. `is_primaria = 1` é o par principal; para "a área do
  paper", filtre por ele, senão a contagem por área infla em ~18,5%.
- **`ponte_paper_vertente`** (`paper_id`, `vertente`, `ordem`) — o eixo
  transversal, com a **ordem** que separa a dominante (`1`) da secundária (`2`).
  Também um-para-muitos: na medição da rodada total de 08/09, eram 3.166 linhas
  de ordem 1 e 680 de ordem 2. Ranking de
  vertente que não filtra `ordem = 1` está somando acompanhamento com
  dominância — e as duas coisas divergem (*Baratear* tem 524 atribuições e 383
  dominantes; *Escalar*, 152 e 77).
- **`dim_area[area_pai]`** — nulo em área raiz, preenchido em sub-área. Sem essa
  coluna a dimensão chega ao Power BI como 74 rótulos planos, sem dizer qual é
  raiz nem de quem cada sub-área é filha. É o que permite a hierarquia
  área > sub-área numa matriz.
- **`ponte_paper_criterio`** (`paper_id`, `criterio`) — os critérios que
  sustentam o veredito de um aprovado, do enum de dez (cinco de estrito, cinco
  de amplo; ver *Regras de classificação*). **É um-para-muitos**: um paper
  aprovado pode se qualificar por mais de um critério — e não é raro: **506 dos
  1.093 aprovados (46,3%) têm dois ou mais**, e quatro têm quatro. Cruzar essa
  ponte com `dim_paper` **multiplica as linhas**. Contar papers pede
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
git (`docs/adr/001-fora-de-escopo-do-mapa.md`, decisão 2). Estas colunas são o
contrato; montar as visuais é trabalho manual no Desktop.

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
- `dim_paper` inclui `data_arxiv_informada_hf`, `data_arxiv_v1` e
  `arxiv_v1_verificado_em`, além de `dias_desde_publicacao`, `tem_codigo_aberto`,
  `tem_project_page`, `faixa_upvotes_atual`, `upvotes_atual`;
- `marts/_manifest.json` registra data/hora, `run_id` e a contagem de linhas de
  cada arquivo — é como conferir no Power BI que o dado é fresco.

São 13 arquivos (um por tabela), `ponte_paper_area.parquet` e
`ponte_paper_vertente.parquet` incluídos.

No Power BI Desktop: Obter Dados → Parquet, apontar para `marts/`. Marcar
`dim_calendario` como tabela de datas e relacionar
`fato_metrica[data_snapshot] → dim_calendario[data]`,
`fato_metrica[paper_id] → dim_paper[paper_id]`,
`ponte_paper_criterio[paper_id] → dim_paper[paper_id]`,
`ponte_paper_area[paper_id] → dim_paper[paper_id]` e
`ponte_paper_vertente[paper_id] → dim_paper[paper_id]` (todas muitos-para-um, com
a armadilha de contagem descrita em *Modelo de dados* — as três pontes
multiplicam linhas). `dim_area` se relaciona duas vezes com a ponte de área, uma
por `area` e outra por `subarea`; a segunda entra como relação inativa e sobe com
`USERELATIONSHIP`, porque a mesma dimensão serve aos dois níveis.

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
   descartados existe justamente para medir a divergência — na base
   inteira, **15 dos 20 papers mais votados são `fora`** (o "13" era da base
   anterior à coleta retroativa; a janela de 90 dias do painel dá o mesmo 15).
2. **O Padrão Extraído é escrito e testado antes do veredito.** A ordem das
   propriedades no schema do Estágio B é normativa.
3. **A LLM não cria rótulo, e não propõe nenhum.** O enum é injetado do banco;
   quando nada serve, ela declara em qual dos três eixos o encaixe falhou e por
   quê, e isso vai para `tax_nao_encaixe`. A declaração de não-encaixe não recusa a triagem. Pares inválidos por
   parentesco, porém, são rejeitados na persistência e podem deixar o paper sem
   área primária até revisão.

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
├── execucao.py     orquestra os 6 estágios, a reclassificação e log_execucao
├── auditoria_arxiv.py  verificação de v1, cache e relatórios de divergência
├── taxonomia.py    validação da grade, não-encaixes, fusão, export/carga
├── guardrails.py   avisos de volume
├── doutor.py       diagnóstico
├── log.py          logging com corte de segredo
├── fontes/         clientes HF/arXiv (httpx, retry, rate limit) e modelos.py
├── llm/            cliente OpenRouter, schemas, estágios A e B
└── estagios/       coleta, enriquecimento, classificação, refresh, export
scripts/
├── run_daily.sh        pipeline diário (launchd, 07:30)
├── gerar_painel.sh     wrapper do painel (launchd, WatchPaths em _manifest.json)
├── gerar_painel.py     monta relatorios/painel.html a partir dos Parquet
├── painel_app.js       app do painel (porte do artboard da Claude Design)
├── coleta_retroativa.py  varre dias anteriores ao início do pipeline (sem LLM)
└── relatorio_massa.py    mede a grade: distribuição, checagens A e B, roteamento
prompts/            regras versionadas
config/             taxonomia_inicial.json — a grade vigente, recarregável
docs/               índice em docs/README.md
├── adr/            decisões, uma por arquivo, numeradas
├── specs/          desenhos entregues — não se reescrevem depois
├── relatorios/     medições da base (relatorio_massa.py), uma por rodada
└── tickets/        a spec quebrada em fatias, uma subpasta por spec
marts/              ← o Power BI aponta para cá
relatorios/         artefatos de leitura: painel.html
data/               o banco SQLite
```

`marts/`, `data/`, `logs/` e os demais arquivos de `relatorios/` não são
versionados. **`relatorios/painel.html` é a exceção versionada.** A diferença entre
eles: `relatorios/` e `marts/` regeneram do banco; `data/` **é** a fonte. O
`docs/relatorios/` é outra coisa e **é** versionado: cada medição de lá é a causa
registrada de uma mudança na grade, e não se regenera.

## Datas arXiv e auditoria da defasagem

A defasagem é `data_hf_daily - data_arxiv_v1`, em dias corridos.
`data_arxiv_v1` é a data de submissão inicial (`published` da entrada Atom da
API arXiv), não o horário do anúncio público. Ela é usada na auditoria e fica
disponível ao Power BI:
o box plot que a mostrava saiu do painel em 08/09/2026, e com ele as duas datas
do payload — as colunas continuam no banco e nos Parquet, que é de onde a
auditoria e o Power BI leem.

`data_arxiv_informada_hf` preserva `paper.publishedAt` do HF, que pode representar
uma revisão. `data_arxiv` permanece como alias legado desse metadado para
compatibilidade. Ambos podem mudar no refresh. A v1 é escrita separadamente,
apenas quando ausente, junto de `arxiv_v1_verificado_em`; uma revalidação
conflitante gera relatório e nunca substitui a data automaticamente.

```bash
# Consulta toda a base e escreve relatório, sem migrar ou modificar o banco:
python -m hfpapers auditar-datas-arxiv --relatorio relatorios/auditoria-arxiv.json
# Backup SQLite consistente, migração aditiva e preenchimento das v1 verificadas:
python -m hfpapers auditar-datas-arxiv --aplicar --relatorio relatorios/auditoria-arxiv.json
# Reconsulta inclusive datas já verificadas, para detectar conflitos:
python -m hfpapers auditar-datas-arxiv --revalidar
# Atualiza os artefatos após a aplicação:
python -m hfpapers export
python scripts/gerar_painel.py --force
```

A auditoria inclui defasagens negativas, positivas, zero e datas ausentes.
Resultados válidos ficam em `data/cache_arxiv_v1/`; consultas falhas são
registradas como pendentes e tentadas novamente na próxima execução.
O estágio `datas_arxiv`, habilitado no pipeline completo, verifica apenas v1
pendentes antes do export. `run --only export` e o comando `export` não acessam
arXiv. O relatório da etapa diária fica em
`relatorios/auditoria-arxiv-pendentes.json`; falhas de consulta entram nos avisos
e não impedem o export. A migração de schema nunca consulta serviços externos.

O relatório distingue divergência de metadados, conflito de revalidação e
negativo remanescente. Este último confirma a ordem das **datas registradas**,
não a ordem real dos eventos: a data HF ainda pode exigir investigação.

Na auditoria concluída em 08/09/2026, os 3.166 papers da base tinham v1
verificada, sem pendências nem defasagens negativas remanescentes. Novos papers
podem alterar essa cobertura; o relatório de cada execução é a referência.
