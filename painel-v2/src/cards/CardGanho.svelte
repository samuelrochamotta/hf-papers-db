<script>
  import Card from '../lib/Card.svelte';
  import Kpi from '../lib/Kpi.svelte';
  import Grafico from '../lib/Grafico.svelte';
  import { median, curto, sgn, SOL_ROT, esc } from '../lib/dados.js';
  import { base, estiloPonto } from '../lib/tema.js';
  import { estado } from '../lib/estado.svelte.js';

  let { papers } = $props();
  const t = $derived(estado.tema);
  const LO = -20, HI = 40;
  const cl = (v) => Math.max(LO, Math.min(HI, v));

  const linhas = $derived(papers.map((p) => {
    const rx = p.res.map((r) => r.rext).filter((v) => v != null);
    return rx.length ? { p, med: median(rx), lo: Math.min(...rx), hi: Math.max(...rx), n: rx.length } : null;
  }).filter(Boolean).sort((a, b) => a.med - b.med));
  const medAll = $derived(median(linhas.map((l) => l.med)));
  const ganham = $derived(linhas.filter((l) => l.med > 0).length);

  const opcao = $derived.by(() => {
    if (!t.ink || !linhas.length) return null;
    return {
      ...base(t),
      grid: { left: 4, right: 14, top: 6, bottom: 22, containLabel: true },
      tooltip: { ...base(t).tooltip, trigger: 'item', formatter: (q) => {
        const l = linhas[q.dataIndex];
        return `<b>${esc(l.p.t)}</b><br>Mediana ${sgn(l.med)}% · de ${sgn(l.lo)}% a ${sgn(l.hi)}% em ${l.n} tabela${l.n > 1 ? 's' : ''}<br>Solidez: ${SOL_ROT[l.p.sol]}`;
      } },
      xAxis: { type: 'value', min: LO, max: HI, interval: 20,
        axisLabel: { color: t.muted, fontFamily: t.mono, fontSize: 10.5, formatter: (v) => `${v > 0 ? '+' : ''}${v}%` },
        splitLine: { lineStyle: { color: t.line } } },
      yAxis: { type: 'category', data: linhas.map((l) => curto(l.p.t)), axisTick: { show: false }, axisLine: { show: false },
        axisLabel: { color: t.ink2, fontSize: 11 } },
      series: [{
        type: 'custom',
        renderItem: (params, api) => {
          const y = api.coord([0, api.value(3)])[1];
          const x0 = api.coord([api.value(1), 0])[0], x1 = api.coord([api.value(2), 0])[0], xm = api.coord([api.value(0), 0])[0];
          const st = api.style();
          return { type: 'group', children: [
            { type: 'line', shape: { x1: x0, y1: y, x2: x1, y2: y }, style: { stroke: t.line, lineWidth: 4, lineCap: 'round' } },
            { type: 'circle', shape: { cx: xm, cy: y, r: 6 }, style: { fill: st.fill, stroke: st.stroke, lineWidth: st.lineWidth, lineDash: st.lineDash },
              emphasis: { style: { shadowBlur: 10, shadowColor: t.accent }, shape: { r: 8 } } },
          ] };
        },
        encode: { x: [0, 1, 2], y: 3 },
        data: linhas.map((l, i) => {
          const s = estiloPonto(t, l.p);
          return { pid: l.p.id, value: [cl(l.med), cl(l.lo), cl(l.hi), i],
            itemStyle: { color: s.color, borderColor: s.borderColor, borderWidth: s.borderWidth, borderType: s.borderType } };
        }),
        markLine: { silent: true, symbol: 'none', data: [{ xAxis: 0 }], lineStyle: { color: t.ink2, type: 'solid', width: 1.2 }, label: { show: false } },
      }],
    };
  });
</script>

<Card titulo="Quanto ganham do melhor rival?">
  {#snippet kpi()}<Kpi valor={medAll} casas={1} prefixo="+" sufixo="%" texto={`mediana · ${ganham} de ${linhas.length} à frente`} />{/snippet}
  {#if opcao}<Grafico {opcao} altura={Math.max(160, linhas.length * 22 + 40)} rotulo="Ganho relativo contra o melhor rival por paper" />
  {:else}<p class="vazio">Nenhum paper compara com rival externo.</p>{/if}
</Card>
