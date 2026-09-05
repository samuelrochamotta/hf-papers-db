# O que sobra do backfill

Type: grilling
Status: resolved
Blocked by: —

## Question

Se todo paper passa a ter o veredito do pipeline, a importação do veredito do
digest morre. O que sobra do comando `backfill` e do `seed/`?

## Answer

(Decidido na cartografia, 2026-09-04.)

`backfill` vira só **carga de papers**: lista (união das três fontes do seed) e
hidratação do HF. Nada de veredito: o paper entra sem linha em `fato_triagem`
e o estágio 3 da rodada seguinte o classifica como qualquer paper novo.

O veredito do digest **sai da `fato_triagem`**. Ele continua existindo no
`seed/` e no relatório `validacao_backfill.md` (pipeline × digest), que segue
como instrumento de auditoria de prompt — onde ele passa a ler cada lado ainda
está em *Not yet specified*.

Consequências: `run_id='backfill'` deixa de existir em `fato_triagem`;
`db.RUN_IDS_DIRIGIDOS` e o código de "veredito herdado" do painel
(`gerar_painel.py: justificativa_exibivel`, código 1) viram código morto a
remover; `data/estado/vereditos_estagio_b.json` perde a razão de existir.

### Adendo (2026-09-04, ticket *Plano da reclassificação total*)

Revisado: o `backfill` **não vira carga — morre**, e o `seed/` sai do
repositório. Motivo: a API diária do HF devolve os dias antigos e `run --data`
já os coleta; o relatório pipeline × digest morreu junto com sua pergunta. O
vocabulário de áreas/tópicos ganha um arquivo de bootstrap exportado do banco.
Detalhe no ticket 10, resposta 6.
