<script>
  // Comparacao: o radar de seis eixos com ate 3 papers e a mediana do recorte,
  // e ao lado os mesmos numeros em tabela, para ler sem adivinhar no grafico.
  import Grafico from '../lib/Grafico.svelte';
  import Icone from '../lib/Icone.svelte';
  import { EIXOS, EIXO_DICA, median, curto, esc, radarValores } from '../lib/dados.js';
  import { base, dica } from '../lib/tema.js';
  import { estado, alternaComparar, abrir, MAX_COMPARAR } from '../lib/estado.svelte.js';

  let { papers, todos } = $props();
  const t = $derived(estado.tema);
  const porId = $derived(new Map(todos.map((p) => [p.id, p])));
  const sel = $derived(estado.comparar.map((id) => porId.get(id)).filter(Boolean));
  const cores = $derived([t.compare1, t.compare2, t.compare3]);
  const medBruta = $derived(EIXOS.map(([k]) => median(papers.map((p) => p.radar[k]))));
  const mediana = $derived(radarValores(medBruta));
  const opcoes = $derived(todos.filter((p) => !estado.comparar.includes(p.id)).sort((a, b) => b.u - a.u));
  const noRecorte = $derived(new Set(papers.map((p) => p.id)));
  const melhor = $derived(EIXOS.map(([k]) => Math.max(-1, ...sel.map((p) => p.radar[k] ?? -1))));

  const opcao = $derived.by(() => {
    if (!t.ink) return null;
    const dados = sel.map((p, i) => ({
      name: p.t, pid: p.id,
      value: radarValores(EIXOS.map(([k]) => p.radar[k])),
      // com eixo nao lido o vertice e so passagem: sem ponto para nao parecer medida
      symbol: EIXOS.some(([k]) => p.radar[k] == null) ? 'none' : 'circle', symbolSize: 6,
      itemStyle: { color: cores[i] },
      lineStyle: { color: cores[i], width: 2 },
      areaStyle: { color: cores[i], opacity: 0.12 },
      emphasis: { areaStyle: { opacity: 0.26 }, lineStyle: { width: 2.6 } },
    }));
    return {
      ...base(t),
      tooltip: {
        ...base(t).tooltip, trigger: 'item',
        formatter: (q) => {
          if (q.data.mediana) return dica('Mediana do recorte', ...EIXOS.map(([, r], i) => `${r}: <b>${medBruta[i] == null ? '–' : Math.round(medBruta[i])}</b>`));
          const p = porId.get(q.data.pid);
          return dica(esc(p.t), ...EIXOS.map(([k, r]) => `${r}: <b>${p.radar[k] == null ? 'não lido' : p.radar[k]}</b>`));
        },
      },
      radar: {
        indicator: EIXOS.map(([k, r]) => ({ name: r, max: 100 })),
        radius: '62%', center: ['50%', '52%'], splitNumber: 4, shape: 'polygon',
        axisName: { color: t.ink2, fontSize: 12, fontWeight: 500, fontFamily: t.body },
        splitLine: { lineStyle: { color: t.line } },
        splitArea: { areaStyle: { color: [t.sunk, 'transparent'] } },
        axisLine: { lineStyle: { color: t.line } },
      },
      series: [{
        type: 'radar', universalTransition: true,
        data: [
          { name: 'Mediana', mediana: true, value: mediana, symbol: 'none',
            lineStyle: { color: t.muted, type: [4, 4], width: 1.2 }, areaStyle: { opacity: 0 } },
          ...dados,
        ],
      }],
    };
  });
  let escolha = $state('');
  function adicionar() { if (escolha) { alternaComparar(escolha); escolha = ''; } }
  const v = (x) => (x == null ? null : Math.round(x));
</script>

