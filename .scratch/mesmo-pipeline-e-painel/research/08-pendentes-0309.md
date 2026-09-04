# Por que os 5 pendentes de 03/09 atravessaram a rodada de 04/09

Ticket: [issues/08](../issues/08-por-que-os-5-pendentes-atravessaram-a-rodada.md).
Pesquisa somente de leitura em 2026-09-04 sobre `data/hfpapers.db`
(aberto com `?mode=ro`), `logs/run_2026-09-04_073000.log`, `logs/hfpapers.jsonl`,
o código em `src/hfpapers/` e o histórico git.

**Veredito (uma linha): latência esperada — os 5 nasceram pelo refresh (estágio 4)
às 07:33:11, quatro segundos depois de o estágio 3 fechar (07:33:07); nunca foram
selecionados, e nenhuma rodada de classificação sem escopo rodou desde então.**

## Causa

Hipótese (c) do ticket. O HF acrescentou os 5 papers ao daily de 2026-09-03
depois da coleta daquele dia. Quem os encontrou foi o refresh da rodada
`run-20260904-073002`, que reconsulta as 16 datas quentes e grava pelo caminho
da coleta (`refresh._atualizar_datas` → `coleta.gravar_itens`, que carimba
`primeiro_visto_em = db.agora()` no upsert). Como o refresh é o estágio 4 e a
classificação o 3 (`execucao.rodar`, ordem `ESTAGIOS`), na hora em que
`classificacao.selecionar(conn, data=None, force=False)` rodou eles ainda não
existiam em `dim_paper` — não havia o que selecionar.

Desde então nenhuma rodada varreu pendentes: as cinco execuções manuais das
08:54 foram `reclassificar --paper <id>` (força `ids=[paper], force=True`),
dirigidas a um paper cada, e o `backfill` das 08:55 só olha o `seed/`.
A próxima varredura sem escopo é o `run` diário de 05/09 às 07:30 (ou um
`run --only classificacao,export` manual), e `selecionar` sem `--data` pega
todo pendente de qualquer dia.

Hipóteses descartadas:

