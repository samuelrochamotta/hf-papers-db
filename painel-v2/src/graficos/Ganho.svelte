<script>
  // Quanto ganham do melhor rival: um ponto na mediana e um traco do pior ao
  // melhor resultado de cada paper. O valor fica escrito na coluna da direita;
  // o que passa do eixo ganha marca de corte, nunca some.
  import Quadro from '../pecas/Quadro.svelte';
  import Grafico from '../lib/Grafico.svelte';
  import Chave from '../pecas/Chave.svelte';
  import { median, curto, sgn, SOL_FRASE, esc } from '../lib/dados.js';
  import { base, estiloPonto, rotNum, rotCat, grade, dica, dominio, pct, corte } from '../lib/tema.js';
  import { estado, abrir } from '../lib/estado.svelte.js';

  let { papers, limite = 16 } = $props();
  const t = $derived(estado.tema);
  const barras = $derived(estado.v.g === 'b');
  let tudo = $state(false);
  const todas = $derived(papers.map((p) => {
    const rx = p.res.map((r) => r.rext).filter((v) => v != null);
    return rx.length ? { p, med: median(rx), lo: Math.min(...rx), hi: Math.max(...rx), n: rx.length } : null;
  }).filter(Boolean).sort((a, b) => b.med - a.med || b.p.u - a.p.u));
  const linhas = $derived(tudo || todas.length <= limite ? todas : todas.slice(0, limite));
  const medAll = $derived(median(todas.map((l) => l.med)));
  const ganham = $derived(todas.filter((l) => l.med > 0).length);
  const dom = $derived(dominio(todas.map((l) => l.med)));
  const cortados = $derived(todas.some((l) => l.hi > dom[1] || l.lo < dom[0]));
  const nome = (l) => curto(l.p.t, 24);

  const opcao = $derived.by(() => {
    if (!t.ink || !linhas.length) return null;
    const [d0, d1] = dom, cl = (v) => Math.max(d0, Math.min(d1, v));
    const eixo = { type: 'category', inverse: true, axisTick: { show: false }, axisLine: { show: false } };
    const zero = { silent: true, symbol: 'none', data: [{ xAxis: 0 }], lineStyle: { color: t.ink, type: 'solid', width: 1, opacity: .6 }, label: { show: false } };
    const pontos = {
      type: 'custom', cursor: 'pointer', encode: { x: [0, 1, 2], y: 3 }, markLine: zero,
      renderItem: (_, api) => {
        const i = api.value(3), l = linhas[i]; if (!l) return null;
        const y = api.coord([0, i])[1], X = (v) => api.coord([v, i])[0];
        const s = estiloPonto(t, l.p), fora = l.med > d1 ? 1 : l.med < d0 ? -1 : 0;
        const xm = fora ? X(fora > 0 ? d1 : d0) - fora * 18 : X(l.med);
        const filhos = [];
        if (l.n > 1) filhos.push({ type: 'line', shape: { x1: X(cl(l.lo)), y1: y, x2: X(cl(l.hi)), y2: y }, style: { stroke: t.lineStrong, lineWidth: 2, lineCap: 'round' } });
        if (l.hi > d1) filhos.push(...corte(X(d1), y, 1, t.ink2));
        if (l.lo < d0) filhos.push(...corte(X(d0), y, -1, t.ink2));
        filhos.push({ type: 'circle', shape: { cx: xm, cy: y, r: 6 }, style: { fill: s.color, stroke: s.borderColor, lineWidth: s.borderWidth, lineDash: s.borderType },
          emphasis: { style: { stroke: t.ink, lineWidth: 2 }, shape: { r: 8 } } });
        return { type: 'group', children: filhos };
      },
      data: linhas.map((l, i) => ({ pid: l.p.id, value: [cl(l.med), cl(l.lo), cl(l.hi), i] })),
    };
    const barra = [{
      type: 'bar', barWidth: 12, cursor: 'pointer', markLine: zero,
      emphasis: { itemStyle: { borderColor: t.ink, borderWidth: 2 } },
      data: linhas.map((l) => { const s = estiloPonto(t, l.p), oco = l.p.sol === 'sem_leitura';
        return { pid: l.p.id, value: cl(l.med), itemStyle: { color: s.color, borderColor: oco ? s.borderColor : 'transparent', borderWidth: oco ? 1.5 : 0, borderType: oco ? 'dashed' : 'solid', borderRadius: 2 } }; }),
    }, {
      type: 'custom', silent: true, data: linhas.map((l, i) => [l.med > d1 ? d1 : d0, i, l.med > d1 ? 1 : l.med < d0 ? -1 : 0]).filter((v) => v[2]),
      renderItem: (_, api) => { const [x, y] = api.coord([api.value(0), api.value(1)]), dir = api.value(2); return { type: 'group', children: corte(x - dir * 4, y, dir, t.surface) }; },
    }];
    return {
      ...base(t),
      grid: { left: 0, right: 4, top: 4, bottom: 4, containLabel: true },
      tooltip: { ...base(t).tooltip, trigger: 'item', formatter: (q) => {
        const l = linhas[q.dataIndex]; if (!l) return '';
        return dica(esc(l.p.t), `Ganho mediano <b>${sgn(l.med)}%</b>`, l.n > 1 ? `de ${sgn(l.lo)}% a ${sgn(l.hi)}% em ${l.n} resultados` : '1 resultado', SOL_FRASE[l.p.sol]);
      } },
      xAxis: { type: 'value', min: d0, max: d1, interval: dom[2], axisLabel: { ...rotNum(t), formatter: pct, hideOverlap: true }, splitLine: grade(t) },
      yAxis: [
        { ...eixo, data: linhas.map(nome), triggerEvent: true, axisLabel: { ...rotCat(t), margin: 12 } },
        { ...eixo, position: 'right', data: linhas.map((l) => `${sgn(l.med)}%`),
          axisLabel: { ...rotNum(t), color: t.ink, margin: 12, formatter: (v, i) => (linhas[i]?.med < 0 ? `{neg|${v}}` : v), rich: { neg: { color: t.alert, fontFamily: t.fNum, fontSize: 12 } } } },
      ],
      series: barras ? barra : [pontos],
    };
  });
  const clicar = (q) => {
    if (q.componentType !== 'yAxis') return;
    const l = linhas[q.dataIndex ?? linhas.findIndex((x) => nome(x) === q.value)];
    if (l) { abrir(l.p.id); return true; }
  };