<div class="comparar card">
  <div class="g">
    {#if opcao}<Grafico {opcao} altura={380} rotulo="Radar de seis eixos comparando os papers escolhidos com a mediana do recorte" />{/if}
  </div>

  <div class="tab">
    <div class="escolhidos">
      {#each sel as p, i (p.id)}
        <span class="chip p" style:--c={cores[i]}>
          <button class="nome" onclick={() => abrir(p.id)} onmouseenter={() => (estado.hover = p.id)} onmouseleave={() => (estado.hover = null)} title={noRecorte.has(p.id) ? `Abrir ${p.t}` : `${p.t} (fora do recorte atual)`}>
            <i class="sw"></i><span class:fora={!noRecorte.has(p.id)}>{curto(p.t)}</span>
          </button>
          <button class="x" aria-label="Tirar {p.t} da comparação" onclick={() => alternaComparar(p.id)}><Icone nome="x" /></button>
        </span>
      {/each}
      <label class="btn ghost addb" class:off={!opcoes.length}>
        <Icone nome="mais" />
        <span>{sel.length >= MAX_COMPARAR ? 'Trocar' : 'Adicionar'}</span>
        <select bind:value={escolha} onchange={adicionar} disabled={!opcoes.length} aria-label="Adicionar paper à comparação">
          <option value="">Escolha um paper</option>
          {#each opcoes as p (p.id)}<option value={p.id}>{curto(p.t)} · {p.u} votos</option>{/each}
        </select>
      </label>
      <span class="cap">{sel.length} de {MAX_COMPARAR}</span>
    </div>
    {#if !sel.length}<p class="dica">Escolha até {MAX_COMPARAR} papers aqui ou no botão <span class="mini"><Icone nome="mais" tam={10} /></span> de cada paper no índice.</p>{/if}
    <div class="cols" style:--n={sel.length + 1}>
      <div class="cab eixo"><span class="eyebrow">Eixo</span></div>
      {#each sel as p, i (p.id)}
        <div class="cab"><span class="col" title={p.t}><i class="sw" style:--c={cores[i]}></i><span>{curto(p.t, 14)}</span><span class="cm">{curto(p.t, 8)}</span></span></div>
      {/each}
      <div class="cab med"><i class="tr"></i>Mediana</div>

      {#each EIXOS as [k, r], ei}
        <div class="eixo"><b>{r}</b><small>{EIXO_DICA[k]}</small></div>
        {#each sel as p, i (p.id)}
          {@const x = v(p.radar[k])}
          <div class="val" class:top={sel.length > 1 && x != null && p.radar[k] === melhor[ei]}>
            {#if x == null}<span class="nl">não lido</span>
            {:else}<span class="mono">{x}</span><i class="bar"><i style:width="{x}%" style:background={cores[i]}></i></i>{/if}
          </div>
        {/each}
        <div class="val med"><span class="mono">{v(medBruta[ei]) ?? '–'}</span></div>
      {/each}
    </div>

  </div>
</div>

<style>
  .comparar { display: grid; grid-template-columns: 1fr; gap: var(--s-4); padding: var(--s-4); }
  @media (min-width: 980px) { .comparar { align-items: center; grid-template-columns: minmax(340px, 5fr) 7fr; gap: var(--s-6); padding: var(--s-5) var(--s-6) var(--s-5) var(--s-4); } }
  .g { min-width: 0; }
  .tab { min-width: 0; display: flex; flex-direction: column; justify-content: center; gap: var(--s-4); }
  .cols { display: grid; grid-template-columns: minmax(120px, 1.3fr) repeat(var(--n), minmax(0, 1fr)); align-items: stretch; }
  .cols > div { padding: 10px 8px; border-bottom: 1px solid var(--line); min-width: 0; display: flex; flex-direction: column; justify-content: center; }
  .cab { border-bottom-color: var(--line-strong) !important; padding-block: 0 10px !important; justify-content: flex-end !important; }
  .cab.med { flex-direction: row !important; align-items: flex-end; gap: 6px; font-size: var(--t-12); color: var(--muted); justify-content: flex-end; }
  .eixo { display: grid; gap: 1px; padding-left: 0 !important; }
  .eixo b { font-weight: 500; font-size: var(--t-14); }
  .eixo small { font-size: var(--t-12); color: var(--muted); line-height: 1.3; }
  .val { display: grid !important; grid-template-columns: 2.4ch 1fr; align-items: center; align-content: center; gap: 8px; }
  .val .mono { font-size: var(--t-13); text-align: right; }
  .val.top .mono { font-weight: 600; color: var(--ink); }
  .val.med { grid-template-columns: 1fr; text-align: right; color: var(--muted); }
  .bar { height: 6px; border-radius: 3px; background: var(--sunk); overflow: hidden; display: block; }
  .bar i { display: block; height: 100%; border-radius: 3px; transition: width var(--dur-3) var(--ease); }
  .nl { grid-column: 1 / -1; font-size: var(--t-12); color: var(--faint); font-style: italic; }
  .tr { width: 16px; border-top: 1.5px dashed var(--muted); display: inline-block; }

  .chip.p { padding-left: 2px; max-width: 100%; }
  .chip.p .nome { display: inline-flex; align-items: center; gap: 6px; min-width: 0; padding: 0 2px 0 8px; height: 100%; }
  .chip.p .nome span { overflow: hidden; text-overflow: ellipsis; }
  .fora { opacity: .6; font-style: italic; }
  .sw { width: 10px; height: 10px; border-radius: 3px; background: var(--c); flex: none; }

  .escolhidos { display: flex; align-items: center; gap: var(--s-2); flex-wrap: wrap; }
  .addb { position: relative; box-shadow: inset 0 0 0 1px var(--line-strong); border-radius: 999px; height: var(--ctl-sm); padding: 0 12px 0 10px; }
  .addb select { position: absolute; inset: 0; opacity: 0; cursor: pointer; width: 100%; font-size: 16px; }
  .addb:focus-within { outline: 2px solid var(--accent); outline-offset: 2px; }
  .col { display: inline-flex; align-items: center; gap: 6px; font-size: var(--t-12); color: var(--ink2); min-width: 0; }
  .col span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .col .sw { background: var(--c); }
  .col .cm { display: none; }
  .cap { font-size: var(--t-12); color: var(--muted); }
  .dica { flex-basis: 100%; margin: 0; font-size: var(--t-13); color: var(--ink2); }
  .mini { display: inline-grid; place-items: center; width: 16px; height: 16px; border-radius: 50%; box-shadow: inset 0 0 0 1px var(--line-strong); vertical-align: -3px; }

  @media (max-width: 560px) {
    .cols { grid-template-columns: minmax(92px, 1fr) repeat(var(--n), minmax(0, 1fr)); }
    .eixo small { display: none; }
    .val { grid-template-columns: 1fr; gap: 4px; }
    .val .mono { text-align: left; }
    .col span { display: none; }
    .col span.cm { display: inline; }
  }
</style>
