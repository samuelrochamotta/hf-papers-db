# Sistema do painel v2

O sistema vem antes das telas: tudo o que aparece no painel sai dos tokens de
`painel-v2/src/app.css`. Os gráficos leem os mesmos tokens (`src/lib/tema.js`),
então trocar um token troca a tela inteira, no claro e no escuro.

## Tipografia

Escala modular de razão 1,2 sobre 14 px, com alturas de linha na grade de 4 px.

| Token | Tamanho / linha | Uso |
|---|---|---|
| `--fs-12` | 12 / 16 | rótulo de campo, eixo de gráfico, legenda. Nada no painel fica abaixo de 12 px |
| `--fs-14` | 14 / 20 | texto base, linha do índice, controles |
| `--fs-17` | 17 / 24 | marca, título de seção pequeno |
| `--fs-20` | 20 / 28 | fato do paper (Firme, Integrar) |
| `--fs-24` | 24 / 32 | título de seção |
| `--fs-29` | 29 / 36 | título do paper aberto |
| `--fs-35` | 35 / 40 | número que responde ao quadro |
| `--fs-42` | 42 / 48 | reserva para tela larga |

Três papéis de fonte: `--f-ui` (texto e controles), `--f-num` (números, sempre
tabulares) e `--f-display` (marca, títulos e números grandes, com
`--display-peso` e `--display-esp`). A identidade troca só essas famílias.

## Grade e espaço

- Espaço na grade de 4 px: `--sp-1` 4, `--sp-2` 8, `--sp-3` 12, `--sp-4` 16, `--sp-5` 20, `--sp-6` 24, `--sp-8` 32, `--sp-10` 40, `--sp-12` 48, `--sp-16` 64.
- Página: 4 colunas até 767 px, 8 até 1023, 12 dali em diante; margem de 16, 24 e 40 px; largura máxima de 1440 px.
- Raios: `--r-1` 4 (foco, célula), `--r-2` 8 (controle), `--r-3` 12 (quadro).
- Alturas fixas: controle 32 px (40 px com toque; chips 36 px), barra 56 px, paper aberto 480 px em tela larga.
- Alvo de toque: 44 px em todo controle, medido com o dedo na tela por `medir/alvos.mjs`. O desenho pode ser menor que o alvo: a área que responde passa do contorno, sem cobrir o alvo do vizinho. Com ponteiro fino o mínimo é 24 px (WCAG 2.2).

## Cor

Papéis, e não cores soltas. Um bloco por tema; a identidade troca só este bloco.

| Papel | Tokens |
|---|---|
| Fundo e superfícies | `--bg`, `--surface`, `--sunk`, `--hover`, `--raise` |
| Texto | `--ink`, `--ink2`, `--muted` |
| Linhas | `--line` (divisão), `--line-strong` (borda de controle, 3:1) |
| Ação e foco | `--accent`, `--on-accent`, `--focus` |
| Alerta | `--alert`, `--alert-soft` |
| Prova, a única codificação de cor de dado | `--sol-forte`, `--sol-firme`, `--sol-basico`, `--sol-fragil`; `--sol-nada` é um anel tracejado, porque ausência de dado não é um nível da rampa. A marca repete o nível no preenchimento (inteiro, três quartos, metade, um quarto): experimento E4 |
| Resultado contra o rival | `--res-ganha`, `--res-ruido`, `--res-perde`, `--res-semrival` |
| Comparação de até três papers | `--cmp-1`, `--cmp-2`, `--cmp-3`, fora da rampa de prova |

Conferido a cada rodada por `medir/contraste.mjs` (76 pares: texto em 4,5:1 ou
mais, marcas e bordas em 3:1 ou mais), `medir/axe.mjs` e `medir/daltonismo.mjs`
(menor ΔE2000 entre categorias de 10 ou mais em protanopia, deuteranopia e
tritanopia).

## Matriz de estados dos controles

Todos os controles passam pelos mesmos estados, na mesma ordem.

