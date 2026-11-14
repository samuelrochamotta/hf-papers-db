<script>
  import Card from '../lib/Card.svelte';
  import Kpi from '../lib/Kpi.svelte';
  import Grafico from '../lib/Grafico.svelte';
  import { ARENA } from '../lib/dados.js';
  import { base } from '../lib/tema.js';
  import { estado, lente } from '../lib/estado.svelte.js';

  let { papers } = $props();
  const t = $derived(estado.tema);
  const ESTADOS = [['ganha', 'Vence'], ['ruido', 'Dentro do ruído'], ['perde', 'Perde'], ['sem_rival', 'Sem rival']];

  const linhas = $derived.by(() => {
    const m = new Map();
    for (const p of papers) for (const r of p.res) {
      const k = r.ar;
      if (!m.has(k)) m.set(k, { k, ps: new Set(), c: { ganha: 0, ruido: 0, perde: 0, sem_rival: 0 } });
      const o = m.get(k);
      o.ps.add(p.id);
      const e = r.e === 'empata' ? 'ruido' : r.e === 'sem_nosso' ? 'sem_rival' : r.e;
      o.c[e] = (o.c[e] || 0) + 1;
    }
    return [...m.values()].sort((a, b) => a.ps.size - b.ps.size || 0);
  });
  const topo = $derived(linhas.length ? linhas[linhas.length - 1] : null);

  const opcao = $derived.by(() => {
    if (!t.ink) return null;
    const cor = { ganha: t.win, ruido: t.noise, perde: t.lose, sem_rival: t.line };
    return {
      ...base(t),
      grid: { left: 4, right: 30, top: 8, bottom: 24, containLabel: true },
      tooltip: { ...base(t).tooltip, trigger: 'axis', axisPointer: { type: 'shadow', shadowStyle: { color: t.accentSoft } } },
      xAxis: { type: 'value', splitLine: { lineStyle: { color: t.line } }, axisLabel: { color: t.muted, fontFamily: t.mono, fontSize: 10.5 } },
      yAxis: {
        type: 'category', data: linhas.map((l) => ARENA[l.k] || l.k), triggerEvent: true,
        axisTick: { show: false }, axisLine: { show: false },
        axisLabel: { color: t.ink, fontWeight: 500, fontSize: 12.5,
          formatter: (v, i) => `${v}  {p|${linhas[i].ps.size}p}`, rich: { p: { color: t.muted, fontFamily: t.mono, fontSize: 10.5 } } },
      },
      series: ESTADOS.map(([e, rot]) => ({
        type: 'bar', name: rot, stack: 'r', barWidth: 13,
        itemStyle: { color: cor[e], borderRadius: 3, borderColor: t.surface, borderWidth: 1 },
        emphasis: { focus: 'series' },
        data: linhas.map((l) => ({ value: l.c[e] || 0, arena: l.k })),
      })),
    };
  });
  const clicar = (p) => {
    const k = p.componentType === 'yAxis' ? linhas[p.dataIndex ?? linhas.findIndex((l) => (ARENA[l.k] || l.k) === p.value)]?.k : p.data?.arena;
    if (k) { lente('ar', k); return true; }
  };
</script>

<Card titulo="Onde está a disputa?">
  {#snippet kpi()}<Kpi valor={topo ? topo.ps.size : 0} texto={topo ? `papers em ${ARENA[topo.k] || topo.k}` : 'sem resultados em tabela'} />{/snippet}
  {#if opcao && linhas.length}
    <Grafico {opcao} altura={Math.max(170, linhas.length * 30 + 40)} aoClicar={clicar} rotulo="Resultados por arena, separados por vitória, ruído e derrota" />
    <div class="leg">
      {#each ESTADOS as [e, rot]}<span><i class="dot" style:background={e === 'ganha' ? 'var(--win)' : e === 'ruido' ? 'var(--noise)' : e === 'perde' ? 'var(--lose)' : 'var(--line)'}></i>{rot}</span>{/each}
    </div>
  {:else}<p class="vazio">Nenhum resultado com benchmark.</p>{/if}
</Card>

<style>
  .leg { display: flex; flex-wrap: wrap; gap: 4px 12px; font-size: 12px; color: var(--ink2); }
  .leg span { display: inline-flex; align-items: center; gap: 5px; }
</style>
