<script>
  // Sobre quem se constroi, contra quem se mede: familias de modelos (ou de
  // benchmarks) usadas como base, a esquerda, e como regua, a direita.
  import Quadro from '../pecas/Quadro.svelte';
  import Grafico from '../lib/Grafico.svelte';
  import { familia, esc } from '../lib/dados.js';
  import { base, rotNum, rotCat } from '../lib/tema.js';
  import { estado, lente, lentesDe } from '../lib/estado.svelte.js';

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
    return [...new Set([...L.keys(), ...R.keys()])]
      .map((f) => ({ f, l: L.get(f) || 0, r: R.get(f) || 0 }))
      .sort((a, b) => (b.l + b.r) - (a.l + a.r) || b.l - a.l).slice(0, 12);
  });
  const ativas = $derived(lentesDe('fam'));
  const topoBase = $derived([...linhas].sort((a, b) => b.l - a.l)[0]);
  const ROT = { modelo: ['construído sobre', 'medido contra'], bench: ['criado ou usado no treino', 'usado para avaliar'] };

  const opcao = $derived.by(() => {
    if (!t.ink || !linhas.length) return null;
    const mx = Math.max(1, ...linhas.map((l) => Math.max(l.l, l.r)));
    const apaga = (f) => (ativas.length && !ativas.includes(f) ? 0.3 : 1);
    return {
      ...base(t),
      grid: { left: 0, right: 8, top: 30, bottom: 4, containLabel: true },
      tooltip: { ...base(t).tooltip, trigger: 'axis', axisPointer: { type: 'shadow', shadowStyle: { color: t.sunk, opacity: .6 } },
        formatter: (qs) => { const l = linhas[qs[0].dataIndex];
          return `<div style="font-weight:600;margin-bottom:2px">${esc(l.f)}</div><div style="opacity:.8">${ROT[modo][0]}: <b>${l.l}</b></div><div style="opacity:.8">${ROT[modo][1]}: <b>${l.r}</b></div>`; } },
      xAxis: { type: 'value', min: -mx * 1.25, max: mx * 1.25, show: false },
      yAxis: { type: 'category', inverse: true, data: linhas.map((l) => l.f), triggerEvent: true,
        axisTick: { show: false }, axisLine: { show: false },
        axisLabel: { ...rotCat(t), margin: 12, formatter: (v) => (ativas.length && !ativas.includes(v) ? `{off|${v}}` : v), rich: { off: { color: t.muted, fontSize: 12, fontFamily: t.fUi } } } },
      series: [
        { type: 'bar', stack: 'x', barWidth: 12, data: linhas.map((l) => ({ value: -l.l, fam: l.f, itemStyle: { opacity: apaga(l.f) } })),
          itemStyle: { color: t.ink, borderRadius: [2, 0, 0, 2] }, cursor: 'pointer', emphasis: { disabled: true },
          label: { show: true, position: 'left', formatter: (q) => (q.value ? -q.value : ''), ...rotNum(t) } },
        { type: 'bar', stack: 'x', barWidth: 12, data: linhas.map((l) => ({ value: l.r, fam: l.f, itemStyle: { opacity: apaga(l.f) } })),
          itemStyle: { color: t.lineStrong, borderRadius: [0, 2, 2, 0] }, cursor: 'pointer', emphasis: { disabled: true },
          label: { show: true, position: 'right', formatter: (q) => q.value || '', ...rotNum(t) } },
        // o eixo do zero e os dois titulos, um de cada lado dele
        { type: 'custom', silent: true, z: 1, tooltip: { show: false }, data: [[0, 0]],
          renderItem: (q, api) => { const x = api.coord([0, 0])[0], a = q.coordSys, f = `500 12px ${t.fUi}`;
            return { type: 'group', children: [
              { type: 'line', shape: { x1: x, y1: a.y - 4, x2: x, y2: a.y + a.height }, style: { stroke: t.lineStrong, lineWidth: 1 } },
              { type: 'text', x: x - 8, y: a.y - 22, style: { text: ROT[modo][0], fill: t.muted, font: f, align: 'right' } },
              { type: 'text', x: x + 8, y: a.y - 22, style: { text: ROT[modo][1], fill: t.muted, font: f } },
            ] }; } },
      ],
    };
  });
  const clicar = (q) => {
    const f = q.componentType === 'yAxis' ? q.value : q.data?.fam;
    if (f) { lente('fam', f); return true; }
  };
</script>

<Quadro id="regua" pergunta={modo === 'modelo' ? 'Sobre quem se constrói, contra quem se mede?' : 'Que benchmarks se criam, quais se usam?'}
  valor={topoBase ? topoBase.l : 0} vazio={!linhas.length}
  resposta={topoBase && topoBase.l ? `${topoBase.l === 1 ? 'paper' : 'papers'} ${modo === 'modelo' ? (topoBase.l === 1 ? 'parte de' : 'partem de') : (topoBase.l === 1 ? 'cria ou treina com' : 'criam ou treinam com')} ${topoBase.f}`
    : modo === 'modelo' ? 'papers dizem de que modelo partem' : 'papers criam benchmark ou treinam com um'}>
  {#snippet extra()}
    <div class="seg" role="group" aria-label="Tipo de entidade">
      <button aria-pressed={modo === 'modelo'} onclick={() => (modo = 'modelo')}>Modelos</button>
      <button aria-pressed={modo === 'bench'} onclick={() => (modo = 'bench')}>Benchmarks</button>
    </div>
  {/snippet}
  {#if opcao}<Grafico {opcao} altura={Math.max(160, linhas.length * 26 + 40)} aoClicar={clicar} rotulo="Famílias usadas como base, à esquerda, e como régua, à direita" />
  {:else}<div class="vazio">Nenhuma entidade lida neste recorte.</div>{/if}
</Quadro>
