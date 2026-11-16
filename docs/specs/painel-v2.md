# Painel v2 — especificação

Implementa o protótipo v3 aprovado em 2026-11-14 (ver ADR 007), com os ajustes
pedidos na revisão: sem textos explicativos sob os gráficos, sem o texto final
e sem a manchete do topo; uma codificação de cor no lugar de formas e
preenchimentos; um radar para classificar e comparar papers.

## Fluxo

```
dim_paper (HF Daily)
  └─ hfpapers ler ──► arXiv HTML ─► texto (sem referências, teto 320 mil car.)
                         └─► Claude Haiku 5.5 pelo OpenRouter (JSON Schema prompts/leitura/esquema-v1.json)
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

Três vistas, com a barra fixa no topo (marca, vistas, período e tema) e uma
linha de recorte embaixo dela (quantos papers, quantos na fila, intervalo de
datas, menus de filtro Arena, Prova, Adoção e Família, e um chip removível por
filtro ligado, com "Limpar"). Os filtros sempre se somam. Vista, período,
filtros, busca, ordem, paper aberto e comparação vão para o endereço
(`?vista=panorama&lente=ar:codigo&lente=sol:forte&paper=…&comparar=…`).
No celular as vistas vão para uma barra de abas embaixo.

1. **Papers** (abre aqui, por votos): a lista responde "o que vale ler hoje".
   Cada linha tem a marca de prova (cor mais preenchimento, decisão 10), o
   título, a frase do problema segundo o modelo (em itálico), votos, prova,
   ganho, esforço de adoção e o que foi liberado; papers na fila aparecem com
   a marca vazia e o link para o arXiv. Busca e ordem por votos, ganho ou
   prova; a linha da mediana de votos do período corta a lista. Clicar abre o
   paper; o `+` põe na comparação.
2. **Panorama**: sete quadros em três grupos. Resultados: onde está a disputa
   (arenas, com quem mais vence pela taxa de vitória) e quanto ganham do
   melhor rival. Prova: onde há votos sem prova e o que a letra miúda admite.
   Adoção: o que dá para adotar já, o que melhora gastando menos e sobre quem
   se constrói e contra quem se mede. Cada quadro tem a pergunta e um número
   que responde; clicar numa categoria liga o filtro.
3. **Comparar**: radar com até três papers e a mediana do recorte, e os mesmos
   números numa tabela por eixo.

**Paper**: gaveta lateral no desktop (a página abre espaço para ela a partir
de 1280 px) e folha de baixo no celular; anterior/próximo (Alt ← →), Esc
fecha e devolve o foco. Abaixo do título, a frase do problema marcada como
"segundo o modelo" (decisão 8). Três níveis: Resumo (o que entrega, Ganho,
Prova e Adoção com régua contra a mediana, sinais de prova, adoção,
resultados, os seis eixos), Trechos (frases literais) e Ficha (tabelas,
entidades, links).

**Sistema visual** (`painel-v2/src/app.css`, regras em
`docs/painel-v2-redesenho/04-sistema.md`): identidade Periódico (decisão 1),
com Newsreader para títulos, IBM Plex Sans para interface e IBM Plex Mono
para números, servidas pelo próprio painel (`src/fontes/`); tokens de cor,
tipo, espaço, raio e movimento; tema segue o sistema, com troca manual;
`prefers-reduced-motion` respeitado. `tema.js` lê os tokens e monta o tema
dos gráficos.

## Eixos do radar (0–100, `null` = não lido)

| Eixo | Conta |
|---|---|
| Ganho | 50 + 50·tanh(mediana do ganho relativo contra o melhor rival ÷ 10) |
| Prova | sinais verdadeiros ÷ sinais lidos (mínimo 3 lidos) |
| Abertura | código 40%, pesos 30%, dados 20%, demo 10% × (liberado 1, prometido 0,4, só página 0,15); o vértice é o confirmado, e `abTeto` soma os artefatos não lidos como se liberados. O radar desenha a faixa do vértice até `abTeto` (decisão 13) |
| Adoção | (5 − esforço) × 20; nulo para panorama e estudo |
| Amplitude | escala logarítmica fixa: 100·ln(1+n) ÷ ln(17), com teto em 16 benchmarks com linha própria (decisão 11) |
| Votos | percentil de votos no conjunto exportado |

## Pendências

- Conjunto-ouro de 100 papers para calibrar extração, solidez e esforço.
- Rodar `hfpapers ler` na máquina do pipeline (usa a `OPENROUTER_API_KEY` que já existe).
- Decidir quando `ler` entra no `run_daily.sh`.
