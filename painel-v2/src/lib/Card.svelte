<script>
  // Cartao-pergunta: pergunta, numero que responde, grafico. `filtra` diz em
  // palavras o que um clique no grafico faz (vira dica no icone de filtro).
  let { titulo, extra = null, kpi = null, children, classe = '', filtra = '', filtros = null, rodape = null } = $props();
  import { slide } from 'svelte/transition';
  let abertos = $state(false);
</script>

<article class="card {classe}">
  <header>
    <h3>{titulo}</h3>
    <div class="acoes">
      {#if extra}{@render extra()}{/if}
      {#if filtros}
        <button class="filtra" class:on={abertos} aria-expanded={abertos} title={filtra} aria-label={filtra} onclick={() => (abertos = !abertos)}>
          <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true"><path d="M2.5 4h11M4.5 8h7M6.5 12h3" /></svg>
        </button>
      {/if}
    </div>
  </header>
  {#if filtros && abertos}<div class="fl" transition:slide={{ duration: 180 }}>{@render filtros()}</div>{/if}
  {#if kpi}{@render kpi()}{/if}
  <div class="chart">{@render children()}</div>
  {#if rodape}<footer>{@render rodape()}</footer>{/if}
</article>

<style>
  header { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--s-2) var(--s-3); min-height: var(--ctl); flex-wrap: wrap; }
  h3 { flex: 1 1 220px; font-size: var(--t-16); font-weight: 600; letter-spacing: -.011em; line-height: 1.3; margin: 5px 0 0; text-wrap: balance; }
  .acoes { display: flex; align-items: center; gap: var(--s-2); flex: none; }
  .filtra { width: 28px; height: 28px; display: grid; place-items: center; border-radius: var(--r-sm); color: var(--muted); transition: background var(--dur-1), color var(--dur-1); }
  .filtra:hover { color: var(--ink); background: var(--sunk); }
  .filtra.on { color: var(--surface); background: var(--ink); }
  .fl { padding-top: var(--s-3); }
  footer { margin-top: var(--s-3); padding-top: var(--s-3); border-top: 1px solid var(--line); }
</style>
