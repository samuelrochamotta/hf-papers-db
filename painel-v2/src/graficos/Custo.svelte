<script>
  // O que melhora gastando menos: custo relativo ao rival contra o ganho.
  import Quadro from '../pecas/Quadro.svelte';
  import Grafico from '../lib/Grafico.svelte';
  import Chave from '../pecas/Chave.svelte';
  import { median, curto, fmt, sgn, esc } from '../lib/dados.js';
  import { base, estiloPonto, rotNum, grade, dica, realce, dominio, pct } from '../lib/tema.js';
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
    return { p, f, g: rx.length ? median(rx) : rw.length ? median(rw) : 0 };
  }).filter(Boolean));
  const bons = $derived(pontos.filter((o) => o.f < 1 && o.g >= 0).length);

  const opcao = $derived.by(() => {
    if (!t.ink || !pontos.length) return null;
    const fs = pontos.map((o) => o.f);
    const x0 = Math.min(0.1, ...fs.map((f) => 10 ** Math.floor(Math.log10(f)))), x1 = Math.max(2, ...fs.map((f) => (f > 1 ? 10 ** Math.ceil(Math.log10(f * 1.01)) : 2)));
    const [y0, y1, passo] = dominio(pontos.map((o) => o.g), { inclui: [-10, 10] });
    const vezes = (v) => `${v >= 1 ? v.toLocaleString('pt-BR') : v.toLocaleString('pt-BR', { maximumSignificantDigits: 1 })}×`;
    return {
      ...base(t),
      grid: { left: 0, right: 16, top: 28, bottom: 32, containLabel: true },
      graphic: [{ type: 'text', left: 0, top: 2, silent: true, style: { text: 'ganho', fill: t.muted, font: `12px ${t.fNum}` } }],
      tooltip: { ...base(t).tooltip, trigger: 'item', formatter: (q) => {
        const o = pontos.find((x) => x.p.id === q.data.pid); if (!o) return '';
        return dica(esc(o.p.t), `Custo <b>${fmt(o.f, 2)}×</b> o do rival`, `Ganho <b>${sgn(o.g)}%</b>`);
      } },
      xAxis: { type: 'log', min: x0, max: x1, logBase: 10,
        name: 'custo em relação ao rival', nameLocation: 'middle', nameGap: 28, nameTextStyle: rotNum(t),
        axisLabel: { ...rotNum(t), formatter: vezes, hideOverlap: true }, splitLine: grade(t) },
      yAxis: { type: 'value', min: y0, max: y1, interval: passo,
        axisLabel: { ...rotNum(t), formatter: pct }, splitLine: grade(t) },
      series: [{
        type: 'scatter', symbolSize: 14, cursor: 'pointer', emphasis: realce(t),
        labelLayout: { hideOverlap: true, moveOverlap: 'shiftY' },
        label: { show: true, distance: 7, color: t.ink2, fontSize: 12, fontFamily: t.fUi,
          formatter: (q) => curto(q.data.t, 18) + (q.data.fora ? ` ${sgn(q.data.g)}%` : '') },
        data: pontos.map((o) => ({ pid: o.p.id, t: o.p.t, g: o.g, fora: o.g > y1 || o.g < y0, value: [o.f, Math.max(y0, Math.min(y1, o.g))], itemStyle: estiloPonto(t, o.p),
          label: { position: Math.log10(o.f / x0) > Math.log10(x1 / x0) / 2 ? 'left' : 'right' } })),
        markArea: { silent: true, itemStyle: { color: t.sunk },
          label: { show: true, position: 'insideTopLeft', distance: 8, color: t.ink2, fontWeight: 500, fontSize: 12, fontFamily: t.fUi, formatter: 'mais barato e melhor' },
          data: [[{ xAxis: x0, yAxis: 0 }, { xAxis: 1, yAxis: y1 }]] },
        markLine: { silent: true, symbol: 'none', label: { show: false }, lineStyle: { color: t.ink, type: 'solid', width: 1, opacity: .5 },
          data: [{ xAxis: 1 }, { yAxis: 0 }] },
      }],
    };
  });
</script>

<Quadro id="custo" pergunta="O que melhora gastando menos?" valor={bons} resposta={`${bons === 1 ? 'paper custa' : 'papers custam'} menos sem perder qualidade`}>
  {#if opcao}<Grafico {opcao} altura={268} rotulo="Ganho de cada paper contra o custo em relação ao rival" />
  {:else}<div class="vazio">Nenhum paper deste recorte declara custo com número.</div>{/if}
  {#snippet legenda()}<Chave />{/snippet}
</Quadro>
