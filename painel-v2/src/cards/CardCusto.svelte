<script>
  import Card from '../lib/Card.svelte';
  import Kpi from '../lib/Kpi.svelte';
  import Grafico from '../lib/Grafico.svelte';
  import { median, curto, fmt, sgn } from '../lib/dados.js';
  import { base, estiloPonto } from '../lib/tema.js';
  import { estado } from '../lib/estado.svelte.js';

  let { papers } = $props();
  const t = $derived(estado.tema);
  const fator = (e) => {
    const v = +e.valor; if (!v) return null;
    if (e.forma === 'percentual') return e.sentido === 'menos' ? 1 - v / 100 : 1 + v / 100;
    if (e.sentido === 'mais') return v;
    return v < 1 ? v : 1 / v;
  };
  const pontos = $derived(papers.map((p) => {
    const e = p.ef.find((x) => /computacao|latencia|memoria/.test(x.recurso)) || p.ef[0];
    if (!e) return null;
    const f = fator(e); if (!f || f <= 0) return null;
    const rx = p.res.map((r) => r.rext).filter((v) => v != null), rw = p.res.map((r) => r.rwk).filter((v) => v != null);
    return { p, f: Math.max(0.02, Math.min(3, f)), g: rx.length ? median(rx) : rw.length ? median(rw) : 0 };
  }).filter(Boolean));
  const bons = $derived(pontos.filter((o) => o.f < 1 && o.g >= 0).length);

  const opcao = $derived.by(() => {
    if (!t.ink || !pontos.length) return null;
    return {
      ...base(t),
      grid: { left: 4, right: 70, top: 14, bottom: 22, containLabel: true },
      tooltip: { ...base(t).tooltip, trigger: 'item', formatter: (q) => {
        const o = pontos.find((x) => x.p.id === q.data.pid);
        return `<b>${o.p.t}</b><br>custo ${fmt(o.f, 2)}× · ganho ${sgn(o.g)}%`;
      } },
      xAxis: { type: 'log', min: 0.02, max: 3, logBase: 10,
        axisLabel: { color: t.muted, fontFamily: t.mono, fontSize: 10.5, formatter: (v) => `${fmt(v, 2)}×` }, splitLine: { lineStyle: { color: t.line } } },
      yAxis: { type: 'value', min: -10, max: 30, interval: 10,
        axisLabel: { color: t.muted, fontFamily: t.mono, fontSize: 10.5, formatter: (v) => `${v > 0 ? '+' : ''}${v}%` }, splitLine: { lineStyle: { color: t.line } } },
      series: [{
        type: 'scatter', symbolSize: 15,
        emphasis: { scale: 1.4, itemStyle: { shadowBlur: 12, shadowColor: t.accent } },
        labelLayout: { hideOverlap: true, moveOverlap: 'shiftY' },
        label: { show: true, position: 'right', distance: 6, color: t.ink, fontSize: 11, formatter: (q) => curto(q.data.t) },
        data: pontos.map((o) => ({ pid: o.p.id, t: o.p.t, value: [o.f, Math.max(-10, Math.min(30, o.g))], itemStyle: estiloPonto(t, o.p) })),
        markArea: { silent: true, itemStyle: { color: t.accentSoft },
          label: { show: true, position: 'insideTopLeft', color: t.accent, fontWeight: 600, fontSize: 11, formatter: 'mais barato e melhor' },
          data: [[{ xAxis: 0.02, yAxis: 0 }, { xAxis: 1, yAxis: 30 }]] },
        markLine: { silent: true, symbol: 'none', label: { show: false }, lineStyle: { color: t.ink2, type: 'solid', width: 1 },
          data: [{ xAxis: 1 }, { yAxis: 0 }] },
      }],
    };
  });
</script>

<Card titulo="O que melhora gastando menos?">
  {#snippet kpi()}<Kpi valor={bons} texto="mais baratos sem perder qualidade" />{/snippet}
  {#if opcao}<Grafico {opcao} altura={250} rotulo="Ganho contra fator de custo" />
  {:else}<p class="vazio">Nenhum paper declara custo com número.</p>{/if}
</Card>
