<script>
  // Onde esta a disputa: resultados por arena, separados pelo desfecho contra
  // o melhor rival. Clicar numa arena aplica a lente.
  import Quadro from '../pecas/Quadro.svelte';
  import Grafico from '../lib/Grafico.svelte';
  import { ARENA, plural, esc } from '../lib/dados.js';
  import { base, rotNum, grade } from '../lib/tema.js';
  import { estado, lente, lentesDe } from '../lib/estado.svelte.js';

  let { papers } = $props();
  const t = $derived(estado.tema);
  const ESTADOS = [['ganha', 'Vence o rival'], ['ruido', 'Dentro do ruído'], ['perde', 'Perde'], ['sem_rival', 'Sem rival externo']];

  const linhas = $derived.by(() => {
    const m = new Map();
    for (const p of papers) for (const r of p.res) {
      if (!m.has(r.ar)) m.set(r.ar, { k: r.ar, ps: new Set(), n: 0, c: { ganha: 0, ruido: 0, perde: 0, sem_rival: 0 } });
      const o = m.get(r.ar);
      o.ps.add(p.id); o.n++;
      const e = r.e === 'empata' ? 'ruido' : r.e === 'sem_nosso' ? 'sem_rival' : r.e;
      o.c[e] = (o.c[e] || 0) + 1;
    }
    return [...m.values()].sort((a, b) => b.ps.size - a.ps.size || b.n - a.n);
  });
  const topo = $derived(linhas[0] || null);
  const nome = (k) => ARENA[k] || k;
  const ativas = $derived(lentesDe('ar'));

  const opcao = $derived.by(() => {
    if (!t.ink) return null;
    const cor = { ganha: t.resGanha, ruido: t.resRuido, perde: t.resPerde, sem_rival: t.surface };
    const apaga = (k) => (ativas.length && !ativas.includes(k) ? 0.3 : 1);
    return {
      ...base(t),
      grid: { left: 0, right: 12, top: 4, bottom: 36, containLabel: true },
      tooltip: { ...base(t).tooltip, trigger: 'axis', axisPointer: { type: 'shadow', shadowStyle: { color: t.sunk, opacity: .6 } },
        formatter: (qs) => {
          const l = linhas[qs[0].dataIndex];
          const le = ESTADOS.filter(([e]) => l.c[e]).map(([e, r]) => `<span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:${cor[e]};box-shadow:inset 0 0 0 1px ${e === 'sem_rival' ? t.lineStrong : cor[e]};margin-right:6px"></span>${r}: <b>${l.c[e]}</b>`);
          return `<div style="font-weight:600">${esc(nome(l.k))}</div><div style="opacity:.8;margin-bottom:6px">${plural(l.ps.size, 'paper', 'papers')} · ${plural(l.n, 'resultado', 'resultados')}</div>${le.join('<br>')}`;
        } },
      xAxis: { type: 'value', minInterval: 1, splitLine: grade(t), axisLabel: rotNum(t),
        name: 'resultados em tabela', nameLocation: 'middle', nameGap: 26, nameTextStyle: rotNum(t) },
      yAxis: {
        type: 'category', inverse: true, data: linhas.map((l) => nome(l.k)), triggerEvent: true,
        axisTick: { show: false }, axisLine: { show: false },
        axisLabel: { fontSize: 12, margin: 12,
          formatter: (v, i) => `{${ativas.length && !ativas.includes(linhas[i].k) ? 'off' : 'a'}|${v}}  {n|${linhas[i].ps.size}}`,
          rich: { a: { color: t.ink, fontWeight: 500, fontFamily: t.fUi, fontSize: 12 }, off: { color: t.muted, fontFamily: t.fUi, fontSize: 12 },
            n: { color: t.muted, fontFamily: t.fNum, fontSize: 12, width: 16, align: 'right' } } },
      },
      series: ESTADOS.map(([e, rot]) => ({
        type: 'bar', name: rot, stack: 'r', barWidth: 14, cursor: 'pointer',
        itemStyle: { color: cor[e], borderRadius: 2, borderColor: e === 'sem_rival' ? t.lineStrong : t.surface, borderWidth: e === 'sem_rival' ? 1.5 : 1 },
        emphasis: { disabled: true },
        data: linhas.map((l) => ({ value: l.c[e] || 0, arena: l.k, itemStyle: { opacity: l.c[e] ? apaga(l.k) : 0 } })),
      })),
    };
  });
  const clicar = (q) => {
    const k = q.componentType === 'yAxis' ? linhas[q.dataIndex ?? linhas.findIndex((l) => q.value?.includes?.(nome(l.k)))]?.k : q.data?.arena;
    if (k) { lente('ar', k); return true; }
  };
</script>

<Quadro id="arenas" pergunta="Onde está a disputa?" valor={topo ? topo.ps.size : 0} resposta={topo ? `${topo.ps.size === 1 ? 'paper disputa' : 'papers disputam'} ${nome(topo.k)}, a arena mais cheia` : 'nenhum resultado em tabela'}>
  {#if opcao && linhas.length}
    <Grafico {opcao} altura={Math.max(160, linhas.length * 28 + 60)} aoClicar={clicar} rotulo="Resultados por arena, separados em vitória, ruído, derrota e sem rival externo" />
  {:else}<div class="vazio">Nenhum resultado com benchmark neste recorte.</div>{/if}
  {#snippet legenda()}
    <ul class="leg" aria-label="Desfecho contra o melhor rival">
      {#each ESTADOS as [e, rot]}<li><i class="sw {e}"></i>{rot}</li>{/each}
    </ul>
  {/snippet}
</Quadro>

<style>
  .leg { display: flex; flex-wrap: wrap; gap: var(--sp-1) var(--sp-3); font-size: var(--fs-12); line-height: var(--lh-12); color: var(--ink2); }
  .leg li { display: inline-flex; align-items: center; gap: 6px; }
  .sw { width: 10px; height: 10px; border-radius: 2px; background: var(--res-ganha); }
  .sw.ruido { background: var(--res-ruido); } .sw.perde { background: var(--res-perde); }
  .sw.sem_rival { background: transparent; box-shadow: inset 0 0 0 1.5px var(--line-strong); }
</style>
