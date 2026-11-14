# ADR 006 — Painel público: site estático com Apache ECharts

- **Data**: 2026-11-14
- **Estado**: aceito
- **Complementa**: ADR 005 (o painel em código é a única leitura)

## Contexto

O painel vai para o site de pesquisa, aberto ao público. Até aqui era um HTML
único de ~5,7 MB, com dados, fichas e a série de votos embutidos, e gráficos
desenhados à mão em `div` e SVG. Público muda o que importa: peso do primeiro
carregamento, celular, link compartilhável de uma visão, acessibilidade e
gráficos que aguentem crescer.

## Decisão

- **Continua estático e sem servidor.** GitHub Pages serve
  `relatorios/painel/`. Streamlit ou Dash exigiriam um processo Python no ar
  para um painel que muda uma vez por dia.
- **Gráficos em Apache ECharts**, num build com só os módulos usados
  (`scripts/echarts/`, saída versionada em `scripts/vendor/`, ~210 KB gzip).
  Zoom, tooltip e eventos de clique nativos; os gráficos são interligados pelo
  mesmo `setState` das pílulas. Plotly.js foi descartado pelo peso com muitos
  gráficos.
- **Dados fora da página e pré-agregados.** `dados.json` tem o que a primeira
  pintura precisa; `fichas.json`, o texto das fichas, chega depois. A série de
  snapshots (1,7 MB) não viaja: `gerar_painel.atencao` a reduz por paper ao
  ganho da semana e à trajetória normalizada. DuckDB-WASM ficou de fora: são
  vários MB para consultas que o JSON pré-agregado já responde.
- **O recorte fica no fragmento da URL**, para um link abrir a mesma visão.
- **Cada gráfico tem título, resumo em texto e tabela**, e a paleta das
  naturezas é segura para daltonismo (validada com o cinza do `fora`, todos os
  pares, contra o fundo do card).
- O arquivo único continua existindo como **prévia**: `--destino x.html`
  embute tudo, inclusive o ECharts, e abre offline.

## Consequências

- `gerar_painel.sh` versiona a pasta, não um arquivo; o workflow do Pages copia
  a pasta.
- Trocar uma cor de natureza pede validar a paleta de novo.
- Um gráfico ou componente novo do ECharts pede acrescentar o módulo em
  `scripts/echarts/entrada.mjs` e refazer o build.
