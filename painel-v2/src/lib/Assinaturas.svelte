<script>
  // Faixa de assinaturas: cada paper e o seu radar em miniatura, do mais
  // votado ao menos votado. Cor = solidez; tracejado = leitura insuficiente.
  import MiniRadar from './MiniRadar.svelte';
  import { curto } from './dados.js';
  import { corSolidez } from './tema.js';
  import { estado, abrir } from './estado.svelte.js';
  let { papers, faltam } = $props();
</script>

<section class="ass" aria-label="Papers do período">
  <div class="itens">
    {#each papers as p, i (p.id)}
      <button class="it" class:aberto={estado.sel === p.id} class:cmp={estado.comparar.includes(p.id)}
        style:animation-delay="{Math.min(i, 30) * 18}ms"
        onclick={() => abrir(p.id)} onmouseenter={() => (estado.hover = p.id)} onmouseleave={() => (estado.hover = null)}
        onfocus={() => (estado.hover = p.id)} onblur={() => (estado.hover = null)} aria-label="{p.t}, {p.u} votos">
        <MiniRadar radar={p.radar} cor={corSolidez(estado.tema, p.sol)} tracejado={p.sol === 'sem_leitura'} aceso={estado.hover === p.id} />
        <span class="nome">{curto(p.t)}</span>
        <span class="u mono">{p.u}</span>
      </button>
    {/each}
    {#each faltam as f (f.id)}
      <a class="it falta" href="https://arxiv.org/abs/{f.id}" target="_blank" rel="noopener" aria-label="{f.t}: não lido">
        <span class="nl" aria-hidden="true"></span>
        <span class="nome">{curto(f.t)}</span>
        <span class="u mono">{f.u}</span>
      </a>
    {/each}
  </div>
</section>

<style>
  .ass { margin: 14px 0 16px; }
  .itens { display: grid; grid-auto-flow: column; grid-auto-columns: 78px; gap: 6px; overflow-x: auto; padding: 4px 2px 10px; scroll-snap-type: x proximity; scrollbar-width: thin; }
  @media (min-width: 1100px) { .itens { grid-auto-flow: row; grid-template-columns: repeat(auto-fill, minmax(78px, 1fr)); overflow: visible; } }
  .it { scroll-snap-align: start; display: grid; justify-items: center; gap: 3px; padding: 8px 4px 6px; border-radius: 14px; text-decoration: none;
    background: var(--surface); box-shadow: 0 0 0 1px var(--ring); animation: sobe .5s cubic-bezier(.2,.8,.2,1) both;
    transition: transform .25s cubic-bezier(.2,.8,.2,1), box-shadow .2s; }
  .it:hover { transform: translateY(-3px); box-shadow: 0 0 0 1px var(--ring), 0 8px 20px rgba(0,0,0,.1); }
  .it.aberto { box-shadow: 0 0 0 2px var(--ink); }
  .it.cmp { box-shadow: 0 0 0 2px var(--accent); }
  .nome { font-size: 10.5px; line-height: 1.15; text-align: center; color: var(--ink2); max-width: 70px; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; min-height: 24px; }
  .u { font-size: 10px; color: var(--muted); }
  .falta { opacity: .55; }
  .nl { width: 44px; height: 44px; border-radius: 50%; border: 1.5px dashed var(--s-nada); }
  @keyframes sobe { from { opacity: 0; transform: translateY(8px) scale(.96); } }
</style>
