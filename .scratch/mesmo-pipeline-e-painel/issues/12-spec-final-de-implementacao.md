# Spec final de implementação

Type: task
Status: resolved
Blocked by: —

## Question

Escrever a spec que o mapa aponta como destino, com toda decisão já tomada nos
tickets 01–11 e nada novo a decidir. Ordem sugerida: schema e código morto
(remoção do backfill/seed, bootstrap do vocabulário) → `reclassificar --tudo`
(log_execucao, lista de falhas, congelamento da taxonomia) → rodada total e
promoção manual dos candidatos → painel (tickets 04, 05, 09, 11, critérios
visíveis) → `doutor` (regra nula passa a ser erro) → README e CONTEXT.md.

Resolvido quando: a spec existe como arquivo no repositório, cada item aponta
o ticket que o decidiu, e alguém pode implementar sem reabrir discussão.

## Answer

(2026-09-04) Escrita em **`docs/spec-mesmo-pipeline-e-painel.md`**: oito
seções — o que já está implementado (commits `bf3660c`, `6e9ba5e`), remoção
do backfill/seed com bootstrap do vocabulário, `reclassificar --tudo`, a
rodada total como checklist de operação, painel card a card com o mapa
enum → rótulo, `doutor`, README/CONTEXT.md, critérios de aceite. Cada item
cita o ticket que o decidiu. Nada ficou em aberto. Com ela, o mapa chegou ao
destino.
