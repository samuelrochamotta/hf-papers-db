<script>
  let { titulo, extra = null, kpi = null, children, classe = '' } = $props();
</script>

<article class="card {classe}">
  <header>
    <h2>{titulo}</h2>
    {#if extra}{@render extra()}{/if}
  </header>
  {#if kpi}{@render kpi()}{/if}
  <div class="chart">{@render children()}</div>
</article>

<style>
  header { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
</style>
