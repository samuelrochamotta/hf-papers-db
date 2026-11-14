<script>
  import { onMount } from 'svelte';
  import Topo from './lib/Topo.svelte';
  import Assinaturas from './lib/Assinaturas.svelte';
  import LetraMiuda from './lib/LetraMiuda.svelte';
  import PainelPaper from './lib/PainelPaper.svelte';
  import CardRadar from './cards/CardRadar.svelte';
  import CardArenas from './cards/CardArenas.svelte';
  import CardGanho from './cards/CardGanho.svelte';
  import CardVotos from './cards/CardVotos.svelte';
  import CardAdocao from './cards/CardAdocao.svelte';
  import CardRegua from './cards/CardRegua.svelte';
  import CardCusto from './cards/CardCusto.svelte';
  import { carregar, aplicaLente } from './lib/dados.js';
  import { observarTema } from './lib/tema.js';
  import { estado } from './lib/estado.svelte.js';

  onMount(() => {
    const parar = observarTema((t) => (estado.tema = t));
    carregar().then((d) => {
      estado.dados = d;
      // Comparacao inicial: os dois mais votados com mais eixos lidos.
      const lidos = (p) => Object.values(p.radar).filter((v) => v != null).length;
      estado.comparar = [...d.papers].filter((p) => lidos(p) >= 4).slice(0, 2).map((p) => p.id);
    }).catch((e) => (estado.erro = String(e)));
    return parar;
  });

  const noPeriodo = (lista, dias) => {
    if (estado.periodo === 'tudo' || !dias.length) return lista;
    const ult = dias[dias.length - 1];
    const lim = new Date(ult); lim.setDate(lim.getDate() - (+estado.periodo - 1));
    const corte = lim.toISOString().slice(0, 10);
    return lista.filter((p) => (p.d || '') >= corte);
  };
  const todos = $derived(estado.dados ? noPeriodo(estado.dados.papers, estado.dados.dias) : []);
  const faltam = $derived(estado.dados ? noPeriodo(estado.dados.faltam, estado.dados.dias) : []);
  const papers = $derived(aplicaLente(todos, estado.lente));
</script>

<Topo total={papers.length} />

<main class="wrap">
  {#if estado.erro}
    <p class="vazio">Não foi possível carregar os dados ({estado.erro}).</p>
  {:else if !estado.dados}
    <div class="esqueleto" aria-busy="true">{#each Array(6) as _}<div></div>{/each}</div>
  {:else}
    <Assinaturas papers={papers} faltam={estado.lente ? [] : faltam} />
    <div class="grade">
      <CardRadar {papers} todos={todos} />
      <CardArenas {papers} />
      <CardGanho {papers} />
      <CardVotos {papers} />
      <CardAdocao {papers} />
      <CardRegua {papers} />
      <CardCusto {papers} />
    </div>
    <LetraMiuda {papers} />
    <PainelPaper {papers} todos={todos} />
  {/if}
</main>

<style>
  main { padding-block: 4px 96px; }
  .grade { display: grid; grid-template-columns: 1fr; gap: 14px; align-items: stretch; }
  @media (min-width: 720px) { .grade { grid-template-columns: repeat(2, minmax(0, 1fr)); } .grade :global(.radar) { grid-column: span 2; } }
  @media (min-width: 1180px) { .grade { grid-template-columns: repeat(3, minmax(0, 1fr)); } .grade :global(.radar) { grid-column: span 1; } }
  :global(body.painel-aberto) .grade { grid-template-columns: repeat(auto-fill, minmax(min(100%, 330px), 1fr)); }
  :global(body.painel-aberto) .grade :global(.radar) { grid-column: auto; grid-row: auto; }
  .esqueleto { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 14px; margin-top: 20px; }
  .esqueleto div { height: 260px; border-radius: 20px; background: linear-gradient(100deg, var(--sunk) 30%, var(--surface) 50%, var(--sunk) 70%); background-size: 300% 100%; animation: brilho 1.4s linear infinite; }
  @keyframes brilho { to { background-position: -100% 0; } }
</style>
