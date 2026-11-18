<script>
  // Chave da unica codificacao de cor do painel: a solidez da prova.
  import { SOLIDEZ, SOL_ROT } from '../lib/dados.js';
  // `papers`: os papers do desenho. A chave so lista os niveis que aparecem nele
  let { niveis = SOLIDEZ, papers = null } = $props();
  const mostra = $derived(papers ? niveis.filter((s) => papers.some((p) => p.sol === s)) : niveis);
</script>

<ul class="chave" aria-label="Cor do ponto: solidez da prova">
  <li class="rot">Prova</li>
  {#each mostra as s}<li><i class="sol {s}"></i>{SOL_ROT[s]}</li>{/each}
</ul>

<style>
  /* texto corrido e equilibrado: quando a chave quebra, nenhuma linha fica com um item so */
  .chave { display: block; text-wrap: balance; font-size: var(--fs-12); line-height: var(--lh-12); color: var(--ink2); }
  li { display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; margin: 2px var(--sp-3) 2px 0; vertical-align: middle; }
  li:last-child { margin-right: 0; }
</style>
