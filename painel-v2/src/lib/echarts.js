// ECharts sob medida: so os tipos que o painel usa (o pacote inteiro passa de 1 MB).
import * as echarts from 'echarts/core';
import { BarChart, ScatterChart, RadarChart, CustomChart, LineChart } from 'echarts/charts';
import {
  GridComponent, TooltipComponent, RadarComponent, MarkAreaComponent, MarkLineComponent,
  GraphicComponent, AriaComponent,
} from 'echarts/components';
import { LabelLayout, UniversalTransition } from 'echarts/features';
import { CanvasRenderer } from 'echarts/renderers';

echarts.use([
  BarChart, ScatterChart, RadarChart, CustomChart, LineChart,
  GridComponent, TooltipComponent, RadarComponent, MarkAreaComponent, MarkLineComponent,
  GraphicComponent, AriaComponent, LabelLayout, UniversalTransition, CanvasRenderer,
]);

export default echarts;
