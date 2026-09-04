# Plano da reclassificação total

Type: grilling
Status: open
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
