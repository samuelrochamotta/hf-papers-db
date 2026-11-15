<script>
  import { SOLIDEZ, SOL_ROT } from './dados.js';
  import { estado, lente } from './estado.svelte.js';
  // A unica codificacao de cor do painel. Cada nivel tambem e uma lente.
  let { rotulo = true } = $props();
</script>

<div class="leg" role="group" aria-label="Cor: solidez da prova. Clique para filtrar.">
  {#if rotulo}<span class="eyebrow">Solidez</span>{/if}
  {#each SOLIDEZ as s}
    {@const on = estado.lente?.k === 'sol' && estado.lente.v === s}
    <button class:on aria-pressed={on} onclick={() => lente('sol', s)} title="Filtrar: solidez {SOL_ROT[s].toLowerCase()}">
      <i class="dot" class:nada={s === 'sem_leitura'} class:fragil={s === 'fragil'} style:background="var(--s-{s === 'sem_leitura' ? 'nada' : s})"></i>{SOL_ROT[s]}
    </button>
  {/each}
</div>

<style>
  .leg { display: flex; align-items: center; gap: 2px; flex-wrap: wrap; }
  .eyebrow { margin-right: 6px; }
  button { display: inline-flex; align-items: center; gap: 5px; height: 26px; padding: 0 7px; border-radius: 999px; font-size: var(--t-12); color: var(--ink2);
    transition: background var(--dur-1) var(--ease), color var(--dur-1) var(--ease); }
  button:hover { background: var(--sunk); color: var(--ink); }
  button.on { background: var(--ink); color: var(--surface); }
</style>
