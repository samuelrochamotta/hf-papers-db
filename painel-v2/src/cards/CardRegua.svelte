<script>
  import Card from '../lib/Card.svelte';
  import Kpi from '../lib/Kpi.svelte';
  import Grafico from '../lib/Grafico.svelte';
  import { familia } from '../lib/dados.js';
  import { base } from '../lib/tema.js';
  import { estado, lente } from '../lib/estado.svelte.js';

  let { papers } = $props();
  const t = $derived(estado.tema);
  let modo = $state('modelo');

  const linhas = $derived.by(() => {
    const L = new Map(), R = new Map();
    for (const p of papers) {
      const vl = new Set(), vr = new Set();
      for (const [nome, tipo, papel] of p.ents) {
        if (modo === 'modelo' ? tipo !== 'modelo' : !(tipo === 'benchmark' || tipo === 'dataset')) continue;
        const f = familia(nome);
        const esq = modo === 'modelo' ? (papel === 'base' || papel === 'professor') : (papel === 'criada_aqui' || papel === 'dados_treino');
        const dir = modo === 'modelo' ? ['baseline', 'objeto_medido', 'juiz_ferramenta'].includes(papel) : papel === 'avaliacao';
        if (esq && !vl.has(f)) { vl.add(f); L.set(f, (L.get(f) || 0) + 1); }
        if (dir && !vr.has(f)) { vr.add(f); R.set(f, (R.get(f) || 0) + 1); }
      }
    }
    const fams = [...new Set([...L.keys(), ...R.keys()])]
      .map((f) => ({ f, l: L.get(f) || 0, r: R.get(f) || 0 }))
      .sort((a, b) => (b.l + b.r) - (a.l + a.r) || b.l - a.l).slice(0, 9).reverse();
    return fams;
  });
  const topoBase = $derived([...linhas].sort((a, b) => b.l - a.l)[0]);

  const opcao = $derived.by(() => {
    if (!t.ink || !linhas.length) return null;
    const mx = Math.max(1, ...linhas.map((l) => Math.max(l.l, l.r)));
    return {
      ...base(t),
      grid: { left: 4, right: 18, top: 22, bottom: 4, containLabel: true },
      tooltip: { ...base(t).tooltip, trigger: 'axis', axisPointer: { type: 'shadow', shadowStyle: { color: t.accentSoft } },
        formatter: (qs) => `<b>${qs[0].name}</b><br>${modo === 'modelo' ? 'Base de' : 'Criado ou usado no treino em'} ${linhas[qs[0].dataIndex].l} · ${modo === 'modelo' ? 'régua de' : 'avalia'} ${linhas[qs[0].dataIndex].r}` },
      xAxis: { type: 'value', min: -mx * 1.3, max: mx * 1.3, show: false },
      yAxis: { type: 'category', data: linhas.map((l) => l.f), triggerEvent: true, position: 'left',
        axisTick: { show: false }, axisLine: { show: false }, axisLabel: { color: t.ink, fontWeight: 500, fontSize: 12 } },
      graphic: [
        { type: 'text', left: '28%', top: 2, style: { text: modo === 'modelo' ? '← como base' : '← criado aqui', fill: t.muted, font: `11px ${t.body}` } },
        { type: 'text', right: 18, top: 2, style: { text: modo === 'modelo' ? 'como régua →' : 'como avaliação →', fill: t.muted, font: `11px ${t.body}` } },
      ],
      series: [
        { type: 'bar', stack: 'x', barWidth: 13, data: linhas.map((l) => ({ value: -l.l, fam: l.f })),
          itemStyle: { color: t.sFirme, borderRadius: [3, 0, 0, 3] },
          label: { show: true, position: 'left', formatter: (q) => q.value ? -q.value : '', color: t.muted, fontFamily: t.mono, fontSize: 10.5 } },
        { type: 'bar', stack: 'x', barWidth: 13, data: linhas.map((l) => ({ value: l.r, fam: l.f })),
          itemStyle: { color: t.compare2, borderRadius: [0, 3, 3, 0] },
          label: { show: true, position: 'right', formatter: (q) => q.value || '', color: t.muted, fontFamily: t.mono, fontSize: 10.5 } },
      ],
    };
  });
  const clicar = (q) => {
    const f = q.componentType === 'yAxis' ? q.value : q.data?.fam;
    if (f) { lente('fam', f); return true; }
  };
</script>

<Card titulo="Sobre o que se constrói e contra quem se mede?">
  {#snippet extra()}
    <div class="seg" role="group" aria-label="Tipo de entidade">
      <button aria-pressed={modo === 'modelo'} onclick={() => (modo = 'modelo')}>Modelos</button>
      <button aria-pressed={modo === 'bench'} onclick={() => (modo = 'bench')}>Benchmarks</button>
    </div>
  {/snippet}
  {#snippet kpi()}<Kpi valor={topoBase ? topoBase.l : 0} texto={topoBase && topoBase.l ? `papers ${modo === 'modelo' ? 'constroem sobre' : 'criam'} ${topoBase.f}` : 'sem entidades lidas'} />{/snippet}
  {#if opcao}<Grafico {opcao} altura={Math.max(170, linhas.length * 27 + 34)} aoClicar={clicar} rotulo="Entidades usadas como base e como régua" />
  {:else}<p class="vazio">Nada lido.</p>{/if}
</Card>
