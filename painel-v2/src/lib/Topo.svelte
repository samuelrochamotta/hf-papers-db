<script>
  import { SOLIDEZ, SOL_ROT, rotuloLente } from './dados.js';
  import { estado } from './estado.svelte.js';
  let { total } = $props();
</script>

<header class="topo">
  <div class="wrap linha">
    <div class="marca"><span class="logo" aria-hidden="true"></span>Papers</div>
    <div class="seg" role="group" aria-label="Período">
      {#each [['7', '7 dias'], ['14', '14 dias'], ['tudo', 'Tudo']] as [v, r]}
        <button aria-pressed={estado.periodo === v} onclick={() => (estado.periodo = v)}>{r}</button>
      {/each}
    </div>
    {#if estado.lente}
      <span class="lente">
        <span>{rotuloLente(estado.lente)} <b class="mono">{total}</b></span>
        <button aria-label="Tirar a lente" onclick={() => (estado.lente = null)}>×</button>
      </span>
    {/if}
    <ul class="leg" aria-label="Cor dos pontos: solidez">
      {#each SOLIDEZ as s}
        <li><i class="dot" class:nada={s === 'sem_leitura'} style:background="var(--s-{s === 'basico' ? 'basico' : s === 'sem_leitura' ? 'nada' : s})"></i>{SOL_ROT[s]}</li>
      {/each}
    </ul>
  </div>
</header>

<style>
  .topo { position: sticky; top: 0; z-index: 9; padding-top: env(safe-area-inset-top, 0px);
    background: color-mix(in srgb, var(--bg) 86%, transparent); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
    border-bottom: 1px solid var(--line); }
  .linha { display: flex; align-items: center; gap: 10px 14px; padding-block: 10px; flex-wrap: wrap; }
  .marca { font-family: var(--display); font-weight: 700; font-size: 19px; letter-spacing: -.02em; display: flex; align-items: center; gap: 8px; margin-right: auto; }
  .logo { width: 20px; height: 20px; border-radius: 6px; background: conic-gradient(from 210deg, var(--s-forte), var(--s-firme), var(--s-basico), var(--compare-2), var(--s-forte)); }
  .lente { display: inline-flex; align-items: center; gap: 8px; padding: 5px 6px 5px 12px; border-radius: 999px; background: var(--ink); color: var(--surface); font-size: 13px; animation: entra .3s cubic-bezier(.2,.8,.2,1); }
  .lente button { width: 22px; height: 22px; border-radius: 50%; display: grid; place-items: center; background: color-mix(in srgb, var(--surface) 22%, transparent); }
  .leg { list-style: none; margin: 0; padding: 0; display: flex; gap: 4px 12px; flex-wrap: wrap; font-size: 12px; color: var(--ink2); width: 100%; }
  .leg li { display: inline-flex; align-items: center; gap: 5px; }
  @media (min-width: 900px) { .leg { width: auto; order: 5; } }
  @keyframes entra { from { opacity: 0; transform: scale(.9); } }
</style>
