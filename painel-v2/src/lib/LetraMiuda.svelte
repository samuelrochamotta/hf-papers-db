<script>
  // O que o proprio paper admite, ressalvas graves e manchetes que a tabela
  // nao confirma. Abre o paper direto nos trechos.
  import { slide } from 'svelte/transition';
  import { curto, fmt } from './dados.js';
  import { corSolidez } from './tema.js';
  import { estado, abrir } from './estado.svelte.js';
  let { papers } = $props();
  const GRAVE = ['preliminar', 'amostra_pequena', 'pesos_ficticios'];
  const TIPO = { adm: 'Limite admitido', grave: 'Ressalva grave', man: 'Manchete ≠ tabela' };
  const TIPOS = { adm: ['limite admitido', 'limites admitidos'], grave: ['ressalva grave', 'ressalvas graves'], man: ['manchete ≠ tabela', 'manchetes ≠ tabela'] };
  const itens = $derived.by(() => {
    const out = [];
    for (const p of papers) {
      if (p.man && p.man.conf === false) out.push({ p, tipo: 'man', q: p.man.tr, g: p.man.n != null ? fmt(p.man.n) + (p.man.u === '%' ? '%' : '') : null });
      for (const r of p.ress) if (GRAVE.includes(r[0])) out.push({ p, tipo: 'grave', q: r[1] });
      for (const a of p.aleg) if (a[0] === 'negativa') out.push({ p, tipo: 'adm', q: a[1] });
    }
    const ordem = { man: 0, grave: 1, adm: 2 };
    return out.sort((a, b) => ordem[a.tipo] - ordem[b.tipo] || b.p.u - a.p.u).slice(0, 24);
  });
  const contagem = $derived(Object.fromEntries(Object.keys(TIPO).map((k) => [k, itens.filter((i) => i.tipo === k).length])));
  let todos = $state(false);
  const visiveis = $derived(todos ? itens : itens.slice(0, 6));
</script>

{#if itens.length}
  <div class="resumo">
    {#each Object.entries(TIPO) as [k, r]}{#if contagem[k]}<span class="tag {k}"><b class="num">{contagem[k]}</b> {TIPOS[k][contagem[k] === 1 ? 0 : 1]}</span>{/if}{/each}
  </div>
  <div class="grade">
    {#each visiveis as it, i (it.p.id + it.tipo + i)}
      <button class="neg {it.tipo}" onclick={() => abrir(it.p.id, 2)} transition:slide={{ duration: 200 }}
        onmouseenter={() => (estado.hover = it.p.id)} onmouseleave={() => (estado.hover = null)}>
        <span class="topo"><span class="tipo">{TIPO[it.tipo]}</span>{#if it.g}<span class="g mono">alega {it.g}</span>{/if}</span>
        <q lang="en">{it.q}</q>
        <span class="quem"><i class="dot" class:nada={it.p.sol === 'sem_leitura'} class:fragil={it.p.sol === 'fragil'} style:background={corSolidez(estado.tema, it.p.sol)}></i>{curto(it.p.t, 28)}<span class="ir" aria-hidden="true">Ver trecho →</span></span>
      </button>
    {/each}
  </div>
  {#if itens.length > 6}
    <button class="btn sec mais" onclick={() => (todos = !todos)} aria-expanded={todos}>{todos ? 'Mostrar menos' : `Ver todos os ${itens.length}`}</button>
  {/if}
{:else}
  <div class="vazio">Nada na letra miúda deste recorte.</div>
{/if}

<style>
  .resumo { display: flex; gap: var(--s-2); flex-wrap: wrap; margin-bottom: var(--s-3); }
  .tag { font-size: var(--t-12); color: var(--ink2); padding: 3px 10px; border-radius: 999px; background: var(--sunk); }
  .tag.man, .tag.grave { background: var(--warn-soft); color: var(--warn); }
  .grade { display: grid; grid-template-columns: 1fr; gap: var(--s-3); }
  @media (min-width: 720px) { .grade { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
  .neg { background: var(--surface); border-radius: var(--r-lg); box-shadow: var(--shadow-1); padding: var(--s-4); display: grid; gap: var(--s-2); align-content: start;
    position: relative; overflow: hidden; transition: box-shadow var(--dur-2) var(--ease), transform var(--dur-2) var(--ease); }
  .neg::before { content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; background: var(--line-strong); }
  .neg.man::before, .neg.grave::before { background: var(--warn); }
  .neg:hover { box-shadow: var(--shadow-2); transform: translateY(-1px); }
  .topo { display: flex; align-items: baseline; justify-content: space-between; gap: var(--s-2); }
  .tipo { font-size: var(--t-11); font-weight: 500; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
  .man .tipo, .grave .tipo { color: var(--warn); }
  .g { font-size: var(--t-12); color: var(--warn); }
  q { font-family: var(--display); font-size: 17px; line-height: 1.35; color: var(--ink); display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
  q::before { content: '“'; } q::after { content: '”'; }
  .quem { display: flex; align-items: center; gap: 6px; font-size: var(--t-12); color: var(--ink2); margin-top: 2px; }
  .ir { margin-left: auto; color: var(--accent); opacity: 0; transform: translateX(-4px); transition: opacity var(--dur-2) var(--ease), transform var(--dur-2) var(--ease); }
  .neg:hover .ir, .neg:focus-visible .ir { opacity: 1; transform: none; }
  .mais { margin-top: var(--s-4); }
</style>
