<script>
  // Numero grande que desliza ate o valor novo quando a lente muda.
  import { Tween } from 'svelte/motion';
  import { cubicOut } from 'svelte/easing';
  let { valor = 0, casas = 0, prefixo = '', sufixo = '', texto = '' } = $props();
  const t = new Tween(0, { duration: 650, easing: cubicOut });
  $effect(() => { t.target = valor ?? 0; });
  const mostra = $derived((prefixo && t.current > 0 ? prefixo : t.current < 0 ? '−' : '')
    + Math.abs(t.current).toLocaleString('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas }) + sufixo);
</script>

<div class="kpi"><b>{valor == null ? '–' : mostra}</b>{#if texto}<span>{texto}</span>{/if}</div>