| Controle | Repouso | Ponteiro em cima | Foco (teclado) | Pressionado | Ligado | Desabilitado |
|---|---|---|---|---|---|---|
| Botão primário `.btn.pri` | fundo `--accent` | 86% do acento | anel `--focus` de 2 px, afastado 2 px | desce 1 px | não se aplica | 45% de opacidade, sem ponteiro |
| Botão secundário `.btn.sec` | borda `--line-strong` | fundo `--hover` | anel | desce 1 px | `aria-pressed`: fundo `--accent` | 45% |
| Botão discreto `.btn.fan`, ícone `.ico` | sem fundo | fundo `--hover` | anel | desce 1 px | não se aplica | 45% |
| Segmento `.seg > button` (período, abas do paper) | texto `--ink2` sobre `--sunk` | texto `--ink`, véu claro | anel | desce 1 px | `aria-pressed` ou `aria-selected`: `--seg-on` com borda (branco no claro; no escuro, mais claro que o trilho) | 45% |
| Filtro com menu `.sel` | borda `--line-strong` | fundo `--hover` | anel redondo | desce 1 px | `.on`: fundo `--accent`, valor escrito no botão e um "×" ao lado que tira só aquele filtro | some quando só há uma opção |
| Opção de menu `[role=option]` | sem fundo | fundo `--hover` | fundo `--sunk` e anel interno | não se aplica | `aria-selected`: peso 600 e marca de visto | não se aplica |
| Link `.lk` | sublinhado em `--line-strong` | sublinhado na cor do texto | anel | não se aplica | visitado igual | não se aplica |
| Linha do índice | sem fundo | fundo `--hover` | anel | não se aplica | paper aberto: fundo `--sunk` | não se aplica |

Vistas (Papers, Panorama, Comparar) usam `aria-current="page"` com fundo
`--accent`; no celular viram abas no rodapé com a mesma marca.

## Movimento

Três durações e duas curvas, só onde o movimento explica uma mudança.

| Token | Valor | Uso |
|---|---|---|
| `--dur-1` | 120 ms | resposta a ponteiro e foco |
| `--dur-2` | 200 ms | entra e sai de elemento pequeno (menu, troca de paper) |
| `--dur-3` | 320 ms | gaveta do paper, folha no celular, reordenação da lista, número do quadro |
| `--sai` | `cubic-bezier(.2,.8,.2,1)` | entrada |
| `--vai-vem` | `cubic-bezier(.65,0,.35,1)` | troca de lugar |

Com `prefers-reduced-motion: reduce` as três durações viram 0 no CSS, as
transições do Svelte recebem duração 0 (`mov()` em `estado.svelte.js`) e os
gráficos desligam a animação (`base()` em `tema.js`).

## Tom

Em vigor no protótipo. O tom e o vocabulário são decisões do Samuel e estão
entre as opções apresentadas a ele.

1. O título de um quadro é a pergunta que o quadro responde.
2. A resposta é um número e o fato que ele conta, sem verbo de opinião.
3. Um nome por conceito, o mesmo no radar, na coluna, no filtro e na comparação: Ganho, Prova, Abertura, Adoção, Amplitude, Votos.
4. O rótulo de um controle diz o que acontece: Limpar, Comparar, Ver os 12 trechos.
5. Nenhuma frase de instrução. O que é clicável se mostra no desenho.
6. Palavra do paper só entre aspas e no idioma original. O painel não parafraseia.
7. Ausência de dado tem nome próprio (Não lida, sem rival externo, ganho não lido, Só informa) e nunca vira zero. Nenhuma tela põe um traço no lugar de um fato do paper.
8. Números em português: vírgula decimal, sinal explícito no ganho (+3,4%), × para razão.
9. Estado vazio diz o que não há e oferece a saída quando existe.
10. Rótulo não leva ponto final; frase completa leva.
11. Um paper tem um nome curto só (`nome()` em `dados.js`: o título até os dois-pontos, até 28 letras, cortado em palavra inteira). Gráficos, nomes, legendas e a comparação usam o mesmo; só onde ele não cabe o desenho usa o menor (`nomeMenor()`).
12. A conferência da manchete diz o que a leitura fez: "fora das tabelas lidas", não "não confere".

## Radar

A nota de 0 a 100 vem do Python e não muda no painel (D12). O que ela esconde
aparece no desenho (`marcasRadar()` em `tema.js`):

| Marca | Quando | Onde |
|---|---|---|
| "50" e "100" | sempre | nos anéis, na aresta entre o primeiro e o último eixo, onde nenhum vértice cai |
| Vértice vazado | o eixo só conta parte do que existe (abertura com artefato não lido) | no vértice do paper, na cor dele |
| Marca de corte "»" | o fato passa do teto do eixo (amplitude acima de 5 benchmarks) | fora do anel, na cor do paper |
| Fato com unidade | radar de um paper só | ao lado do nome de cada eixo ("9 bench.", "código", "+10,2%") |

Na tabela da comparação, a barra é proporcional ao número escrito onde há
número (benchmarks e votos, até o maior do período); o ganho sai do zero para
os dois lados; a prova escreve os sinais cumpridos; a abertura mostra os quatro
artefatos, com os não lidos tracejados.
