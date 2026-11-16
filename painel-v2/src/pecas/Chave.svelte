<script>
  // Chave da unica codificacao de cor do painel: a solidez da prova.
  import { SOLIDEZ, SOL_ROT } from '../lib/dados.js';
  let { niveis = SOLIDEZ } = $props();
</script>

<ul class="chave" aria-label="Cor do ponto: solidez da prova">
  <li class="rot">Prova</li>
  {#each niveis as s}<li><i class="sol {s}"></i>{SOL_ROT[s]}</li>{/each}
</ul>

<style>
  .chave { display: flex; flex-wrap: wrap; gap: var(--sp-1) var(--sp-3); font-size: var(--fs-12); line-height: var(--lh-12); color: var(--ink2); align-items: center; }
  li { display: inline-flex; align-items: center; gap: 6px; }
</style>
