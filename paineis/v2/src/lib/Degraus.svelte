<script>
  // Adocao em quatro degraus: quanto mais degraus acesos, mais
  // facil adotar (Configurar 4, Integrar 3, Reimplementar 2, Treinar grande 1,
  // Fora de alcance 0). E o mesmo sentido da barra da comparacao e do radar.
  let { esf } = $props();
</script>

<i class="degraus" aria-hidden="true">{#each [1, 2, 3, 4] as n}<i class:on={n <= 5 - esf}></i>{/each}</i>

<style>
  .degraus { display: inline-flex; gap: 2px; align-items: flex-end; flex: none; }
  .degraus i { width: 3px; border-radius: 1px; background: var(--line-strong); opacity: .45; }
  .degraus i:nth-child(1) { height: 5px; } .degraus i:nth-child(2) { height: 7px; } .degraus i:nth-child(3) { height: 9px; } .degraus i:nth-child(4) { height: 12px; }
  .degraus i.on { background: var(--ink); opacity: 1; }
</style>
