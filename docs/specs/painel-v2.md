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

Uma página em cinco seções numeradas, com a barra fixa no topo (marca, seções
com "você está aqui", legenda de solidez, período e tema claro/escuro) e uma
linha de recorte embaixo dela (quantos papers, intervalo de datas, filtro
ativo como chip removível). Período, filtro, paper aberto e comparação vão
para o endereço (`?periodo=7&lente=ar:codigo&paper=…&comparar=…`).

1. **Papers**: índice de assinaturas (mini radar por paper), ordenável por
   votos, ganho ou solidez; tracejado quando a leitura não basta. Clicar abre
   o paper; o `+` do canto põe na comparação (com a cor da comparação).
2. **Comparar**: radar com até 3 papers e a mediana do recorte, e os mesmos
   números numa tabela por eixo.
3. **Resultados**: onde está a disputa (arenas) e quanto ganham do melhor
   rival (haltere).
4. **Prova**: onde há votos sem prova (enxame) e a letra miúda (limites
   admitidos, ressalvas graves, manchetes que a tabela não confirma).
5. **Adoção**: o que dá para adotar já, o que melhora gastando menos e sobre
   quem se constrói e contra quem se mede.

Cada cartão tem pergunta e um número que responde. Clicar numa arena, nível
de solidez, degrau de esforço ou família aplica a lente em tudo; o botão de
filtro do cartão mostra as mesmas categorias como botões (teclado e leitor de
tela). Passar o ponteiro num paper acende o mesmo paper em todos os gráficos.

**Paper**: gaveta lateral no desktop (a página abre espaço para ela a partir
de 1280 px) e folha de baixo no celular; anterior/próximo (Alt ← →), Esc
fecha e devolve o foco. Abas Resumo (fatos, radar contra a mediana, comparar,
resultados, sinais de prova, esforço, hardware, abertura), Trechos (frases
literais) e Ficha (tabelas, entidades, links).

**Sistema visual** (`painel-v2/src/app.css`): tokens de cor, tipo, espaço,
raio e movimento; Newsreader para títulos e números, Geist para interface,
Geist Mono para dados; grade de 4 px; uma família de controles (segmentado,
botão, chip, botão de ícone) com repouso, hover, foco, ativo e desabilitado;
`prefers-reduced-motion` respeitado. `tema.js` lê os tokens e monta o tema
dos gráficos.

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
- Rodar `hfpapers ler` na máquina do pipeline (usa a `OPENROUTER_API_KEY` que já existe).
- Decidir quando `ler` entra no `run_daily.sh`.
