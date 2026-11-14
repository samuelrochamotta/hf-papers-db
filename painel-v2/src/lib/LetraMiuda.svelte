<script>
  import { curto, fmt } from './dados.js';
  import { corSolidez } from './tema.js';
  import { estado, abrir } from './estado.svelte.js';
  let { papers } = $props();
  const GRAVE = ['preliminar', 'amostra_pequena', 'pesos_ficticios'];
  const grande = (t) => { const m = String(t).match(/(\d+(?:[.,]\d+)?\s?%|\d+(?:[.,]\d+)?×|\b\d+(?:[.,]\d+)?\b)/); return m ? m[1].replace('.', ',') : null; };
  const itens = $derived.by(() => {
    const out = [];
    for (const p of papers) {
      for (const a of p.aleg) if (a[0] === 'negativa') out.push({ p, tipo: 'O paper admite', q: a[1], g: grande(a[1]) });
      for (const r of p.ress) if (GRAVE.includes(r[0])) out.push({ p, tipo: 'Ressalva grave', q: r[1], g: grande(r[1]) });
      if (p.man && p.man.conf === false) out.push({ p, tipo: 'Manchete não confere', q: p.man.tr, g: fmt(p.man.n) + (p.man.u === '%' ? '%' : '') });
    }
    return out.slice(0, 24);
  });
</script>

{#if itens.length}
<section class="lm">
  <h2>A letra miúda</h2>
  <div class="faixa">
    {#each itens as it, i (it.p.id + i)}
      <button class="neg" onclick={() => { abrir(it.p.id); estado.prof = 2; }}>
        <span class="tipo">{it.tipo}</span>
        {#if it.g && it.tipo !== 'O paper admite'}<span class="g">{it.g}</span>{/if}
        <q>{it.q}</q>
        <span class="quem"><i class="dot" class:nada={it.p.sol === 'sem_leitura'} style:background={corSolidez(estado.tema, it.p.sol)}></i>{curto(it.p.t)}</span>
      </button>
    {/each}
  </div>
</section>
{/if}

<style>
  .lm { margin-top: 22px; }
  h2 { font-family: var(--display); font-weight: 700; font-size: 20px; margin: 0 0 10px; letter-spacing: -.01em; }
  .faixa { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(230px, 280px); gap: 10px; overflow-x: auto; padding-bottom: 8px; scroll-snap-type: x mandatory; }
  .neg { scroll-snap-align: start; background: var(--surface); border-radius: 16px; box-shadow: 0 0 0 1px var(--ring); padding: 12px; display: grid; gap: 6px; align-content: start; transition: transform .2s, box-shadow .2s; }
  .neg:hover { transform: translateY(-2px); box-shadow: 0 0 0 1.5px var(--ink); }
  .tipo { font-size: 10.5px; letter-spacing: .05em; text-transform: uppercase; color: var(--muted); }
  .g { font-family: var(--display); font-weight: 700; font-size: 30px; line-height: 1; color: var(--warn); }
  q { font-size: 13.5px; line-height: 1.35; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
  .quem { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--ink2); }
</style>
