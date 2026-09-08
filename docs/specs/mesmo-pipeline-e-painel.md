# Spec: mesmo pipeline para todo paper, e o painel que decorre disso

Estado: **decidido**. Nada aqui está em aberto. Cada item cita o ticket do mapa
wayfinder (`.scratch/mesmo-pipeline-e-painel/issues/`) que o decidiu; o detalhe
e o porquê moram lá, esta spec só ordena e delimita. Glossário em `CONTEXT.md`.

Escrita em 2026-09-04. Fatos de partida: 482 papers, 477 triagens, 242 com
veredito herdado do digest (`run_id='backfill'`), 5 `fora` de rodadas normais
sem regra, 5 pendentes. Modelo `qwen/qwen3.8-flash` nos dois estágios.

> **O vocabulário desta spec foi substituído em 08/09/2026.** Onde se lê
> *tópico*, `dim_topico` ou `ponte_paper_topico`, o sistema atual tem a
> **taxonomia facetada** de `docs/specs/taxonomia-facetada.md`: área hierárquica
> (`dim_area` com `area_pai`) e vertente (`dim_vertente`, com `ordem` na ponte).
> A grade de tópicos foi removida do banco, não versionada.
>
> Cinco pontos deixaram de valer ao pé da letra e nenhum foi reescrito, porque
> reescrever spec entregue apaga a causa das decisões que vieram depois:
>
> - **§1, bootstrap do vocabulário** — "9 áreas, 23 tópicos" hoje são 10 áreas
>   raiz, 64 sub-áreas e 10 vertentes; `taxonomia exportar` grava áreas,
>   sub-áreas e vertentes, com a sub-área aninhada sob a área.
> - **§2, taxonomia congelada** — o candidato virou **não-encaixe**
>   (`tax_nao_encaixe`): o modelo constata em qual dos três eixos a grade não
>   serviu, em vez de propor um nome. `registrar_candidato`, `tax_candidato` e o
>   parâmetro `promover` não existem mais; a rodada diária também não promove.
> - **§2, o que a rodada reescreve** — "pontes de área/tópico" hoje são
>   `ponte_paper_area` (com a sub-área na chave, para admitir o par secundário de
>   mesma área) e `ponte_paper_vertente` (com a `ordem` que separa a dominante).
> - **§3, passo 5** — "promover ou fundir à mão os candidatos com quórum" hoje é
>   ler a fila com `taxonomia nao-encaixes --eixo ...`. `taxonomia fundir` perdeu
>   o parâmetro `--tipo` e passou a valer para rótulos irmãos da hierarquia.
> - **§4, painel, e §5, `doutor`** — o heatmap *Tópico × tempo* saiu do painel
>   junto com o eixo que ele media; o check de vocabulário vazio olha `dim_area`
>   e `dim_vertente`, e conta só a área raiz que tem ao menos uma sub-área.

## 0. O que já está implementado

Commits `bf3660c` e `6e9ba5e` (2026-09-04), validados em 6 papers reais, 250
testes:

- Enum de 6 regras de descarte, `regra_fora` obrigatória em todo `fora`,
  exceção do componente adotável no Estágio A — *Regra obrigatória em todo
  `fora`* (02).
- `criterios_veredito` (lista ≥ 1 de 10 critérios), veredito decorre da lista,
  `exige_acesso_interno` excludente, `decisao_fronteira` + `fronteira_contraparte`
  com validação e "refazer uma vez" — *Critério de veredito* (03), *Enum de
  critérios estrito/amplo* (06), *Prototipar o Estágio B* (07).
- Tabela `ponte_paper_criterio`, coluna `fato_triagem.fronteira_contraparte`,
  migração, Parquet novo no export.
- Prompts `regras_classificacao.md`, `estagio_a.md`, `estagio_b.md` reescritos;
  `estagio_a.max_tokens` 2400.
- `doutor.checar_pendencias` corta pelo último `classificado_em` da execução —
  *Por que os 5 pendentes atravessaram a rodada* (08).

O que segue é o que falta, na ordem de execução.

## 1. Um caminho só: remover o backfill e o seed

Ticket: *Plano da reclassificação total* (10), resposta 6, revogando parte de
*O que sobra do backfill* (01).

Dia antigo é dia como outro: a API diária do HF devolve datas passadas
(verificado em 2026-08-14: 30 itens, igual ao banco) e `run --data` já coleta
qualquer dia. Não há carga especial.

**Remover**

