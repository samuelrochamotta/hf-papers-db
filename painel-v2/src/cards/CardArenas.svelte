<script>
  import Card from '../lib/Card.svelte';
  import Kpi from '../lib/Kpi.svelte';
  import Grafico from '../lib/Grafico.svelte';
  import Filtros from '../lib/Filtros.svelte';
  import { ARENA, plural } from '../lib/dados.js';
  import { base, rotNum, grade } from '../lib/tema.js';
  import { estado, lente } from '../lib/estado.svelte.js';

  let { papers } = $props();
  const t = $derived(estado.tema);
  const ESTADOS = [['ganha', 'Vence o rival'], ['ruido', 'Dentro do ruído'], ['perde', 'Perde'], ['sem_rival', 'Sem rival']];
  const COR = { ganha: 'var(--win)', ruido: 'var(--noise)', perde: 'var(--lose)', sem_rival: 'var(--norival)' };

  const linhas = $derived.by(() => {
    const m = new Map();
    for (const p of papers) for (const r of p.res) {
      const k = r.ar;
      if (!m.has(k)) m.set(k, { k, ps: new Set(), n: 0, c: { ganha: 0, ruido: 0, perde: 0, sem_rival: 0 } });
      const o = m.get(k);
      o.ps.add(p.id); o.n++;
      const e = r.e === 'empata' ? 'ruido' : r.e === 'sem_nosso' ? 'sem_rival' : r.e;
      o.c[e] = (o.c[e] || 0) + 1;
    }
    return [...m.values()].sort((a, b) => b.ps.size - a.ps.size || b.n - a.n);
  });
  const topo = $derived(linhas[0] || null);
  const nome = (k) => ARENA[k] || k;
  const ativa = $derived(estado.lente?.k === 'ar' ? estado.lente.v : null);

  const opcao = $derived.by(() => {
    if (!t.ink) return null;
    const cor = { ganha: t.win, ruido: t.noise, perde: t.lose, sem_rival: t.norival };
    const apaga = (k) => (ativa && ativa !== k ? 0.25 : 1);
    return {
      ...base(t),
      grid: { left: 0, right: 8, top: 20, bottom: 30, containLabel: true },
      tooltip: { ...base(t).tooltip, trigger: 'axis', axisPointer: { type: 'shadow', shadowStyle: { color: t.accentSoft } },
        formatter: (qs) => {
          const l = linhas[qs[0].dataIndex];
          const linhasE = ESTADOS.filter(([e]) => l.c[e]).map(([e, r]) => `<span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:${cor[e]};margin-right:6px"></span>${r}: <b>${l.c[e]}</b>`);
          return `<div style="font-weight:600">${nome(l.k)}</div><div style="opacity:.7;margin-bottom:6px">${plural(l.ps.size, 'paper', 'papers')} · ${plural(l.n, 'resultado', 'resultados')}</div>${linhasE.join('<br>')}`
            + `<div style="margin-top:8px;padding-top:6px;border-top:1px solid ${t.line};color:${t.accent};font-size:11.5px">${ativa === l.k ? 'Clique para tirar o filtro' : 'Clique para filtrar tudo por esta arena'}</div>`;
        } },
      xAxis: { type: 'value', minInterval: 1, splitLine: grade(t), axisLabel: rotNum(t),
        name: 'resultados em tabela', nameLocation: 'middle', nameGap: 24, nameTextStyle: rotNum(t) },
      yAxis: {
        type: 'category', inverse: true, data: linhas.map((l) => nome(l.k)), triggerEvent: true,
        name: 'papers', nameLocation: 'start', nameGap: 6, nameTextStyle: { ...rotNum(t), align: 'right', padding: [0, 14, 0, 0] },
        axisTick: { show: false }, axisLine: { show: false },
        axisLabel: { fontSize: 12.5, margin: 12,
          formatter: (v, i) => `{${ativa && ativa !== linhas[i].k ? 'off' : 'a'}|${v}}  {n|${linhas[i].ps.size}}`,
          rich: { a: { color: t.ink, fontWeight: 500, fontFamily: t.body, fontSize: 12.5 }, off: { color: t.muted, fontFamily: t.body, fontSize: 12.5 },
            n: { color: t.muted, fontFamily: t.mono, fontSize: 11, width: 14, align: 'right' } } },
      },
      series: ESTADOS.map(([e, rot]) => ({
        type: 'bar', name: rot, stack: 'r', barWidth: 14, cursor: 'pointer',
        itemStyle: { color: cor[e], borderRadius: 2, borderColor: t.surface, borderWidth: 1 },
        emphasis: { disabled: true },
        data: linhas.map((l) => ({ value: l.c[e] || 0, arena: l.k, itemStyle: { opacity: apaga(l.k) } })),
      })),
    };
  });
  const clicar = (p) => {
    const k = p.componentType === 'yAxis' ? linhas[p.dataIndex ?? linhas.findIndex((l) => nome(l.k) === p.value)]?.k : p.data?.arena;
    if (k) { lente('ar', k); return true; }
  };
</script>

<Card titulo="Onde está a disputa?" filtra="Clique numa arena para filtrar o painel inteiro">
  {#snippet filtros()}<Filtros k="ar" rotulo="Filtrar por arena" itens={linhas.map((l) => [l.k, nome(l.k)])} />{/snippet}
  {#snippet kpi()}<Kpi valor={topo ? topo.ps.size : 0} texto={topo ? `papers disputam ${nome(topo.k)}, a arena mais cheia` : 'nenhum resultado em tabela'} />{/snippet}
  {#if opcao && linhas.length}
    <Grafico {opcao} altura={Math.max(180, linhas.length * 30 + 56)} aoClicar={clicar} rotulo="Resultados por arena, separados em vitória, ruído, derrota e sem rival" />
  {:else}<div class="vazio">Nenhum resultado com benchmark neste recorte.</div>{/if}
  {#snippet rodape()}
    <div class="leg">
      {#each ESTADOS as [e, rot]}<span><i class="sw" style:background={COR[e]}></i>{rot}</span>{/each}
    </div>
  {/snippet}
</Card>

<style>
  .leg { display: flex; flex-wrap: wrap; gap: 6px 14px; font-size: var(--t-12); color: var(--ink2); }
  .leg span { display: inline-flex; align-items: center; gap: 6px; }
  .sw { width: 10px; height: 10px; border-radius: 2px; }
  .n { margin-left: auto; color: var(--muted); }
</style>
