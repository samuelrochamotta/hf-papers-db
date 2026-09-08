# 07: Rodada 1 e relatório de massa

**O que construir:** a base inteira — cerca de 2.600 papers — classificada na grade v1,
**só no Estágio A**, e um relatório que diz se a grade se sustenta. É o ponto em que as
sub-áreas deixam de ser hipótese e viram medida.

O relatório responde às duas checagens objetivas da spec:

- nenhuma sub-área acima de ~25% da sua área — acima disso, falta ramificar;
- nenhuma vertente abaixo de ~2% — abaixo disso, o rótulo deve ser absorvido.

*Adaptar* e *Explicar* são as candidatas conhecidas a sumir: na classificação manual dos
127 aprovados, *Medir* ficaria com cerca de 40 e *Adaptar* com 3.

A rodada usa concorrência 4, conforme o ADR 001 — é espera de rede, e divide por N.
Vale também a consequência que o ADR registra: rodada interrompida no meio deixa papers
já pagos sem triagem, com o gasto visível no log de custos mas fora do custo da
execução.

**Bloqueado por:** 05, 06.

**Status:** in progress — desbloqueado por `llm.prazo_total_s` (ver *O que destravou*)

- [x] Backup do banco tomado antes da rodada
- [x] Custo estimado apresentado antes de disparar
- [ ] Todos os papers da base com área, sub-área e vertente, incluindo os `fora`
      — a rodada foi abortada com zero chamadas concluídas; a base segue com 212
- [ ] Uma única rodada, com `run_id` único em toda a triagem
      — `run-20260908-153226` existe em `log_execucao`, mas sem triagem nenhuma
- [x] Nenhuma ficha nova gerada nesta etapa — `--so-estagio-a` é a trava, e
      `dim_ficha` continua com as 184 de antes
- [ ] Relatório com a distribuição por sub-área e por vertente, e o resultado das duas
      checagens — o gerador está pronto (`scripts/relatorio_massa.py`); falta a massa
- [ ] Relatório com a contagem de não-encaixes por eixo — idem
- [ ] Custo real conferido contra a estimativa de US$ 0,54 — a estimativa foi
      refeita e é de **US$ 1,23** para 3.166 papers (o prompt da grade facetada
      dobrou a entrada, de ~2.500 para 4.401 tokens); falta o real

## Rodada 1, tentativa 1 — abortada em 2026-09-08 15:39

`run-20260908-153226`, Estágio A apenas, concorrência 4. **Sete minutos, quatro
chamadas em voo, zero concluídas.** Abortada pela regra de ritmo (piso de 10
chamadas/min).

O culpado é o roteamento: as quatro chamadas caíram todas em **Sail Research**,
que hoje mede assim no `log_llm` do Estágio A com a grade facetada:

| Provedor | chamadas | latência média | pior |
|---|---:|---:|---:|
| Together | 84 | 2,0 s | 3,9 s |
| Sail Research | 41 | 14,6 s | 55,5 s |
| DeepInfra | 1 | 28,0 s | 28,0 s |

Uma sonda com o payload real do Estágio A, fora do pipeline, pegou Sail Research
em **195,5 s para 178 tokens de saída e zero tokens de raciocínio** — não é o modo
de falha do `effort` ignorado, é endpoint lento. Oito sondas depois, o mesmo
provedor devolvia em 5,6 a 19,3 s. A cauda é o problema, não a média.

Dois achados que sobrevivem à rodada:

1. **`llm.timeout_s` não protege desta falha.** O OpenRouter manda linhas
   `: OPENROUTER PROCESSING` enquanto o provedor pensa, e cada uma reinicia o
   read timeout do httpx. Uma chamada de 195 s passa por baixo de um teto de
   180 s sem disparar nada, e a rodada fica pendurada em silêncio.
2. **`provider.require_parameters` sozinho não escolhe endpoint bom.** Dos 23
   endpoints do `z-ai/glm-5.3-flash`, 21 anunciam saída estruturada, e o
   balanceador escolhe entre eles por preço. A decisão de fixar (ou banir)
   provedor não é deste ticket.

## O que destravou — `llm.prazo_total_s`, 2026-09-08 16:30

A preferência por `Together` **não bastou**. Uma validação de 29 papers com
`provider.order: [Together]` roteou 28 das 30 chamadas para lá, e mesmo assim
teve **uma chamada de 409,8 s** — no endpoint de melhor mediana do catálogo
(3,2 s nas outras 28). Ela sozinha consumiu 68% da parede e derrubou o ritmo
para 4,4 chamadas/min, abaixo do piso de 10 que aborta a rodada.

**A cauda não tem dono.** Atribuí-la ao Sail Research foi erro meu: o Together
produziu a pior chamada do dia. Trocar de endpoint trata a mediana, não a cauda,
porque a causa é a ausência de um teto de tempo efetivo — `llm.timeout_s` é read
timeout do httpx e o keep-alive `: OPENROUTER PROCESSING` o reinicia a cada
linha.

A correção é um prazo de ponta a ponta nosso: a chamada roda numa thread e é
abandonada aos 90 s, caindo na retentativa que já existia. O valor vem da
medição já sob `esforco_raciocinio` — em 195 chamadas, o pior caso legítimo foi
55,5 s no Estágio A e 13,8 s no Estágio B, e o valor seguinte depois de 55,5 s
era 409,8 s. O teto cai no vazio entre os dois.

Duas validações, o mesmo dia de 29 papers:

| | sem prazo (`run-...160502`) | com prazo (`run-...162127`) |
|---|---:|---:|
| chamadas | 30 | 29 |
| p50 | 2,4 s | 2,8 s |
| pior caso | **409,8 s** | **5,7 s** |
| parede | 405 s | **20 s** |
| ritmo | 4,4/min | **87,0/min** |
| custo | US$ 0,0124 | US$ 0,0114 |
| triagem | 19 `fora` | 19 `fora` |

Ressalva de leitura: **nesta rodada o prazo não chegou a ser acionado** — a cauda
simplesmente não apareceu. O que a tabela prova é que o teto não cria falso
positivo. Que ele corta de fato foi provado à parte, com o prazo baixado de
propósito contra a API real: 16 cortes, cada um com sua linha em `log_llm`
(`ErroPrazo`), e a retentativa recuperando na tentativa seguinte.

Duas consequências operacionais:

1. A chamada abandonada **continua sendo cobrada** e sua resposta é descartada
   (~US$ 0,0004). `log_llm` subestima o gasto exatamente nessas linhas, porque
   os tokens vêm na resposta que nunca foi lida. Para conferir a fatura, conte
   `erro LIKE 'ErroPrazo%'`.
2. O 6º modo de falha do OpenRouter deixa de ser silencioso: antes a chamada
   pendurada não gerava linha nenhuma.
