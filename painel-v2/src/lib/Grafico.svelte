<script>
  // Um grafico ECharts. Liga o realce cruzado: passar o ponteiro sobre um
  // paper em qualquer grafico acende o mesmo paper nos outros. Para isso cada
  // ponto de paper leva `pid` no item de dado.
  import { onMount } from 'svelte';
  import echarts from './echarts.js';
  import { estado, abrir } from './estado.svelte.js';

  let { opcao, altura = 260, aoClicar = null, rotulo = '' } = $props();

  let el;
  let chart = $state.raw(null);
  let mapa = new Map(); // pid -> [{seriesIndex, dataIndex}]
  let aceso = null;

  function indexar(op) {
    mapa = new Map();
    (op.series || []).forEach((s, si) => {
      (s.data || []).forEach((d, di) => {
        const pid = d && typeof d === 'object' ? d.pid : null;
        if (!pid) return;
        if (!mapa.has(pid)) mapa.set(pid, []);
        mapa.get(pid).push({ seriesIndex: si, dataIndex: di });
      });
    });
  }

  function acender(pid) {
    if (!chart) return;
    if (aceso) for (const a of mapa.get(aceso) || []) chart.dispatchAction({ type: 'downplay', ...a });
    aceso = null;
    if (pid && mapa.has(pid)) {
      for (const a of mapa.get(pid)) chart.dispatchAction({ type: 'highlight', ...a });
      aceso = pid;
    }
  }

  onMount(() => {
    chart = echarts.init(el, null, { renderer: 'canvas' });
    chart.on('mouseover', (p) => { if (p.data && p.data.pid) estado.hover = p.data.pid; });
    chart.on('mouseout', (p) => { if (p.data && p.data.pid && estado.hover === p.data.pid) estado.hover = null; });
    chart.on('click', (p) => {
      if (aoClicar && aoClicar(p) === true) return;
      if (p.data && p.data.pid) abrir(p.data.pid);
    });
    const ro = new ResizeObserver(() => chart && chart.resize({ animation: { duration: 250 } }));
    ro.observe(el);
    return () => { ro.disconnect(); chart.dispose(); chart = null; };
  });

  $effect(() => {
    if (!chart || !opcao) return;
    chart.setOption(opcao, { notMerge: false, replaceMerge: ['series', 'xAxis', 'yAxis', 'grid', 'radar'] });
    indexar(opcao);
    aceso = null;
    acender(estado.hover);
  });

  $effect(() => { acender(estado.hover); });
</script>

<div class="g" bind:this={el} style:height="{altura}px" role="img" aria-label={rotulo}></div>

<style>
  .g { width: 100%; }
</style>
