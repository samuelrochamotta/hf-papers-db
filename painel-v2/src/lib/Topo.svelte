<script>
  // Barra fixa: marca, onde estou (secoes), recorte (periodo e filtro), tema.
  import { onMount } from 'svelte';
  import { slide } from 'svelte/transition';
  import Icone from './Icone.svelte';
  import Legenda from './Legenda.svelte';
  import { rotuloLente, intervalo, plural } from './dados.js';
  import { estado, aplicarTema, mov } from './estado.svelte.js';
  let { total, base, dias = [] } = $props();

  const SECOES = [['papers', 'Papers'], ['comparar', 'Comparar'], ['resultados', 'Resultados'], ['prova', 'Prova'], ['adocao', 'Adoção']];
  let atual = $state('papers');

  onMount(() => {
    // "voce esta aqui": a ultima secao cujo topo ja passou da barra fixa
    let quadro = 0;
    const medir = () => {
      cancelAnimationFrame(quadro);
      quadro = requestAnimationFrame(() => {
        let v = SECOES[0][0];
        for (const [id] of SECOES) { const el = document.getElementById(id); if (el && el.getBoundingClientRect().top < 140) v = id; }
        if (innerHeight + scrollY >= document.documentElement.scrollHeight - 4) v = SECOES[SECOES.length - 1][0];
        atual = v;
      });
    };
    addEventListener('scroll', medir, { passive: true }); addEventListener('resize', medir); medir();
    return () => { removeEventListener('scroll', medir); removeEventListener('resize', medir); cancelAnimationFrame(quadro); };
  });

  const escuro = $derived(estado.tema.escuro);
  const PERIODOS = [['7', '7 dias'], ['14', '14 dias'], ['tudo', 'Tudo']];
</script>

<header class="topo">
  <div class="wrap linha">
    <a class="marca" href="#papers" aria-label="Papers lidos, início">
      <svg class="logo" viewBox="0 0 24 24" aria-hidden="true">
        <polygon points="12,2.5 20.2,7.25 20.2,16.75 12,21.5 3.8,16.75 3.8,7.25" class="l-grade" />
        <polygon points="12,5.5 18,9.2 16.4,15.6 12,17.2 6.6,14.4 7.4,8.6" class="l-forma" />
      </svg>
      <span class="nome">Papers lidos</span>
    </a>

    <nav class="secoes" aria-label="Seções">
      {#each SECOES as [id, r]}
        <a href="#{id}" class:atual={atual === id} aria-current={atual === id ? 'location' : undefined}>{r}</a>
      {/each}
    </nav>

    <div class="dir">
      <div class="leg-topo"><Legenda /></div>
      <div class="seg" role="group" aria-label="Período">
        {#each PERIODOS as [v, r]}
          <button aria-pressed={estado.periodo === v} onclick={() => (estado.periodo = v)}>{r}</button>
        {/each}
      </div>
      <button class="icon-btn" onclick={() => aplicarTema(escuro ? 'light' : 'dark')}
        aria-label={escuro ? 'Usar tema claro' : 'Usar tema escuro'} title={escuro ? 'Tema claro' : 'Tema escuro'}>
        <Icone nome={escuro ? 'sol' : 'lua'} />
      </button>
    </div>
  </div>

  <div class="wrap recorte" aria-live="polite">
    <span class="contagem">
      {#if estado.lente}
        <b class="num">{total}</b> de {plural(base, 'paper', 'papers')}
      {:else}
        <b class="num">{plural(total, 'paper lido', 'papers lidos')}</b>
      {/if}
      <span class="sep">·</span>{intervalo(dias[0], dias[dias.length - 1])}
    </span>
    {#if estado.lente}
      <span class="chip ativo" transition:slide={{ axis: 'x', duration: mov(200) }}>
        {rotuloLente(estado.lente)}
        <button class="x" aria-label="Tirar o filtro" onclick={() => (estado.lente = null)}><Icone nome="x" /></button>
      </span>
    {/if}
  </div>
</header>

<style>
  .topo { position: sticky; top: 0; z-index: 9; padding-top: env(safe-area-inset-top, 0px);
    background: var(--bg);
    border-bottom: 1px solid var(--line); }
  .linha { display: flex; align-items: center; gap: var(--s-4); height: 56px; }
  .marca { display: flex; align-items: center; gap: 10px; text-decoration: none; flex: none; }
  .logo { width: 24px; height: 24px; }
  .l-grade { fill: none; stroke: var(--line-strong); stroke-width: 1.4; }
  .l-forma { fill: var(--s-firme); opacity: .9; }
  .nome { font-family: var(--display); font-weight: 600; font-size: 19px; letter-spacing: -.01em; }

  .secoes { display: none; gap: 2px; margin-left: var(--s-6); }
  .secoes a { position: relative; height: var(--ctl); display: inline-flex; align-items: center; padding: 0 10px; border-radius: var(--r);
    font-size: var(--t-13); font-weight: 500; color: var(--muted); text-decoration: none; transition: color var(--dur-1) var(--ease), background var(--dur-1) var(--ease); }
  .secoes a:hover { color: var(--ink); background: var(--sunk); }
  .secoes a.atual { color: var(--ink); }
  .secoes a.atual::after { content: ''; position: absolute; left: 10px; right: 10px; bottom: -12px; height: 2px; border-radius: 2px; background: var(--ink); }
  @media (min-width: 980px) { .secoes { display: flex; } }

  .dir { margin-left: auto; display: flex; align-items: center; gap: var(--s-3); }
  .leg-topo { display: none; }
  @media (min-width: 1320px) { .leg-topo { display: block; padding-right: var(--s-2); border-right: 1px solid var(--line); margin-right: var(--s-1); } }

  .recorte { display: flex; align-items: center; gap: var(--s-3); min-height: 36px; padding-block: 2px 8px; flex-wrap: wrap; font-size: var(--t-13); color: var(--muted); }
  .contagem b { color: var(--ink); font-weight: 600; }
  .sep { margin: 0 6px; color: var(--faint); }

  @media (max-width: 560px) {
    .linha { height: 52px; gap: var(--s-2); }
    .nome { font-size: 17px; }
    .seg :global(button) { padding: 0 9px; }
  }
</style>
