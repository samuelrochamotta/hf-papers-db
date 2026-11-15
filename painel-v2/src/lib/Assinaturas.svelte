<script>
  // Indice de papers: cada paper e o seu radar em miniatura (a "assinatura").
  // Cor = solidez; tracejado = leitura insuficiente. Clicar abre o paper;
  // o botao do canto poe o paper na comparacao.
  import MiniRadar from './MiniRadar.svelte';
  import Icone from './Icone.svelte';
  import { curto, SOL_ROT } from './dados.js';
  import { corSolidez } from './tema.js';
  import { estado, abrir, alternaComparar } from './estado.svelte.js';
  let { papers, faltam } = $props();
  // no celular mostra os 9 primeiros e um botao para o resto
  let estreito = $state(false), todos = $state(false);
  $effect(() => { const mq = matchMedia('(max-width: 899px)'); estreito = mq.matches; const f = () => (estreito = mq.matches); mq.addEventListener('change', f); return () => mq.removeEventListener('change', f); });
  const LIM = 9;

  const RANK = { forte: 0, firme: 1, basico: 2, fragil: 3, sem_leitura: 4 };
  const ordenados = $derived.by(() => {
    const a = [...papers];
    if (estado.ordem === 'ganho') a.sort((x, y) => (y.radar.ganho ?? -1) - (x.radar.ganho ?? -1) || y.u - x.u);
    else if (estado.ordem === 'solidez') a.sort((x, y) => RANK[x.sol] - RANK[y.sol] || y.u - x.u);
    else a.sort((x, y) => y.u - x.u);
    return a;
  });
  const idxCmp = (id) => estado.comparar.indexOf(id);
</script>

<div class="itens" role="list">
  {#each (estreito && !todos ? ordenados.slice(0, LIM) : ordenados) as p, i (p.id)}
    {@const c = idxCmp(p.id)}
    <div class="it" role="listitem" class:aberto={estado.sel === p.id} class:aceso={estado.hover === p.id} class:cmp={c >= 0}
      style:--c={c >= 0 ? `var(--compare-${c + 1})` : null} style:animation-delay="{Math.min(i, 24) * 14}ms">
      <button class="abre" onclick={() => abrir(p.id)}
        onmouseenter={() => (estado.hover = p.id)} onmouseleave={() => (estado.hover = null)}
        onfocus={() => (estado.hover = p.id)} onblur={() => (estado.hover = null)}
        aria-label="{p.t}. {p.u} votos. Solidez {SOL_ROT[p.sol].toLowerCase()}." aria-current={estado.sel === p.id ? 'true' : undefined}>
        <MiniRadar radar={p.radar} cor={corSolidez(estado.tema, p.sol)} borda={p.sol === 'fragil' ? 'var(--s-basico)' : null} tam={56} tracejado={p.sol === 'sem_leitura'} aceso={estado.hover === p.id || estado.sel === p.id} />
        <span class="nome" title={p.t}>{curto(p.t, 34)}</span>
        <span class="u mono">{p.u}<span class="vh"> votos</span></span>
      </button>
      <button class="tg" aria-pressed={c >= 0}
        onclick={() => alternaComparar(p.id)} title={c >= 0 ? 'Tirar da comparação' : 'Comparar'}
        aria-label={c >= 0 ? `Tirar ${p.t} da comparação` : `Comparar ${p.t}`}>
        {#if c >= 0}<span class="mono">{c + 1}</span>{:else}<Icone nome="mais" tam={12} />{/if}
      </button>
    </div>
  {/each}
  {#each (estreito && !todos ? [] : faltam) as f (f.id)}
    <div role="listitem" class="li"><a class="it falta" href="https://arxiv.org/abs/{f.id}" target="_blank" rel="noopener" title="Ainda não lido: abrir no arXiv">
      <span class="abre">
        <span class="nl" aria-hidden="true"></span>
        <span class="nome" title={f.t}>{curto(f.t, 34)}</span>
        <span class="u mono">não lido ↗</span>
      </span>
    </a></div>
  {/each}
</div>
{#if estreito && ordenados.length + faltam.length > LIM}
  <button class="btn sec todos" onclick={() => (todos = !todos)} aria-expanded={todos}>{todos ? 'Mostrar menos' : `Ver os ${ordenados.length + faltam.length} papers`}</button>
{/if}

<style>
  .itens { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--s-2); padding: 2px; margin: 0 -2px; }
  @media (min-width: 600px) { .itens { grid-template-columns: repeat(auto-fill, minmax(112px, 1fr)); } }
  .todos { width: 100%; margin-top: var(--s-3); }

  .it { position: relative; scroll-snap-align: start; border-radius: var(--r-lg); background: var(--surface); box-shadow: var(--shadow-1);
    animation: sobe .45s var(--ease) both; transition: box-shadow var(--dur-2) var(--ease), transform var(--dur-2) var(--ease); text-decoration: none; }
  .abre { width: 100%; display: grid; justify-items: center; gap: 6px; padding: var(--s-3) var(--s-2) 10px; border-radius: inherit; }
  .it:hover, .it.aceso { box-shadow: var(--shadow-2); transform: translateY(-2px); }
  .it.aberto { box-shadow: 0 0 0 2px var(--ink), var(--shadow-2); }
  .it.cmp { box-shadow: 0 0 0 1.5px var(--c), var(--shadow-1); }
  .it.cmp.aberto { box-shadow: 0 0 0 2px var(--ink), var(--shadow-2); }
  .nome { font-size: var(--t-12); line-height: 1.25; text-align: center; color: var(--ink); max-width: 100%; padding-inline: 4px; overflow: hidden;
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; min-height: 30px; text-wrap: balance; }
  .u { font-size: 11px; color: var(--muted); }

  .tg { position: absolute; top: 6px; right: 6px; width: 22px; height: 22px; border-radius: 50%; display: grid; place-items: center;
    color: var(--ink2); background: var(--surface); box-shadow: inset 0 0 0 1px var(--line-strong); opacity: 0;
    transition: opacity var(--dur-1) var(--ease), background var(--dur-1), color var(--dur-1), transform var(--dur-1); }
  .tg span { font-size: 11px; font-weight: 500; }
  .it:hover .tg, .it:focus-within .tg, .tg[aria-pressed="true"] { opacity: 1; }
  .tg:hover { transform: scale(1.08); color: var(--ink); }
  .tg[aria-pressed="true"] { background: var(--c); color: var(--on-accent); box-shadow: none; }
  @media (hover: none) { .tg { opacity: 1; } }

  .li { display: contents; }
  .falta { display: block; background: transparent; box-shadow: inset 0 0 0 1px var(--line-strong); }
  .falta:hover { box-shadow: inset 0 0 0 1px var(--ink2); transform: none; }
  .falta .nome { color: var(--muted); }
  .nl { width: 56px; height: 56px; border-radius: 50%; border: 1.5px dashed var(--s-nada); }
  @keyframes sobe { from { opacity: 0; transform: translateY(6px); } }
</style>
