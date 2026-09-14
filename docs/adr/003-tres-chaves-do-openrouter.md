# ADR 003 — Três chaves que existem por causa do OpenRouter

- **Data**: 2026-09-13
- **Estado**: aceito
- **Contexto**: `config.yaml` (seção `llm`), `src/hfpapers/llm/`, `docs/relatorios/` (roteamento por provedor)

## Decisão

### 1. `llm.prazo_total_s` — o teto que o `timeout_s` não é

`llm.timeout_s` é read timeout do httpx: conta o tempo desde o último byte
recebido. O OpenRouter manda linhas de keep-alive (`: OPENROUTER PROCESSING`)
enquanto o provedor pensa, e **cada uma reinicia esse relógio**. Uma chamada
pode ficar minutos além do `timeout_s` **sem erro, sem retentativa e sem linha
em `log_llm`**. A rodada fica pendurada em silêncio, e a única evidência é o
ritmo caindo.

`prazo_total_s` é um prazo de ponta a ponta nosso: a chamada roda numa thread
e é abandonada ao estourar, caindo na retentativa que já existia. O valor deve
ser calibrado pela distribuição de latência do modelo em uso: acima do pior
caso legítimo, abaixo da cauda patológica. `0` desliga.

Duas consequências para quem confere a fatura: a chamada abandonada **continua
sendo cobrada** e sai com uso zero, porque os tokens vinham na resposta que
nunca foi lida. `log_llm` **subestima** o gasto exatamente nessas linhas.
Conte-as com `erro LIKE 'ErroPrazo%'`.

Efeito colateral na operação: acima de `--concorrencia 1`, o Ctrl+C só age
quando as chamadas em voo terminam, ou seja
`llm.retry.tentativas × llm.prazo_total_s + backoff` por estágio, o dobro se o
paper já estiver no Estágio B. Espere; kill no meio de uma gravação é o único
jeito de corromper a rodada.

### 2. `log_llm.provedor` — a coluna sem a qual a lentidão não tem réu

O OpenRouter roteia entre endpoints do mesmo modelo, e eles não se comportam
igual: a média e a cauda de latência variam por ordem de grandeza entre um e
outro. Sem a coluna, "a rodada ficou mais lenta" é uma frase sem sujeito. Com
ela, o relatório de massa sai por provedor e a cauda ganha dono. Ou não ganha,
o que é informação igual: quem morre antes de responder não informa quem era,
e essas chamadas ficam numa linha *(não registrado)* em vez de acusarem um
inocente.

Foi essa coluna que mostrou que trocar de endpoint trata a mediana e não a
cauda: a pior chamada observada saiu do endpoint de melhor mediana. Por isso a
defesa contra a cauda é o item 1, não um filtro de provedor.

### 3. `llm.esforco_raciocinio` — porque alguns modelos raciocinam de qualquer jeito

Alguns modelos raciocinam de forma obrigatória: `reasoning.enabled: false`
volta HTTP 400. Sem limite, o rascunho de raciocínio pode ser várias vezes
maior que o JSON de saída, e a latência sobe na mesma proporção. Passar
`reasoning.effort` corta esse rascunho em uma ordem de grandeza **sem mexer na
classificação**: a concordância entre dois níveis de esforço é maior que a
auto-concordância do modelo com ele mesmo, então o esforço não é onde a grade
perde precisão.

## Consequências

- As três chaves ficam. Remover `prazo_total_s` reabre o modo de falha
  silencioso do item 1; remover `provedor` deixa a lentidão sem diagnóstico;
  remover `esforco_raciocinio` multiplica latência e custo em modelos de
  raciocínio obrigatório.
- A estimativa de custo do `--dry-run` é confiável, porque custo escala com
  token; a estimativa de tempo não é, porque tempo escala com o endpoint que o
  OpenRouter sortear.
- `custos --mes` lê `log_llm` e é o número da fatura; `log_execucao.custo_usd`
  conta só o que virou triagem. Eles não batem por desenho.
- **Modelo com um único provedor é risco operacional, não detalhe de
  catálogo.** Um endpoint só, quando entra em 429, para a rodada inteira sem
  alternativa de roteamento. Antes de trocar o modelo de qualquer estágio,
  olhe `GET /api/v1/models/<id>/endpoints`.
- Ao trocar de modelo, recalibrar os três: a distribuição de latência, o
  conjunto de endpoints e o comportamento de raciocínio mudam juntos.