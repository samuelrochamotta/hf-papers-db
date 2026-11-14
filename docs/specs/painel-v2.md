# Painel v2 — especificação

Implementa o protótipo v3 aprovado em 2026-11-14 (ver ADR 007), com os ajustes
pedidos na revisão: sem textos explicativos sob os gráficos, sem o texto final
e sem a manchete do topo; uma codificação de cor no lugar de formas e
preenchimentos; um radar para classificar e comparar papers.

## Fluxo

```
dim_paper (HF Daily)
  └─ hfpapers ler ──► arXiv HTML ─► texto (sem referências, teto 320 mil car.)
                         └─► Claude Haiku 5.5 (JSON Schema prompts/leitura/esquema-v1.json)
                               └─► conferência de trechos e números (_ok)
                                     └─► leitura_texto
scripts/gerar_painel_v2.py ─► derivar (deltas, solidez, esforço, radar) ─► relatorios/painel-v2/dados.json
painel-v2/ (Svelte + ECharts 6) ─► npm run build ─► relatorios/painel-v2/{index.html, assets/}
```

## Comandos

```bash
hfpapers ler --dias 7 --limite 30          # lê os mais votados da semana
hfpapers ler --ids ids.txt --refazer       # relê uma lista
python scripts/gerar_painel_v2.py --dias 14
cd painel-v2 && npm ci && npm run build    # só quando o front-end muda
npm run dev                                # desenvolvimento, com public/dados.json
DADOS=../relatorios/painel-v2/dados.json npm run previa   # HTML único em .previa/
```

## Telas

- **Topo**: marca, período (7 dias, 14 dias, tudo), lente ativa com ×, legenda
  de cor (solidez).
- **Assinaturas**: um mini radar por paper, do mais votado ao menos votado;
  tracejado quando a leitura não basta. Passar o ponteiro acende o paper em
  todos os gráficos; clicar abre o painel.
- **Cartões** (cada um com pergunta e um número grande, sem rodapé):
  comparar papers (radar com até 3 papers e a mediana do período), onde está a
  disputa (arenas, vitórias, ruído, derrotas), quanto ganham do melhor rival
  (haltere por paper), onde os votos não têm prova (enxame votos × solidez), o
  que dá para adotar já (unidades por esforço), sobre o que se constrói e
  contra quem se mede (barras divergentes por família), o que melhora gastando
  menos (custo × ganho). Clicar numa arena, nível de solidez, degrau de esforço
  ou família aplica a lente em tudo.
- **A letra miúda**: limites admitidos, ressalvas graves e manchetes que a
  tabela não confirma.
- **Paper**: cartão (linha fixa, radar contra a mediana, comparar, células de
  resultado, régua de 7 sinais, esforço, hardware, abertura), trechos literais,
  ficha (tabelas, entidades por papel, links).

## Eixos do radar (0–100, `null` = não lido)

| Eixo | Conta |
|---|---|
| Ganho | 50 + 50·tanh(mediana do ganho relativo contra o melhor rival ÷ 10) |
| Solidez | sinais verdadeiros ÷ sinais lidos (mínimo 3 lidos) |
| Abertura | código 40%, pesos 30%, dados 20%, demo 10% × (liberado 1, prometido 0,4, só página 0,15) |
| Facilidade | (5 − esforço) × 20; nulo para panorama e estudo |
| Amplitude | 20 por benchmark com linha própria, até 100 |
| Atenção | percentil de votos no conjunto exportado |

## Pendências

- Conjunto-ouro de 100 papers para calibrar extração, solidez e esforço.
- Rodar `hfpapers ler` na máquina do pipeline (precisa de `ANTHROPIC_API_KEY`).
- Decidir quando `ler` entra no `run_daily.sh`.
