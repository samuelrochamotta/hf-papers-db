# 10: Documentação

**O que construir:** o repositório passa a descrever o sistema que ele de fato tem. O
modelo de dados documenta as facetas novas e a hierarquia; a spec sai de *proposta* para
*implementada*, com os números reais no lugar das estimativas; e o registro de como o
diagnóstico deve se comportar acompanha a grade nova.

Vale documentar também o que **não** foi feito e por quê, porque essas ausências são
decisões: o corte por vertente no painel, o versionamento da taxonomia, e a terceira
faceta de domínio de aplicação — avaliada e recusada porque o único domínio recorrente
na base é código, e ele já cai em Harness & orquestração.

Se a rodada 1 tiver derrubado alguma decisão do desenho — a lista de nove vertentes é a
candidata —, o registro dessa mudança de rumo vale um ADR próprio.

**Bloqueado por:** 09.

**Status:** done

- [x] O modelo de dados documenta área hierárquica, sub-área, vertente e ordem —
      README, *Modelo de dados* → *A taxonomia facetada*: a tabela de tabelas passa a
      explicar `dim_area.area_pai`, `dim_vertente` e as duas pontes, e uma tabela nova
      dá as três decisões de schema com a razão de cada uma (por que a sub-área entra
      na chave primária da ponte de área, por que a `ordem` existe). `CONTEXT.md` ganha
      a seção *Taxonomia*, com Grade, Faceta, Área/sub-área, Par, Vertente e
      Não-encaixe no formato do glossário
- [x] A spec marcada como implementada, com custo e tempo reais medidos —
      `docs/specs/taxonomia-facetada.md` sai de `proposta` para **implementada em
      2026-09-08**, com a tabela de previsto contra medido no cabeçalho: base 3.166
      (previa ~2.600), 64 sub-áreas (previa ~45), 10 vertentes (previa 9 e a perda de
      duas), **US$ 3,30 de fatura** (previa ~US$ 1,35) e **1,54 h de máquina** (previa
      ~3 h)
- [x] A distribuição final por área, sub-área e vertente registrada —
      `docs/relatorios/massa-grade-v2.md` é a medição completa e continua sendo a fonte; o
      README ganha o retrato de leitura (cobertura, áreas maiores, vertentes maiores,
      fila de revisão) e o resultado das duas checagens, que **falham** e estão
      registradas como pendência do ADR 002
- [x] As três exclusões de escopo documentadas com a razão de cada uma — README,
      seção *O que ficou de fora, e por quê*, com a razão inteira; o *Out of Scope*
      da spec aponta para lá em vez de repetir, porque uma razão só tem uma casa e
      duas cópias divergem. Duas ganharam evidência da medição: o corte por vertente
      (*Baratear* caiu de 33,6% para 16,6% entre a v1 e a v2, então um filtro feito na
      v1 estaria hoje errado no rótulo mais frequente da grade) e a terceira faceta
      (as famílias de não-encaixe pediram **área**, nenhuma pediu domínio)
- [x] Nenhuma referência ao vocabulário de tópicos permanece na documentação — sete
      correções no README (o `--tipo topico` que quebrava o comando copiado, o
      `dim_topico` do `doutor`, o heatmap que não existe mais, a linha de filtros do
      painel, duas linhas do modelo de dados e o texto de `taxonomia exportar`).
      **O que não foi mexido, de propósito**: o corpo da `spec-mesmo-pipeline-e-painel`
      e o *Problem Statement* da `spec-taxonomia-facetada` — as duas descrevem a grade
      de tópicos porque ela é a **causa registrada** das decisões que vieram depois, e
      reescrevê-las apagaria o porquê. As duas ganharam banner de leitura dizendo o
      que deixou de valer, ponto a ponto. Idem os tickets 01, 03, 04 e 05 (registro do
      que foi feito), os testes que provam que a grade antiga saiu do banco, e o código
      de migração em `db.py`

## O ADR que a rodada 1 tornou devido

`docs/adr/002-a-lista-de-vertentes.md`. A lista de nove vertentes caiu, e de forma
que o desenho não previu: ele esperava **perder** *Adaptar* e *Explicar*, e a grade
**ganhou** `Treinar`. *Explicar* ficou em 6,3% na v1, com folga; quem reprovou foi
*Especificar* (1,5%), que a spec não cita. O ADR registra os três achados — a previsão
errada, os 12 de 13 não-encaixes que pediram o verbo por extenso, e o efeito medido na
rodada 2 (`Treinar` nasce com 45,3%, `Baratear` cai de 33,6% para 16,6%, o não-encaixe
de eixo `vertente` desaba de 13 registros para 2).

## A pendência que este ticket declara e não resolve

A regra 3 do ticket 08 foi suspensa por decisão de coordenação, com o compromisso
escrito de que *"se Especificar continuar abaixo de 2% na rodada 2, ela é absorvida sem
mais discussão"*. **A rodada 2 respondeu: continuou (1,1%) e arrastou *Adaptar* junto
(1,2%).** A razão 3 da suspensão — "o denominador vai mudar de qualquer jeito" — estava
certa quanto ao fato e errada quanto à conclusão: o denominador mudou muito e nenhuma
das duas se recuperou.

Fica documentado como a primeira decisão de uma v3, na seção *Pendência declarada* do
ADR 002. **A grade não foi alterada por este ticket**: absorver reescreve pontes e tira
rótulo do enum do Estágio A, o que exige uma rodada de reclassificação, e o ticket 10 é
documentação.

## Infraestrutura desta série que não estava documentada

Três chaves existiam só em comentário de `config.yaml` e em nada mais. O README ganhou
*Três chaves que existem por causa do OpenRouter*, que aponta para a calibração em vez
de duplicá-la:

- **`llm.prazo_total_s`** e o 6º modo de falha: `llm.timeout_s` é read timeout do httpx
  e o keep-alive `: OPENROUTER PROCESSING` o reinicia a cada linha, então uma chamada de
  409,8 s atravessa um teto de 180 s sem erro, sem retentativa e sem linha em `log_llm`.
- **`log_llm.provedor`**: sem ela, "a rodada ficou 9x mais lenta" não tem sujeito. Foi
  ela que mostrou que a pior chamada do dia saiu do endpoint de melhor mediana.
- **`llm.esforco_raciocinio`**: o GLM 5.3 flash raciocina de forma obrigatória, e o
  `effort` corta a latência 14x sem mexer na classificação. Os 82% de auto-concordância
  dessa medição são a origem do ~19% de instabilidade intrínseca da grade.
