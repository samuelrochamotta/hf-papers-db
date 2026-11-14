/* Só o que o painel usa do ECharts. Acrescentar um tipo de gráfico ou um
   componente novo em painel_app.js exige acrescentá-lo aqui e rodar
   `npm run build` (ver README desta pasta). */
import * as echarts from 'echarts/core';
import { BarChart, LineChart, ScatterChart, HeatmapChart, TreemapChart } from 'echarts/charts';
import {
  GridComponent, TooltipComponent, MarkLineComponent,
  DataZoomComponent, AriaComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

echarts.use([
  BarChart, LineChart, ScatterChart, HeatmapChart, TreemapChart,
  GridComponent, TooltipComponent, MarkLineComponent,
  DataZoomComponent, AriaComponent,
  CanvasRenderer,
]);

window.echarts = echarts;
