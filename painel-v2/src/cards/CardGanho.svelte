<script>
  import Card from '../lib/Card.svelte';
  import Kpi from '../lib/Kpi.svelte';
  import Grafico from '../lib/Grafico.svelte';
  import { median, curto, sgn, SOL_ROT, esc } from '../lib/dados.js';
  import { base, estiloPonto, rotNum, grade, dica } from '../lib/tema.js';
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
      grid: { left: 0, right: 12, top: 4, bottom: 24, containLabel: true },
      tooltip: { ...base(t).tooltip, trigger: 'item', formatter: (q) => {
        const l = linhas[q.dataIndex];
        return dica(esc(l.p.t), `Ganho mediano <b>${sgn(l.med)}%</b>`, l.n > 1 ? `de ${sgn(l.lo)}% a ${sgn(l.hi)}% em ${l.n} resultados` : '1 resultado', `Solidez ${SOL_ROT[l.p.sol].toLowerCase()}`);
      } },
      xAxis: { type: 'value', min: LO, max: HI, interval: 20,
        axisLabel: { ...rotNum(t), formatter: (v) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v)}%` },
        splitLine: grade(t) },
      yAxis: { type: 'category', data: linhas.map((l) => curto(l.p.t)), axisTick: { show: false }, axisLine: { show: false },
        axisLabel: { color: t.ink2, fontSize: 12, fontFamily: t.body, margin: 12 } },
      series: [{
        type: 'custom',
        renderItem: (params, api) => {
          const y = api.coord([0, api.value(3)])[1];
          const x0 = api.coord([api.value(1), 0])[0], x1 = api.coord([api.value(2), 0])[0], xm = api.coord([api.value(0), 0])[0];
          const st = api.style();
          return { type: 'group', children: [
            { type: 'line', shape: { x1: x0, y1: y, x2: x1, y2: y }, style: { stroke: t.lineStrong, lineWidth: 3, lineCap: 'round', opacity: .7 } },
            { type: 'circle', shape: { cx: xm, cy: y, r: 6 }, style: { fill: st.fill, stroke: st.stroke, lineWidth: st.lineWidth, lineDash: st.lineDash },
              emphasis: { style: { stroke: t.ink, lineWidth: 2 }, shape: { r: 8 } } },
          ] };
        },
        encode: { x: [0, 1, 2], y: 3 },
        data: linhas.map((l, i) => {
          const s = estiloPonto(t, l.p);
          return { pid: l.p.id, value: [cl(l.med), cl(l.lo), cl(l.hi), i],
            itemStyle: { color: s.color, borderColor: s.borderColor, borderWidth: s.borderWidth, borderType: s.borderType } };
        }),
        markLine: { silent: true, symbol: 'none', data: [{ xAxis: 0 }], lineStyle: { color: t.ink, type: 'solid', width: 1, opacity: .55 }, label: { show: false } },
      }],
    };
  });
</script>

<Card titulo="Quanto ganham do melhor rival?">
  {#snippet kpi()}<Kpi valor={medAll} casas={1} prefixo="+" sufixo="%" texto={`ganho mediano · ${ganham} de ${linhas.length} vencem o rival`} />{/snippet}
  {#if opcao}<Grafico {opcao} altura={Math.max(160, linhas.length * 22 + 40)} rotulo="Ganho relativo contra o melhor rival por paper: ponto na mediana, traço do pior ao melhor resultado" />
  {:else}<div class="vazio">Nenhum paper deste recorte compara com rival externo.</div>{/if}
</Card>
