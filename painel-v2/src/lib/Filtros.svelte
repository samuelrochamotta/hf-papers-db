<script>
  // As categorias de um grafico como botoes de verdade: o canvas do ECharts
  // nao recebe foco, entao quem navega por teclado aplica a lente por aqui.
  // Aparecem como fila de chips pelo botao de filtro do cartao.
  import { estado, lente } from './estado.svelte.js';
  let { k, itens, rotulo } = $props(); // itens: [[valor, texto]]
</script>

<div class="ft" role="group" aria-label={rotulo}>
  {#each itens as [v, r]}
    {@const on = estado.lente?.k === k && estado.lente.v === v}
    <button aria-pressed={on} class:on onclick={() => lente(k, v)}>{r}</button>
  {/each}
</div>

<style>
  .ft { display: flex; flex-wrap: wrap; gap: 6px; }
  .ft::before { content: 'Filtrar o painel por'; flex-basis: 100%; font-size: var(--t-12); color: var(--muted); }
  button { height: 26px; transition: background var(--dur-1), box-shadow var(--dur-1); padding: 0 10px; border-radius: 999px; font-size: var(--t-12); box-shadow: inset 0 0 0 1px var(--line-strong); }
  button:hover:not(.on) { background: var(--sunk); }
  button.on { background: var(--ink); color: var(--surface); box-shadow: none; }
</style>
