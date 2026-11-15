<script>
  // Uma secao da pagina: numero, titulo e o que a secao responde.
  let { id, n, titulo, sub = '', aside = null, children } = $props();
</script>

<section {id} class="secao" aria-labelledby="{id}-t">
  <header>
    <div class="t">
      <span class="n mono">{n}</span>
      <h2 id="{id}-t">{titulo}</h2>
      {#if sub}<p>{sub}</p>{/if}
    </div>
    {#if aside}<div class="aside">{@render aside()}</div>{/if}
  </header>
  {@render children()}
</section>

<style>
  .secao { padding-top: var(--s-12); scroll-margin-top: 72px; }
  header { display: flex; align-items: flex-end; justify-content: space-between; gap: var(--s-3) var(--s-6); flex-wrap: wrap;
    padding-bottom: var(--s-4); margin-bottom: var(--s-5); border-bottom: 1px solid var(--line); }
  .t { position: relative; min-width: 0; }
  .n { position: absolute; right: calc(100% + 12px); top: 14px; font-size: var(--t-12); color: var(--faint); }
  @media (max-width: 1439px) { .n { position: static; display: block; margin-bottom: 4px; } }
  h2 { font-family: var(--display); font-weight: 500; font-size: var(--t-32); line-height: 1.1; letter-spacing: -.02em; margin: 0; }
  p { margin: 6px 0 0; color: var(--ink2); font-size: var(--t-14); max-width: 62ch; }
  .aside { display: flex; align-items: center; gap: var(--s-3); flex-wrap: wrap; }
  @media (max-width: 560px) { .secao { padding-top: var(--s-10); } h2 { font-size: var(--t-25); } }
</style>
