<script>
  import Card from '../lib/Card.svelte';
  import Grafico from '../lib/Grafico.svelte';
  import { EIXOS, EIXO_DICA, median, curto, esc } from '../lib/dados.js';
  import { base } from '../lib/tema.js';
  import { estado, alternaComparar, abrir, MAX_COMPARAR } from '../lib/estado.svelte.js';

  let { papers, todos } = $props();
  const t = $derived(estado.tema);
  const porId = $derived(new Map(todos.map((p) => [p.id, p])));
  const sel = $derived(estado.comparar.map((id) => porId.get(id)).filter(Boolean));
  const cores = $derived([t.compare1, t.compare2, t.compare3]);
  const mediana = $derived(EIXOS.map(([k]) => median(papers.map((p) => p.radar[k])) ?? 0));
  const opcoes = $derived(todos.filter((p) => !estado.comparar.includes(p.id)));

  const opcao = $derived.by(() => {
    if (!t.ink) return null;
    const dados = sel.map((p, i) => ({
      name: p.t, pid: p.id,
      value: EIXOS.map(([k]) => p.radar[k] ?? 0),
      symbol: 'circle', symbolSize: 6,
      itemStyle: { color: cores[i] },
      lineStyle: { color: cores[i], width: 2.2 },
      areaStyle: { color: cores[i], opacity: 0.16 },
      emphasis: { areaStyle: { opacity: 0.32 }, lineStyle: { width: 3 } },
    }));
    return {
      ...base(t),
      tooltip: {
        ...base(t).tooltip, trigger: 'item',
        formatter: (q) => {
          if (q.data.mediana) return `<b>Mediana do período</b>`;
          const p = porId.get(q.data.pid);
          return `<b>${esc(p.t)}</b><br>` + EIXOS.map(([k, r]) =>
            `${r}: <b>${p.radar[k] == null ? 'não lido' : p.radar[k]}</b> <span style="opacity:.6">${EIXO_DICA[k]}</span>`).join('<br>');
        },
      },
      radar: {
        indicator: EIXOS.map(([, r]) => ({ name: r, max: 100 })),
        radius: '68%', center: ['50%', '52%'], splitNumber: 4, shape: 'polygon',
        axisName: { color: t.ink2, fontSize: 12, fontWeight: 500 },
        splitLine: { lineStyle: { color: t.line } },
        splitArea: { areaStyle: { color: [t.sunk, 'transparent'] } },
        axisLine: { lineStyle: { color: t.line } },
      },
      series: [{
        type: 'radar', universalTransition: true,
        data: [
          { name: 'Mediana', mediana: true, value: mediana, symbol: 'none',
            lineStyle: { color: t.muted, type: [4, 4], width: 1.2 }, areaStyle: { opacity: 0 }, silent: true },
          ...dados,
        ],
      }],
    };
  });
  let escolha = $state('');
  function adicionar() { if (escolha) { alternaComparar(escolha); escolha = ''; } }
</script>

<Card titulo="Compare papers" classe="radar">
  {#snippet extra()}
    <label class="add">
      <span class="vh">Adicionar paper à comparação</span>
      <select bind:value={escolha} onchange={adicionar} disabled={!opcoes.length}>
        <option value="">+ paper</option>
        {#each opcoes as p (p.id)}<option value={p.id}>{curto(p.t)}</option>{/each}
      </select>
    </label>
  {/snippet}
  {#if opcao}<Grafico {opcao} altura={320} rotulo="Radar comparando papers selecionados" />{/if}
  <ul class="sel">
    {#each sel as p, i (p.id)}
      <li>
        <button class="nome" onclick={() => abrir(p.id)} onmouseenter={() => (estado.hover = p.id)} onmouseleave={() => (estado.hover = null)}>
          <span class="dot" style:background={cores[i]}></span>{curto(p.t)}
        </button>
        <button class="x" aria-label="Tirar {p.t} da comparação" onclick={() => alternaComparar(p.id)}>×</button>
      </li>
    {/each}
    <li class="med"><span class="tr"></span>Mediana</li>
    {#if sel.length < MAX_COMPARAR && sel.length}<li class="dica">até {MAX_COMPARAR}</li>{/if}
  </ul>
</Card>

<style>
  .sel { list-style: none; margin: 4px 0 0; padding: 0; display: flex; flex-wrap: wrap; gap: 6px; }
  .sel li { display: inline-flex; align-items: center; background: var(--sunk); border-radius: 999px; font-size: 12.5px; }
  .nome { display: inline-flex; align-items: center; gap: 6px; padding: 5px 4px 5px 10px; }
  .x { padding: 4px 10px 4px 6px; color: var(--muted); font-size: 15px; line-height: 1; }
  .x:hover { color: var(--ink); }
  .med, .dica { padding: 5px 10px; color: var(--muted); gap: 6px; }
  .dica { background: none !important; }
  .tr { width: 16px; border-top: 1.5px dashed var(--muted); }
  .add select { appearance: none; background: var(--sunk); border: 0; border-radius: 999px; padding: 6px 12px; font: 500 12.5px var(--body); color: var(--ink); cursor: pointer; max-width: 150px; }
</style>