- `src/hfpapers/backfill/` inteiro; comando `backfill` do `__main__.py`.
- `src/hfpapers/digests.py`.
- `seed/` inteiro (fica no histórico do git). Os digests não têm leitor.
- `data/estado/vereditos_estagio_b.json` e a lógica que o escreve.
- `db.RUN_ID_BACKFILL`, `db.RUN_IDS_DIRIGIDOS` e todo `NOT IN (...)` que os
  usa (`doutor.checar_pendencias`, consultas do painel).
- No painel: `gerar_painel.py: justificativa_exibivel` código 1 ("veredito
  herdado") e o aviso correspondente em `painel_app.js` (inclusive a frase
  "o backfill não a registra" na seção 01 da aba Janela).
- Testes: `test_backfill.py`, `test_digests.py`, fixture `seed_dir` do
  `conftest.py`, e os trechos de `test_doutor.py`, `test_guardrails_taxonomia.py`,
  `test_justificativa_exibivel.py`, `test_painel_hall.py` que dependem do seed
  ou do `run_id='backfill'`. Fixtures que os testes ainda precisarem viram
  dados mínimos em `tests/fixtures/`.

**Acrescentar: bootstrap do vocabulário.** É o único dado do seed sem outra
fonte. O vocabulário vivo está no banco (9 áreas, 23 tópicos, com definições):

- `python -m hfpapers taxonomia exportar --destino config/taxonomia_inicial.json`
  grava áreas e tópicos (rótulo, definição) a partir de `dim_area`/`dim_topico`.
  Candidatos não entram.
- `python -m hfpapers taxonomia carregar <arquivo>` é o inverso, para banco
  vazio; idempotente (rótulo existente não é tocado). Substitui
  `taxonomia.carregar_seed`.
- O arquivo é versionado; o `doutor` avisa se o banco tiver vocabulário vazio.

## 2. `reclassificar --tudo`

Ticket: *Plano da reclassificação total* (10), respostas 1–5.

- Flag nova `--tudo` em `reclassificar`, exclusiva com `--data`/`--paper`:
  `selecionar(force=True)` sem filtro. Sem comando novo.
- **Registra a rodada em `log_execucao`** (`_abrir_execucao`/`_fechar_execucao`
  de `execucao.py`, hoje só usados por `run`). Vale para `--data` e `--paper`
  também: rodada dirigida deixa de ser invisível para o `doutor` e para a trava
  de `run_id` do painel.
- **Taxonomia congelada** quando `--tudo`: `registrar_candidato` grava o
  candidato e o paper, mas não promove (parâmetro `promover=False`). A rodada
  diária continua promovendo. Motivo: promoção no meio da rodada deixa os já
  classificados sem o rótulo.
- **Relatório de saída**: além da linha atual (`fora | amplo | estrito | fichas |
  pendentes | US$`), imprime a lista dos `paper_id` cujo Estágio B falhou nas
  duas passadas (já existem como avisos `estagio_b_falhou:<id>`), em formato
  colável em `reclassificar --paper`.
- Comportamento já existente, confirmado (resposta 3): aprovado que vira `fora`
  perde ficha e critérios; ficha de quem segue aprovado é upsert; pontes de
  área/tópico reescritas; `revisao` +1; `run_id` novo; `classificado_em` =
  agora. Sem histórico de ficha.
- Falha no B com linha antiga: a linha fica intacta (código atual). O critério
  de conclusão da rodada é a consulta
  `SELECT paper_id FROM fato_triagem WHERE run_id <> :run_total`
  devolver vazio, mais zero papers sem triagem.

## 3. A rodada total (operação, uma vez)

Ticket: *Plano da reclassificação total* (10), resposta 5. Sequencial, A ≈ 65 s
e B ≈ 127 s por paper com o `qwen3.8-flash`: **8 a 10 horas**, ≈ US$ 1,0.

1. Esperar a rodada diária das 07:30 terminar (`log_execucao` com
   `finalizado_em`).
2. `python -m hfpapers reclassificar --tudo` à mão, em terminal que sobreviva
   (ou `nohup`). Começando às 08:00 termina antes da rodada seguinte.
3. Para cada id da lista de falhas impressa no fim: `reclassificar --paper <id>`.
4. Verificar a consulta de conclusão da seção 2 e
   `SELECT COUNT(*) FROM fato_triagem WHERE veredito='fora' AND regra_fora IS NULL`
   = 0.
5. `taxonomia listar`; promover ou fundir à mão os candidatos com quórum
   (`taxonomia fundir` existe; `promover` ganha comando se ainda não tiver).
   Sem rerodar.
6. `python -m hfpapers export` e `scripts/gerar_painel.sh --force`. O painel
   só é regenerado aqui, por isso **não há transição visível**.