- (a) falhou nas duas passadas do Estágio A/B — **não**. `log_llm` não tem
  nenhuma linha para os 5 ids. Além disso, às 07:30 rodou o código **anterior**
  ao commit `5d48b15` (08:53:40, "falha no Estagio B nao fabrica mais veredito
  amplo"): naquela versão falha de B gravava `amplo` (nunca deixava pendente) e
  falha de A gerava aviso `estagio_a_falhou` + `status = 'parcial'`. A rodada
  fechou `status = 'ok'`, `avisos = '[]'`. A linha de log das 07:33:07 ainda
  tem o formato antigo (sem "N pendentes"), o que confirma a versão que rodou.
- (b) selecionados e excluídos por `selecionar` — **não**. `selecionar` só
  filtra por `fato_triagem` (e por `data`/`ids` quando passados); não olha
  `enriquecido_em`, abstract, nem data. Os 5 têm `abstract` e `ai_summary`
  preenchidos. Eles simplesmente não estavam na tabela ainda.
- (d) outra causa — nada encontrado.

## Evidência

### 1. Os 5 nasceram no refresh, depois da classificação

```sql
SELECT paper_id, data_hf_daily, primeiro_visto_em, enriquecido_em
FROM dim_paper WHERE paper_id IN ('2609.00196','2609.01936','2609.00834','2608.30005','2504.15476');
-- 2504.15476 | 2026-09-03 | 2026-09-04T07:33:11 | NULL
-- 2608.30005 | 2026-09-03 | 2026-09-04T07:33:11 | NULL
-- 2609.00196 | 2026-09-03 | 2026-09-04T07:33:11 | NULL
-- 2609.00834 | 2026-09-03 | 2026-09-04T07:33:11 | NULL
-- 2609.01936 | 2026-09-03 | 2026-09-04T07:33:11 | NULL
```

`logs/run_2026-09-04_073000.log` (linhas 9–10):

```
07:33:07 INFO    classificacao: 17 fora, 1 amplo, 4 estrito, 5 fichas, US$ 0.1369
07:33:11 INFO    refresh: 16 datas quentes, 0 mornas, 481 papers, 0 enriquecidos
```

`primeiro_visto_em` (07:33:11) é o segundo exato do `refresh:` e é posterior à
última chamada LLM da rodada:

```sql
SELECT (SELECT MAX(criado_em) FROM log_llm WHERE run_id='run-20260904-073002') ultima_llm,
       (SELECT MIN(primeiro_visto_em) FROM dim_paper WHERE primeiro_visto_em > '2026-09-04T07:31') primeiro_refresh,
       (SELECT finalizado_em FROM log_execucao WHERE run_id='run-20260904-073002') finalizado;
-- 2026-09-04T07:33:07 | 2026-09-04T07:33:11 | 2026-09-04T07:33:11
```

`enriquecido_em` nulo é o mesmo sintoma descrito no README ("Papers que chegam
pelo refresh"): o enriquecimento (estágio 2) também roda antes do refresh.
`fato_metrica` dos 5 só tem `data_snapshot = 2026-09-04, origem = 'daily'`.

### 2. A classificação da rodada cobriu exatamente os 22 novos da coleta

```sql
SELECT run_id, COUNT(*) n, COUNT(DISTINCT paper_id) papers, SUM(erro IS NOT NULL AND erro != '') erros
FROM log_llm WHERE run_id='run-20260904-073002';
-- run-20260904-073002 | 32 | 22 | 3

SELECT COUNT(*) FROM fato_triagem WHERE run_id='run-20260904-073002';   -- 22
SELECT COUNT(*) FROM log_llm WHERE paper_id IN ('2609.00196','2609.01936','2609.00834','2608.30005','2504.15476');  -- 0
```

Log (linha 4): `07:30:03 INFO 2026-09-04: 23 coletados, 22 novos`; 17+1+4 = 22.
Os 3 erros de `log_llm` (429 em `2609.01507` B; resposta cortada em
`2609.04131` e `2609.04199` A) foram resolvidos pelo retry interno — os três têm
linha em `fato_triagem` na mesma rodada. Contagem dos Parquet no log confirma:
`dim_paper` 455 → 482 (+27 = 22 novos + 5 do refresh), `fato_triagem`
455 → 477 (+22).

### 3. Qual código rodou às 07:30

```
$ git log --format='%h %ci %s' -- src/hfpapers/estagios/classificacao.py
5d48b15 2026-09-04 08:53:40 -0300 fix(classificacao): falha no Estagio B nao fabrica mais veredito amplo
3c6aaf9 2026-08-26 21:47:00 -0300 feat: pipeline de dados ...
$ git show 3c6aaf9:src/hfpapers/estagios/classificacao.py   # linhas 235-247
        except ErroLLM as e:
            log.error("estagio B falhou em %s: %s", paper.paper_id, e)
            ...
            _gravar_triagem(conn, paper_id=paper.paper_id, veredito="amplo", ...
```

A segunda passada do Estágio B e o "N pendentes" no log só existem a partir de
`5d48b15`; a linha `classificacao:` das 07:33:07 não tem "pendentes" — versão
antiga. `selecionar` é idêntico nas duas versões.

### 4. As rodadas manuais das 08:54 eram dirigidas a um paper cada

```sql
SELECT run_id, GROUP_CONCAT(paper_id) FROM fato_triagem WHERE run_id LIKE 'run-20260904-0854%' GROUP BY 1;
-- run-20260904-085410 | 2608.21832   (revisao 2)
-- run-20260904-085423 | 2608.19269   (revisao 2)
-- run-20260904-085432 | 2608.28476   (revisao 2)
-- run-20260904-085439 | 2608.29613   (revisao 2)
-- run-20260904-085451 | 2608.29847   (revisao 2)
```

São os cinco `amplo` fabricados que o commit `5d48b15` cita, refeitos com
`reclassificar --paper` (`src/hfpapers/__main__.py`, l. 152–176:
`selecionar(conn, ids=[paper], force=True)`). Esse comando não chama
`execucao.rodar` nem grava `log_execucao` (a tabela tem 17 linhas, as mesmas
do `fato_execucao.parquet` das 07:33). Portanto não é "rodada que varre
pendentes" nem move o corte do `doutor`.

### 5. Precedente idêntico em 03/09

```sql
SELECT p.paper_id, p.data_hf_daily, p.primeiro_visto_em, t.run_id
FROM dim_paper p LEFT JOIN fato_triagem t USING(paper_id)
WHERE p.primeiro_visto_em LIKE '2026-09-03T09:23%';
-- 9 papers, todos primeiro_visto_em = 2026-09-03T09:23:23 (segundo do "refresh:" de 03/09),
-- todos classificados por run-20260903-153101 (run --only classificacao,export manual, 15:31)
```

Mesmo mecanismo, resolvido por uma varredura manual no mesmo dia — o que o
README já documenta ("Em 2026-09-03 eram 9 papers de 455").

## O que o `doutor` diz hoje

```
$ python -m hfpapers doutor --sem-rede
[ok]    triagem   5 sem veredito, todos vistos depois da ultima classificacao (entram na proxima rodada)
```

`checar_pendencias` (`src/hfpapers/doutor.py`) compara `primeiro_visto_em`
com o corte = `MAX(finalizado_em)` da última execução que classificou alguém e
não é dirigida (`run-20260904-073002`, `2026-09-04T07:33:11`). `visto < corte`
é falso (são iguais), então os 5 caem em "na fila". Leitura correta.

Observação lateral (não é a causa deste ticket, mas é um risco latente do
diagnóstico): `finalizado_em` é carimbado em `_fechar_execucao`, **depois** do
refresh, e `primeiro_visto_em` é carimbado por data dentro do loop do refresh.
Hoje os dois caíram no mesmo segundo (07:33:11; em 03/09, 09:23:23). Num
refresh que demore mais de 1 s entre a primeira data gravada e o fechamento,
papers que nunca tiveram chance seriam acusados como "atrasados" — falso
positivo do `doutor`, não falha da repescagem. Um corte mais honesto seria o
fim do estágio 3 (por exemplo, `MAX(log_llm.criado_em)` da execução, ou um
carimbo próprio do estágio), não o fim da rodada.

## Veredito

**Latência esperada**, por desenho: refresh (4) roda depois da classificação
(3); paper que o HF acrescenta a um dia passado nasce sem triagem e é
repescado pela próxima varredura sem escopo (`run` diário de 05/09 07:30, ou
`run --only classificacao,export` agora). Nada a corrigir na repescagem.

Para o mapa: "todos seguem o mesmo pipeline, com recuperação" continua
verdadeiro. A reclassificação em massa pode contar com `selecionar` — desde que
seja disparada como varredura sem `--paper`/`--data` (ou com `--force` sobre o
conjunto todo), porque só essa forma alcança quem nasceu pelo refresh.

Melhoria opcional, fora deste ticket: trocar o corte do `doutor` de
`finalizado_em` para o fim do estágio 3, eliminando o falso positivo descrito
acima.
