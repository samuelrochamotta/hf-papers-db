<script>
  // A letra miuda: o que o proprio paper admite, as ressalvas graves e as
  // manchetes que a tabela nao confirma. Abre o paper direto nos trechos.
  import Quadro from '../pecas/Quadro.svelte';
  import { curto, fmt } from '../lib/dados.js';
  import { estado, abrir } from '../lib/estado.svelte.js';
  let { papers } = $props();
  const GRAVE = ['preliminar', 'amostra_pequena', 'pesos_ficticios'];
  const TIPO = { man: 'Manchete não confere', grave: 'Ressalva grave', adm: 'Limite admitido' };
  const TIPOS = { man: ['manchete não confere', 'manchetes não conferem'], grave: ['ressalva grave', 'ressalvas graves'], adm: ['limite admitido', 'limites admitidos'] };
  const LIM = 5;
  const itens = $derived.by(() => {
    const out = [];
    for (const p of papers) {
      if (p.man && p.man.conf === false) out.push({ p, tipo: 'man', q: p.man.tr, g: p.man.n != null ? fmt(p.man.n) + (p.man.u === '%' ? '%' : '') : null });
      for (const r of p.ress) if (GRAVE.includes(r[0])) out.push({ p, tipo: 'grave', q: r[1] });
      for (const a of p.aleg) if (a[0] === 'negativa') out.push({ p, tipo: 'adm', q: a[1] });
    }
    const ordem = { man: 0, grave: 1, adm: 2 };
    return out.sort((a, b) => ordem[a.tipo] - ordem[b.tipo] || b.p.u - a.p.u);
  });
  const contagem = $derived(Object.keys(TIPO).map((k) => [k, itens.filter((i) => i.tipo === k).length]).filter(([, n]) => n));
  let todos = $state(false);
  const visiveis = $derived(todos ? itens : itens.slice(0, LIM));
</script>

<Quadro id="letra" pergunta="O que a letra miúda admite?" valor={itens.length} resposta={contagem.map(([k, n]) => `${n} ${TIPOS[k][n === 1 ? 0 : 1]}`.replace(/ /g, '\u00a0')).join(' · ')}>
  {#if itens.length}
    <ul>
      {#each visiveis as it, i (it.p.id + it.tipo + i)}
        <li><button class="neg {it.tipo}" onclick={() => abrir(it.p.id, 2)} onmouseenter={() => (estado.hover = it.p.id)} onmouseleave={() => (estado.hover = null)}>
          <span class="tipo pts"><span>{TIPO[it.tipo]}</span>{#if it.g}<span>alega <span class="num">{it.g}</span></span>{/if}</span>
          <q lang="en">{it.q}</q>
          <span class="quem"><i class="sol {it.p.sol}"></i>{curto(it.p.t, 32)}</span>
        </button></li>
      {/each}
    </ul>
    {#if itens.length > LIM}<button class="btn sec mais" onclick={() => (todos = !todos)} aria-expanded={todos}>{todos ? 'Mostrar menos' : `Ver os ${itens.length} trechos`}</button>{/if}
  {:else}
    <div class="vazio">Nada na letra miúda deste recorte.</div>
  {/if}
</Quadro>

<style>
  ul { display: grid; }
  li + li { border-top: 1px solid var(--line); }
  .neg { width: 100%; padding: var(--sp-3) 0 var(--sp-3) var(--sp-4); display: grid; gap: var(--sp-1); position: relative; border-radius: var(--r-1); transition: background var(--dur-1); }
  .neg::before { content: ''; position: absolute; left: 0; top: var(--sp-3); bottom: var(--sp-3); width: 2px; border-radius: 1px; background: var(--line-strong); }
  .neg.man::before, .neg.grave::before { background: var(--alert); }
  .neg:hover { background: var(--hover); }
  .tipo { font-size: var(--fs-12); line-height: var(--lh-12); font-weight: 500; color: var(--muted); }
  .man .tipo, .grave .tipo { color: var(--alert); }
  q { font-family: var(--f-display); font-size: var(--fs-14); line-height: var(--lh-14); font-weight: 500; quotes: '“' '”'; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
  .quem { display: flex; align-items: center; gap: 6px; font-size: var(--fs-12); line-height: var(--lh-12); color: var(--ink2); }
  .mais { margin-top: var(--sp-3); align-self: flex-start; }
</style>
