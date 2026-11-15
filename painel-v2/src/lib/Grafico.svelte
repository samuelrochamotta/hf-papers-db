<script>
  // Um grafico ECharts. Liga o realce cruzado: passar o ponteiro sobre um
  // paper em qualquer grafico acende o mesmo paper nos outros. Para isso cada
  // ponto de paper leva `pid` no item de dado. O paper aberto no painel fica
  // aceso enquanto o painel estiver aberto.
  import { onMount, untrack } from 'svelte';
  import echarts from './echarts.js';
  import { estado, abrir } from './estado.svelte.js';

  let { opcao, altura = 260, aoClicar = null, rotulo = '' } = $props();

  let el;
  let chart = $state.raw(null);
  let mapa = new Map(); // pid -> [{seriesIndex, dataIndex}]
  let acesos = [];

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

  function acender(...pids) {
    if (!chart) return;
    for (const a of acesos) chart.dispatchAction({ type: 'downplay', ...a });
    acesos = [];
    for (const pid of new Set(pids.filter(Boolean))) {
      for (const a of mapa.get(pid) || []) { chart.dispatchAction({ type: 'highlight', ...a }); acesos.push(a); }
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
    // redimensiona uma vez por quadro e sem animacao: animar cada passo de
    // uma mudanca de largura deixa barras e pontos fora do lugar
    let quadro = 0;
    const ro = new ResizeObserver(() => {
      cancelAnimationFrame(quadro);
      quadro = requestAnimationFrame(() => chart && chart.resize({ animation: { duration: 0 } }));
    });
    ro.observe(el);
    return () => { cancelAnimationFrame(quadro); ro.disconnect(); chart.dispose(); chart = null; };
  });

  // so a opcao redesenha; o realce nao pode virar dependencia deste efeito
  $effect(() => {
    if (!chart || !opcao) return;
    chart.setOption(opcao, { notMerge: false, replaceMerge: ['series', 'xAxis', 'yAxis', 'grid', 'radar', 'graphic'] });
    indexar(opcao);
    acesos = [];
    untrack(() => acender(estado.hover, estado.sel));
  });

  $effect(() => { acender(estado.hover, estado.sel); });
</script>

<div class="g" bind:this={el} style:height="{altura}px" role="img" aria-label={rotulo}></div>

<style>
  .g { width: 100%; }
</style>
