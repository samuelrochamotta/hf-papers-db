<script>
  import Card from '../lib/Card.svelte';
  import Kpi from '../lib/Kpi.svelte';
  import Grafico from '../lib/Grafico.svelte';
  import { median, curto, fmt, sgn, esc } from '../lib/dados.js';
  import { base, estiloPonto, rotNum, grade, dica, realce } from '../lib/tema.js';
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
      grid: { left: 0, right: 16, top: 12, bottom: 26, containLabel: true },
      tooltip: { ...base(t).tooltip, trigger: 'item', formatter: (q) => {
        const o = pontos.find((x) => x.p.id === q.data.pid);
        return dica(esc(o.p.t), `Custo <b>${fmt(o.f, 2)}×</b> o do rival`, `Ganho <b>${sgn(o.g)}%</b>`);
      } },
      xAxis: { type: 'log', min: 0.02, max: 3, logBase: 10,
        name: 'custo relativo', nameLocation: 'middle', nameGap: 26, nameTextStyle: rotNum(t),
        axisLabel: { ...rotNum(t), formatter: (v) => `${fmt(v, 2)}×` }, splitLine: grade(t) },
      yAxis: { type: 'value', min: -10, max: 30, interval: 10, name: 'ganho', nameTextStyle: { ...rotNum(t), align: 'left', padding: [0, 0, 0, -28] },
        axisLabel: { ...rotNum(t), formatter: (v) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v)}%` }, splitLine: grade(t) },
      series: [{
        type: 'scatter', symbolSize: 14, cursor: 'pointer',
        emphasis: realce(t),
        labelLayout: { hideOverlap: true, moveOverlap: 'shiftY' },
        label: { show: true, distance: 7, color: t.ink2, fontSize: 11.5, fontFamily: t.body, formatter: (q) => curto(q.data.t, 18) },
        data: pontos.map((o) => ({ pid: o.p.id, t: o.p.t, value: [o.f, Math.max(-10, Math.min(30, o.g))], itemStyle: estiloPonto(t, o.p),
          label: { position: o.f > 0.5 ? 'left' : 'right' } })),
        markArea: { silent: true, itemStyle: { color: t.sunk },
          label: { show: true, position: 'insideTopLeft', distance: 8, color: t.ink2, fontWeight: 500, fontSize: 11, formatter: 'mais barato e melhor' },
          data: [[{ xAxis: 0.02, yAxis: 0 }, { xAxis: 1, yAxis: 30 }]] },
        markLine: { silent: true, symbol: 'none', label: { show: false }, lineStyle: { color: t.ink, type: 'solid', width: 1, opacity: .45 },
          data: [{ xAxis: 1 }, { yAxis: 0 }] },
      }],
    };
  });
</script>

<Card titulo="O que melhora gastando menos?">
  {#snippet kpi()}<Kpi valor={bons} texto="papers custam menos sem perder qualidade" />{/snippet}
  {#if opcao}<Grafico {opcao} altura={270} rotulo="Ganho contra fator de custo" />
  {:else}<div class="vazio">Nenhum paper deste recorte declara custo com número.</div>{/if}
</Card>