Depois da rodada, todo paper tem `revisao ≥ 2`; a distinção recente/backfill
deixa de existir nos dados, não só no código. *(A primeira metade desta frase
está errada — ver a errata da §9; a marca da rodada é o `run_id`.)*

## 4. Painel

Tickets: *Cores e formas dos gráficos* (04), *Como o voto amadurece* (05),
*Prototipar a curva normalizada* (09), *Gráfico "por que o pipeline aprova"*
(11), *Critério de veredito* (03). Arquivos: `scripts/gerar_painel.py`
(monta `DADOS` a partir dos Parquet), `scripts/painel_app.js` (desenha).
Consultar a skill `dataviz` ao implementar.

**Dados novos em `DADOS`** (`gerar_painel.py`): critérios por paper
(`ponte_paper_criterio.parquet`), `fronteira_contraparte` da triagem, e a série
de votos por paper já existente para a curva. Mapa enum → rótulo legível em
português, um só, usado pela ficha e pelo gráfico novo:

| enum | rótulo |
|---|---|
| `padrao_arquitetural` | padrão arquitetural |
| `artefato_aberto` | artefato aberto |
| `invalida_pratica` | invalida prática corrente |
| `vulnerabilidade` | vulnerabilidade |
| `tecnica_de_avaliacao` | técnica de avaliação |
| `benchmark` | benchmark |
| `panorama` | panorama |
| `framework_conceitual` | framework conceitual |
| `principio_sem_o_como` | princípio sem o como |
| `exige_acesso_interno` | exige acesso interno |

As 6 regras de descarte ganham rótulos no mesmo mapa (`rotuloRegra` hoje só
trata a nula).

**Cores** (04): verde `#4ec07a` = aprovado em todo o painel — linha da Taxa de
aprovação, escala de aprovação do heatmap, cor da matriz. Amarelo `ACCENT`
volta a ser só link/destaque. Estrito azul, amplo laranja, como hoje.

**Seção "Vocabulário e cruzamentos"**

- Heatmap Tópico × tempo, uma escala por vista (04): `volume` sequencial azul;
  `crescimento` divergente (vermelho caiu, cinza estável, verde cresceu);
  `aprovação` sequencial verde.
- Matriz área primária × secundária vira matriz de bolhas (04): cor = taxa de
  aprovação, tamanho = total. Grande e verde = muitos e muito aprovados; grande
  e cinza = muitos e poucos.

**Seção "Regras do corte"**

- "Onde o pipeline corta" (Pareto) sem a linha do acumulado (04). Cada barra
  com rótulo "n · % dos descartados". A barra "regra não registrada" continua
  no código, mesmo tendendo a zero.
- Card novo **"Por que o pipeline aprova"** (11), logo depois do Pareto, mesmo
  tamanho: barras horizontais, uma por critério, ordenadas por total,
  **empilhadas** por veredito do paper (estrito verde escuro, amplo verde
  claro); separador fino entre o bloco dos critérios de estrito e o dos de
  amplo. **Contagem por ocorrência**: paper com dois critérios conta em dois;
  subtítulo traz o total de aprovados. Clique na barra filtra o painel como o
  Pareto faz.

**Seção "Atenção e adoção"**

- "Como o voto amadurece" vira **uma curva normalizada** (05, 09): eixo x =
  dias desde `data_hf_daily`, eixo y = % do voto final, escala linear 0–100%.
  Mediana com **uma** faixa P25–P75 atrás. **Voto final** = último snapshot do
  paper; só entram papers com idade ≥ 14 dias (hoje 185). Linha vertical
  tracejada no primeiro dia em que a mediana cruza 90%, rótulo "estabiliza por
  volta do dia +N". Sem separação por veredito, sem log. A lista lateral
  "maior velocidade recente" continua.

**Ficha do paper** (03, 11)

- Linha do veredito: "ESTRITO · artefato aberto + benchmark" com os rótulos do
  mapa acima.
- Quando `decisao_fronteira`: "fronteira: quase <rótulo da contraparte>" ao
  lado.
- Justificativa sempre exibida (código 1 morre com o backfill).

## 5. `doutor`

- Check novo em `checar_banco`: `fora` com `regra_fora` nula é **erro**, não
  aviso (depois da rodada total o número certo é zero; o schema já impede
  novos).
- Check novo: vocabulário vazio (`dim_area` ou `dim_topico` sem linhas) é
  aviso apontando `taxonomia carregar`.
- Remover a exclusão de `RUN_IDS_DIRIGIDOS` do corte de pendências (seção 1).
- O `doutor` passa a ver rodadas de `reclassificar` porque elas entram em
  `log_execucao` (seção 2); nenhum ajuste extra.

