<script>
  // Os papers que respondem a pergunta de um quadro, pelo nome: da para abrir
  // sem cacar ponto no grafico. Passar o ponteiro acende o ponto do paper.
  import { nome } from '../lib/dados.js';
  import { estado, abrir } from '../lib/estado.svelte.js';
  // `titulo` e o rotulo escrito antes dos nomes, quando eles nao sao a resposta do numero grande
  let { papers, rotulo, valor = null, alerta = false, max = 8, titulo = '' } = $props();
</script>

{#if papers.length}
  <ul class="nomes" class:alerta aria-label={rotulo}>
    {#if titulo}<li class="resto" aria-hidden="true">{titulo}</li>{/if}
    {#each papers.slice(0, max) as p (p.id)}
      <li><button title={p.t} onclick={() => abrir(p.id)} onmouseenter={() => (estado.hover = p.id)} onmouseleave={() => (estado.hover = null)}>
        <i class="sol {p.sol}"></i><span class="um">{nome(p)}</span>{#if valor}<span class="v">{valor(p)}</span>{/if}</button></li>
    {/each}
    {#if papers.length > max}<li class="resto">e mais {papers.length - max}</li>{/if}
  </ul>
{/if}

<style>
  .nomes { display: flex; flex-wrap: wrap; gap: var(--sp-2); margin-top: var(--sp-3); }
  li { min-width: 0; max-width: 100%; }
  button { display: inline-flex; align-items: center; gap: 6px; min-height: calc(var(--ctl) - 4px); padding: 0 var(--sp-3) 0 var(--sp-2); border-radius: 999px; background: var(--sunk);
    font-size: var(--fs-12); line-height: var(--lh-12); font-weight: 500; max-width: 100%; transition: box-shadow var(--dur-1); }
  button:hover { box-shadow: inset 0 0 0 1px var(--line-strong); }
  @media (pointer: coarse) { button { position: relative; } button::after { content: ''; position: absolute; inset: -4px 0; } }      /* alvo de 44 px */
  .alerta button { background: var(--alert-soft); }
  .alerta button:hover { box-shadow: inset 0 0 0 1px var(--alert); }
  .v { font-weight: 400; color: var(--ink2); white-space: nowrap; font-variant-numeric: tabular-nums; }
  .resto { align-self: center; font-size: var(--fs-12); color: var(--ink2); }
</style>
