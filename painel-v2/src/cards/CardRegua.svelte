<script>
  import Card from '../lib/Card.svelte';
  import Kpi from '../lib/Kpi.svelte';
  import Grafico from '../lib/Grafico.svelte';
  import Filtros from '../lib/Filtros.svelte';
  import { familia, esc } from '../lib/dados.js';
  import { base, rotNum } from '../lib/tema.js';
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
  const ativa = $derived(estado.lente?.k === 'fam' ? estado.lente.v : null);
  const topoBase = $derived([...linhas].sort((a, b) => b.l - a.l)[0]);

  const opcao = $derived.by(() => {
    if (!t.ink || !linhas.length) return null;
    const mx = Math.max(1, ...linhas.map((l) => Math.max(l.l, l.r)));
    return {
      ...base(t),
      grid: { left: 0, right: 18, top: 26, bottom: 4, containLabel: true },
      tooltip: { ...base(t).tooltip, trigger: 'axis', axisPointer: { type: 'shadow', shadowStyle: { color: t.accentSoft } },
        formatter: (qs) => { const l = linhas[qs[0].dataIndex];
          return `<div style="font-weight:600;margin-bottom:4px">${esc(qs[0].name)}</div>`
            + `<div style="opacity:.78">${modo === 'modelo' ? 'Base' : 'Criado ou usado no treino'} em <b>${l.l}</b> · ${modo === 'modelo' ? 'régua' : 'avaliação'} em <b>${l.r}</b></div>`
            + `<div style="margin-top:8px;padding-top:6px;border-top:1px solid ${t.line};color:${t.accent};font-size:11.5px">${ativa === l.f ? 'Clique para tirar o filtro' : 'Clique para filtrar tudo por ' + esc(l.f)}</div>`; } },
      xAxis: { type: 'value', min: -mx * 1.3, max: mx * 1.3, show: false },
      yAxis: { type: 'category', data: linhas.map((l) => l.f), triggerEvent: true, position: 'left',
        axisTick: { show: false }, axisLine: { show: false },
        axisLabel: { color: t.ink, fontWeight: 500, fontSize: 12, fontFamily: t.body, margin: 12,
          formatter: (v) => (ativa && ativa !== v ? `{off|${v}}` : v), rich: { off: { color: t.muted, fontSize: 12, fontFamily: t.body } } } },
      graphic: [
        { type: 'text', left: '30%', top: 4, style: { text: modo === 'modelo' ? '← parte dele' : '← cria ou treina', fill: t.muted, font: `500 11px ${t.body}` } },
        { type: 'text', right: 18, top: 4, style: { text: modo === 'modelo' ? 'compara com ele →' : 'avalia com ele →', fill: t.muted, font: `500 11px ${t.body}` } },
      ],
      series: [
        { type: 'bar', stack: 'x', barWidth: 13, data: linhas.map((l) => ({ value: -l.l, fam: l.f })),
          itemStyle: { color: t.ink2, borderRadius: [2, 0, 0, 2] }, cursor: 'pointer', emphasis: { disabled: true },
          label: { show: true, position: 'left', formatter: (q) => q.value ? -q.value : '', ...rotNum(t) } },
        { type: 'bar', stack: 'x', barWidth: 13, data: linhas.map((l) => ({ value: l.r, fam: l.f })),
          itemStyle: { color: t.faint, borderRadius: [0, 2, 2, 0] }, cursor: 'pointer', emphasis: { disabled: true },
          label: { show: true, position: 'right', formatter: (q) => q.value || '', ...rotNum(t) } },
      ],
    };
  });
  const clicar = (q) => {
    const f = q.componentType === 'yAxis' ? q.value : q.data?.fam;
    if (f) { lente('fam', f); return true; }
  };
</script>

<Card titulo={modo === 'modelo' ? 'Sobre quem se constrói, contra quem se mede?' : 'Que benchmarks se criam, quais se usam?'} filtra="Clique numa família para filtrar o painel inteiro">
  {#snippet filtros()}<Filtros k="fam" rotulo="Filtrar por família" itens={linhas.map((l) => [l.f, l.f]).reverse()} />{/snippet}
  {#snippet extra()}
    <div class="seg sm" role="group" aria-label="Tipo de entidade">
      <button aria-pressed={modo === 'modelo'} onclick={() => (modo = 'modelo')}>Modelos</button>
      <button aria-pressed={modo === 'bench'} onclick={() => (modo = 'bench')}>Benchmarks</button>
    </div>
  {/snippet}
  {#snippet kpi()}<Kpi valor={topoBase ? topoBase.l : 0} texto={topoBase && topoBase.l ? `papers ${modo === 'modelo' ? 'partem do' : 'criam ou treinam com'} ${topoBase.f}` : 'nenhuma entidade lida'} />{/snippet}
  {#if opcao}<Grafico {opcao} altura={Math.max(170, linhas.length * 27 + 34)} aoClicar={clicar} rotulo="Entidades usadas como base e como régua" />
  {:else}<div class="vazio">Nenhuma entidade lida neste recorte.</div>{/if}
</Card>
