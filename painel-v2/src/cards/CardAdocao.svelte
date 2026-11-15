<script>
  import Card from '../lib/Card.svelte';
  import Kpi from '../lib/Kpi.svelte';
  import Grafico from '../lib/Grafico.svelte';
  import { ESFORCO, SOL_ROT, ART, ART_EST, esc } from '../lib/dados.js';
  import { base, estiloPonto } from '../lib/tema.js';
  import { estado, lente } from '../lib/estado.svelte.js';

  let { papers } = $props();
  const t = $derived(estado.tema);
  const NIVEIS = [1, 2, 3, 4, 5, 0];
  const prontos = $derived(papers.filter((p) => p.esf >= 1 && p.esf <= 2).length);

  const opcao = $derived.by(() => {
    if (!t.ink) return null;
    const pos = new Map();
    const dados = [...papers].sort((a, b) => b.u - a.u).map((p) => {
      const n = pos.get(p.esf) || 0; pos.set(p.esf, n + 1);
      return { pid: p.id, value: [n, NIVEIS.indexOf(p.esf)], itemStyle: estiloPonto(t, p) };
    });
    const maxN = Math.max(6, ...pos.values());
    return {
      ...base(t),
      grid: { left: 4, right: 10, top: 6, bottom: 6, containLabel: true },
      tooltip: { ...base(t).tooltip, trigger: 'item', formatter: (q) => {
        const p = papers.find((x) => x.id === q.data.pid);
        const ab = Object.entries(p.ab).map(([k, v]) => `${ART[k]} ${ART_EST[v]}`).join(' · ');
        return `<b>${esc(p.t)}</b><br>${ESFORCO[p.esf]} · solidez ${SOL_ROT[p.sol]}<br><span style="opacity:.75">${ab}</span>`;
      } },
      xAxis: { type: 'value', min: -0.6, max: maxN - 0.4, show: false },
      yAxis: { type: 'category', inverse: true, data: NIVEIS.map((n) => ESFORCO[n]), triggerEvent: true,
        axisTick: { show: false }, axisLine: { show: false }, splitLine: { show: true, lineStyle: { color: t.line } },
        axisLabel: { color: t.ink, fontSize: 12, fontWeight: 500 } },
      series: [{ type: 'scatter', symbolSize: 16,
        emphasis: { scale: 1.4, itemStyle: { shadowBlur: 12, shadowColor: t.accent } }, data: dados }],
    };
  });
  const clicar = (q) => {
    if (q.componentType === 'yAxis') { const i = ESFORCO.indexOf(q.value); if (i >= 0) { lente('esf', i); return true; } }
  };
</script>

<Card titulo="O que dá para adotar já?">
  {#snippet kpi()}<Kpi valor={prontos} texto="prontos para configurar ou integrar" />{/snippet}
  {#if opcao}<Grafico {opcao} altura={230} aoClicar={clicar} rotulo="Papers por esforço de adoção" />{/if}
</Card>
