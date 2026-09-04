# Por que os 5 pendentes de 03/09 atravessaram a rodada de 04/09

Type: research
Status: resolved
Blocked by: —

## Question

Cinco papers de `data_hf_daily = 2026-09-03` (`2609.00196`, `2609.01936`,
`2609.00834`, `2608.30005`, `2504.15476`) estão sem linha em `fato_triagem`
depois da rodada `run-20260904-073002`. O README diz que a rodada seguinte varre
todo pendente de qualquer dia. Por que não pegou? Ler `logs/run_20260904*.log`,
`log_llm` (erro por paper) e `log_execucao` da rodada; conferir
`classificacao.selecionar`. Distinguir: falharam nas duas passadas do Estágio
B? nem foram selecionados? chegaram pelo refresh depois da classificação?

Isso importa para o mapa porque "todos seguem o mesmo pipeline, com
recuperação" só é verdade se a repescagem funciona — a reclassificação em massa
vai depender dela.

Resolvido quando: causa identificada com evidência (linhas de log), e um
veredito: bug a corrigir na implementação, ou latência esperada.

## Answer

(Pesquisa somente de leitura, 2026-09-04 — [research/08-pendentes-0309.md](../research/08-pendentes-0309.md).)

**Latência esperada, não bug.** Os 5 têm `primeiro_visto_em = 2026-09-04T07:33:11`,
o segundo exato da linha `refresh:` do log, 4 s **depois** de `classificacao:`
(07:33:07): nasceram pelo estágio 4, quando o estágio 3 já tinha fechado, e
`selecionar` não tinha como vê-los. `log_llm` não tem linha para nenhum deles;
a rodada classificou exatamente os 22 novos da coleta (`status='ok'`, sem avisos),
e às 07:30 ainda rodava o código anterior a `5d48b15`, que nem deixava pendente
por falha de B. As rodadas manuais das 08:54 foram `reclassificar --paper` sobre
outros 5 papers (os `amplo` fabricados) — dirigidas, sem `log_execucao`.
O `doutor` reporta `[ok] 5 sem veredito, todos vistos depois da ultima classificacao`.
Mesmo padrão de 03/09 (9 papers, resolvidos por `run --only classificacao,export`).
Risco lateral anotado: o corte do `doutor` usa `finalizado_em` (pós-refresh) e só
não acusa falso positivo porque refresh e fechamento caíram no mesmo segundo.

**Adendo (2026-09-04):** o achado lateral foi corrigido a pedido do usuário —
`doutor.checar_pendencias` passou a usar o último `classificado_em` da
execução como corte, com `finalizado_em` de reserva (3 testes novos em
`tests/test_doutor.py`, README atualizado). Ainda não commitado.
