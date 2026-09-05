# Plano da reclassificação total

Type: grilling
Status: resolved
Blocked by: 07, 08

## Question

Com o enum travado e o prompt aprovado na amostra, como os 482 papers vão para
o mesmo estado? Decidir:

- **Escopo**: os 482 (os 235 do pipeline também foram com regras antigas e sem
  critério) — confirmar.
- **Mecanismo**: `reclassificar --force` sobre tudo, ou um comando novo? O que
  acontece com `revisao`, `run_id`, `classificado_em`, e com `dim_ficha` e as
  pontes de área/tópico dos aprovados que virarem `fora`.
- **Taxonomia**: reclassificar tudo pelo Estágio A reabre candidatos a rótulo
  (`tax_candidato`) — congelar o vocabulário durante a rodada ou deixar
  promover?
- **De uma vez ou em lotes**: afeta a transição do painel (ver *Not yet
  specified*) e a recuperação de falha — quantos papers podem ficar pendentes
  no fim, e o que o `doutor` diz sobre eles.
- **O relatório pipeline × digest**: de onde lê cada lado agora que o veredito
  do digest não está no banco.

Resolvido quando: cada ponto acima tem uma resposta de uma linha, e o gráfico
"por que o pipeline aprova" e a spec final podem ser escritos.

## Answer

(2026-09-04, grilling em uma ronda + duas revisões da Q6.)

Fatos que pesaram: o `qwen3.8-flash` raciocina antes de responder e o estágio
3 é sequencial — A ≈ 65 s/paper, B ≈ 127 s/paper nas rodadas de hoje; a
rodada total leva **8–10 h** e custa ≈ US$ 1,0. `reclassificar` não registra
em `log_execucao`; falha do B com `--force` mantém a linha antiga intacta;
taxonomia com folga 1 (23/24 tópicos, 9/10 áreas) e 42 candidatos parados.

1. **Escopo**: os 482, sem exceção — inclusive os 6 validados hoje e os 5
   pendentes de 03/09. `revisao` +1 em todos: "revisão ≥ 2 = vocabulário novo".
2. **Mecanismo**: `reclassificar --tudo` (`selecionar(force=True)` sem filtro).
   Duas alterações no comando: **registrar a rodada em `log_execucao`** (hoje
   não registra, e o `doutor` e a trava do painel não a veem) e **imprimir no
   fim a lista de papers cujo B falhou**. `run_id` novo, `classificado_em` =
   agora; os gráficos temporais usam `data_hf_daily`, nada se desloca.
3. **Ficha e pontes**: comportamento atual do código confirmado — aprovado que
   vira `fora` perde ficha e critérios; ficha de quem segue aprovado é upsert;
   pontes de área/tópico reescritas. Sem histórico de ficha.
4. **Taxonomia**: **congelada** durante o `--tudo` — `registrar_candidato`
   grava, não promove. Promoção no meio da rodada deixaria os já classificados
   sem o rótulo. Depois: `taxonomia listar`, promover/fundir à mão, sem rerodar.
   A rodada diária continua promovendo.
5. **De uma vez**: invocação única, iniciada à mão logo após a rodada das
   07:30, painel regenerado só no fim (`gerar_painel.sh --force`). **Não há
   transição visível do painel** — a neblina correspondente fecha como
   inexistente. Falha: os que falharam no B são reprocessados com
   `reclassificar --paper`; critério de conclusão = nenhuma linha em
   `fato_triagem` com `run_id` diferente do da rodada total. Concorrência no
   estágio 3 é ganho de engenharia, fora deste mapa.
6. **Relatório pipeline × digest: morre.** Ele respondia "o prompt novo
   reproduz o digest?"; a resposta é "não, de propósito" e divergência deixou
   de ser diagnóstico. **E com ele morrem o `backfill` e o `seed/`** (revoga
   parte do ticket *O que sobra do backfill*): a API diária do HF ainda devolve
   os dias antigos (2026-08-14 → 30 itens, igual ao banco) e `run --data` já
   coleta um dia qualquer — dia antigo é dia como outro. O vocabulário de
   áreas/tópicos, único bootstrap sem outra fonte, passa a ser um arquivo
   exportado do banco atual (o do seed já está desatualizado), com um comando
   de carga inverso ao `taxonomia listar`.

**Somem**: `backfill/` inteiro, `digests.py`, `seed/` (fica no histórico do
git), `data/estado/vereditos_estagio_b.json`, `db.RUN_IDS_DIRIGIDOS`, o
veredito herdado do painel (`gerar_painel.py: justificativa_exibivel`, código
1), seções Backfill e validação do README, testes do backfill (`conftest.py:
seed_dir`). Se um dia quiser medir quanto mudou frente ao digest: consulta ad
hoc contra o `seed/` do histórico, não comando do produto.
