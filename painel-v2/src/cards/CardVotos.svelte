<script>
  import Card from '../lib/Card.svelte';
  import Kpi from '../lib/Kpi.svelte';
  import Grafico from '../lib/Grafico.svelte';
  import { SOLIDEZ, SOL_ROT, median, esc } from '../lib/dados.js';
  import { base, estiloPonto } from '../lib/tema.js';
  import { estado, lente } from '../lib/estado.svelte.js';

  let { papers } = $props();
  const t = $derived(estado.tema);
  const ORDEM = ['sem_leitura', 'fragil', 'basico', 'firme', 'forte'];
  const med = $derived(median(papers.map((p) => p.u)) || 1);
  const ruidosos = $derived(papers.filter((p) => (p.sol === 'fragil' || p.sol === 'basico') && p.u >= med).length);

  const opcao = $derived.by(() => {
    if (!t.ink) return null;
    return {
      ...base(t),
      grid: { left: 4, right: 10, top: 14, bottom: 26, containLabel: true },
      tooltip: { ...base(t).tooltip, trigger: 'item', formatter: (q) => {
        const p = papers.find((x) => x.id === q.data.pid);
        return `<b>${esc(p.t)}</b><br>${p.u} votos · solidez ${SOL_ROT[p.sol]} (${p.T} de ${p.nl} sinais)`;
      } },
      xAxis: { type: 'category', data: ORDEM.map((s) => SOL_ROT[s]), triggerEvent: true,
        jitter: 34, jitterOverlap: false, jitterMargin: 3,
        axisTick: { show: false }, axisLine: { lineStyle: { color: t.line } },
        axisLabel: { color: t.ink2, fontSize: 11, fontWeight: 500, interval: 0, hideOverlap: false } },
      yAxis: { type: 'log', logBase: 10, min: (v) => Math.max(1, Math.round(v.min * 0.8)), max: (v) => Math.round(v.max * 1.2),
        axisLabel: { color: t.muted, fontFamily: t.mono, fontSize: 10.5 }, splitLine: { lineStyle: { color: t.line } } },
      series: [{
        type: 'scatter', symbolSize: 13,
        emphasis: { scale: 1.5, itemStyle: { shadowBlur: 12, shadowColor: t.accent } },
        data: papers.map((p) => ({ pid: p.id, value: [ORDEM.indexOf(p.sol), Math.max(1, p.u)], itemStyle: estiloPonto(t, p) })),
        markArea: { silent: true, itemStyle: { color: t.shade },
          data: [[{ xAxis: 1, yAxis: med }, { xAxis: 2, yAxis: 'max' }]] },
      }],
    };
  });
  const clicar = (q) => {
    if (q.componentType === 'xAxis') { const i = ORDEM.findIndex((s) => SOL_ROT[s] === q.value); if (i >= 0) { lente('sol', ORDEM[i]); return true; } }
  };
</script>

<Card titulo="Onde os votos não têm prova?">
  {#snippet kpi()}<Kpi valor={ruidosos} texto="com muitos votos e pouca prova" />{/snippet}
  {#if opcao}<Grafico {opcao} altura={260} aoClicar={clicar} rotulo="Votos por nível de solidez" />{/if}
</Card>