</script>

<Quadro id="ganho" pergunta="Quanto ganham do melhor rival?" valor={medAll} casas={1} prefixo="+" sufixo="%"
  resposta={todas.length ? `ganho mediano · ${ganham} de ${todas.length} ${ganham === 1 ? 'vence' : 'vencem'} o rival` : ''}>
  {#if opcao}
    <Grafico {opcao} altura={linhas.length * 24 + 40} aoClicar={clicar} rotulo="Ganho relativo de cada paper contra o melhor rival externo, do maior para o menor" />
    {#if todas.length > limite}<button class="btn sec mais" aria-expanded={tudo} onclick={() => (tudo = !tudo)}>{tudo ? 'Mostrar menos' : `Ver os ${todas.length} papers`}</button>{/if}
  {:else}<div class="vazio">Nenhum paper deste recorte compara com rival externo.</div>{/if}
  {#snippet legenda()}
    <div class="leg">
      <Chave />
      {#if !barras}<span class="k"><i class="pt"></i>mediana<i class="tr"></i>do pior ao melhor resultado</span>{/if}
      {#if cortados}<span class="k"><b aria-hidden="true">»</b>passa do eixo</span>{/if}
    </div>
  {/snippet}
</Quadro>

<style>
  .mais { margin-top: var(--sp-3); align-self: flex-start; }
  .leg { display: flex; flex-wrap: wrap; gap: var(--sp-2) var(--sp-5); font-size: var(--fs-12); line-height: var(--lh-12); color: var(--ink2); align-items: center; }
  .k { display: inline-flex; align-items: center; gap: 6px; }
  .pt { width: 10px; height: 10px; border-radius: 50%; background: var(--ink2); }
  .tr { width: 20px; height: 2px; border-radius: 1px; background: var(--line-strong); margin-left: var(--sp-2); }
  .k b { font-weight: 600; color: var(--ink2); }
</style>
