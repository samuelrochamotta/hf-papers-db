# ECharts do painel

O painel usa um build do Apache ECharts com só os módulos que `painel_app.js`
usa (barra, linha, dispersão, heatmap, treemap; grade, tooltip, markLine,
dataZoom, aria; renderizador canvas). O build completo tem ~1 MB; este tem
~620 KB (~210 KB gzip).

A saída, `scripts/vendor/echarts.painel.min.js`, é versionada: gerar o painel
não precisa de Node. Só é preciso rodar o build ao trocar a versão do ECharts
ou ao usar um tipo de gráfico ou componente novo no app:

```bash
cd scripts/echarts
npm install
# edite entrada.mjs se precisar de um módulo novo
npm run build
```
