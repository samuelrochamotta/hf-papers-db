<script>
  // Numero que responde a pergunta do cartao; desliza ate o valor novo quando
  // o recorte muda.
  import { Tween } from 'svelte/motion';
  import { cubicOut } from 'svelte/easing';
  let { valor = 0, casas = 0, prefixo = '', sufixo = '', texto = '', tom = '' } = $props();
  const t = new Tween(0, { duration: 500, easing: cubicOut });
  $effect(() => { t.target = valor ?? 0; });
  const mostra = $derived((prefixo && t.current >= 0.05 ? prefixo : t.current <= -0.05 ? '−' : '')
    + Math.abs(t.current).toLocaleString('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas }));
</script>

<div class="kpi">
  <b class="num {tom}">{valor == null ? '–' : mostra}{#if sufixo && valor != null}<small>{sufixo}</small>{/if}</b>
  {#if texto}<span>{texto}</span>{/if}
</div>

<style>
  .kpi { display: flex; align-items: baseline; gap: 10px; margin: var(--s-2) 0 var(--s-4); flex-wrap: wrap; }
  b { font-family: var(--display); font-weight: 500; font-size: 44px; line-height: .95; letter-spacing: -.03em; }
  b small { font-size: .55em; letter-spacing: 0; margin-left: 1px; color: var(--ink2); }
  b.warn { color: var(--warn); }
  span { font-size: var(--t-13); color: var(--ink2); max-width: 36ch; line-height: 1.35; text-wrap: pretty; }
</style>
