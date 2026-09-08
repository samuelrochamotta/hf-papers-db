# Tickets — Taxonomia facetada

Quebra de `../spec-taxonomia-facetada.md` em fatias verticais. Cada arquivo é um
ticket; a numeração segue a ordem de dependência.

```
01 grade v1 carregavel  ──┐
                          ├─> 02 area hierarquica ──> 03 vertente ──┬──> 04 nao-encaixe ──┐
                          │                                         │                     │
                          │                                         └─────────────────────┴──> 05 contracao ──┐
                          │                                                                                   ├──> 07 rodada 1 ──> 08 grade v2 ──> 09 rodada 2 ──> 10 docs
06 coleta retroativa ─────┴───────────────────────────────────────────────────────────────────────────────────┘
```

**01 e 06 podem começar imediatamente e em paralelo.** O caminho crítico passa por
01 → 02 → 03 → 04 → 05 → 07 → 08 → 09 → 10; a coleta retroativa é a única ramificação
que corre por fora.

O ticket **08 é o ponto de decisão humana**: a grade v1 é hipótese, e só a medição do
ticket 07 diz quais sub-áreas e vertentes sobrevivem.