## 6. README e `CONTEXT.md`

README: apagar a seção **Backfill** e as menções ao `seed/` e à validação;
em **Comandos**, `reclassificar --tudo` e `taxonomia exportar|carregar`;
em **Pipeline**, um parágrafo "dia antigo é `run --data`"; em **Regras de
classificação**, já atualizado; em **Painel**, os cards novos e o verde;
em **Modelo de dados**, `revisao ≥ 2` como marca da rodada total; em
**Estrutura**, remover `backfill/`, `digests.py`, `seed/`, adicionar
`config/taxonomia_inicial.json` e `docs/`.

`CONTEXT.md`: já reflete o estado final (verbetes *Reclassificação total*,
*Dia antigo*, *Digest*). Só revisar depois da implementação se algum termo
novo aparecer no código.

## 7. Aceite

- `pytest` verde, sem nenhum teste lendo `seed/`.
- `grep -rn "backfill\|seed" src scripts README.md` devolve só o glossário
  histórico do `CONTEXT.md`, se tanto.
- Após a rodada total: zero papers com `run_id` diferente do da rodada; zero
  `fora` sem regra; zero papers sem triagem; `doutor` sem erro.
- Painel gerado sem exceção; os seis cards alterados/novos aparecem com dado
  real; nenhuma frase sobre "veredito herdado" ou "backfill".

## 8. Fora de escopo (mapa)

Rubrica com pontuação; mudanças no Power BI além das colunas novas dos
Parquet; concorrência no estágio 3 para encurtar a rodada total.

## 9. Errata (pós-implementação, 05/09/2026)

Duas correções de fato levantadas pela implementação. **Nenhuma decisão desta
spec muda**; o que muda é uma afirmação que a medição desmentiu e um item que
deixou de estar fora de escopo.

- **§3 e §6 — "`revisao ≥ 2` como marca da rodada total" está errado.**
  `classificacao._gravar_triagem` faz `revisao = (row["revisao"] + 1) if row
  else 1`, e as 242 linhas de veredito importado (`run_id = 'backfill'`) estão
  hoje em `revisao = 0` — nunca passaram pela classificação, coerente com a
  definição do `CONTEXT.md`. A rodada total as leva a **1**, não a 2, e um
  filtro `revisao ≥ 2` deixaria de fora justamente as linhas antigas que a
  rodada veio consertar (valeria para 235 das 482 linhas). **A marca da
  rodada é o `run_id` compartilhado** — que é o que a própria §2 já usa como
  critério de conclusão e o que `execucao.conferir` implementa. O código está
  certo; a frase da §3 é que estava errada. Distribuição medida em 04/09/2026:
  242 linhas com `revisao = 0`, 224 com 1, 9 com 2, 2 com 3.
- **§8 — "concorrência no estágio 3" foi revogada.** O item saiu de fora de
  escopo e foi implementado; a decisão está no
  `docs/adr/001-fora-de-escopo-do-mapa.md` (decisão 3), que também mantém fora
  os outros dois itens da §8.

### 9.1 Execução da §3 (07/09/2026)

A rodada total foi executada: `run-20260907-182217`, 516 papers, **47 minutos**
com `--concorrencia 4`, **US$ 0,21**. Resultado: 346 `fora`, 43 amplo, 127
estrito, 170 fichas, zero pendentes. O aceite da §7 fechou inteiro — um `run_id`
só em toda a `fato_triagem`, zero `fora` sem regra, zero aprovado sem critério,
`doutor` com código 0.

Duas notas de fato:

- **O modelo teve de mudar para a rodada acontecer.** O `qwen/qwen3.8-flash` da
  §0 tem **um único provider** no OpenRouter (Alibaba, pool compartilhado) e
  passou 07/09 em 429 upstream: a rodada diária levou 10h30 para 19 papers e
  falhou em 14; a rodada total, medida com `--concorrencia 4`, fez 1 paper em
  3,5 min e falhou em 3. Os dois estágios voltaram ao `z-ai/glm-5.3-flash`
  (24 endpoints, roteamento que se espalha sozinho), commit `2df77c5`. As
  estimativas de tempo e custo da §3 (8–10 h, ≈ US$ 1,0) foram feitas sobre o
  qwen e não descrevem mais a operação.
- **A distribuição de `revisao` confirmou a errata acima**, em dado e não em
  leitura de código: depois da rodada, 245 linhas em 1, 248 em 2, 21 em 3, 2 em
  4 — nenhuma em 0. As 242 importadas chegaram a 1, exatamente como previsto, e
  o filtro `revisao ≥ 2` teria perdido as 245 primeiras.
