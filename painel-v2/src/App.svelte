<script>
  import { onMount } from 'svelte';
  import Topo from './lib/Topo.svelte';
  import Secao from './lib/Secao.svelte';
  import Legenda from './lib/Legenda.svelte';
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
  import { carregar, aplicaLente, plural } from './lib/dados.js';
  import { observarTema } from './lib/tema.js';
  import { estado, temaSalvo } from './lib/estado.svelte.js';

  // O recorte vai para o endereco: um link copiado abre o mesmo painel.
  function lerEndereco() {
    const q = new URLSearchParams(location.search);
    if (['7', '14'].includes(q.get('periodo'))) estado.periodo = q.get('periodo');
    const l = q.get('lente');
    if (l && l.includes(':')) { const [k, ...v] = l.split(':'); estado.lente = { k, v: k === 'esf' ? +v.join(':') : v.join(':') }; }
    if (q.get('paper')) estado.sel = q.get('paper');
    if (q.get('comparar')) estado.comparar = q.get('comparar').split(',').filter(Boolean).slice(0, 3);
    return q.has('comparar');
  }
  let pronto = $state(false);
  $effect(() => {
    if (!pronto) return;
    const q = new URLSearchParams();
    if (estado.periodo !== 'tudo') q.set('periodo', estado.periodo);
    if (estado.lente) q.set('lente', `${estado.lente.k}:${estado.lente.v}`);
    if (estado.sel) q.set('paper', estado.sel);
    if (estado.comparar.length) q.set('comparar', estado.comparar.join(','));
    const s = q.toString();
    history.replaceState(null, '', (s ? `?${s}` : location.pathname) + location.hash);
  });

  onMount(() => {
    temaSalvo();
    const parar = observarTema((t) => (estado.tema = t));
    const temCmp = lerEndereco();
    carregar().then((d) => {
      estado.dados = d;
      const ids = new Set(d.papers.map((p) => p.id));
      if (estado.sel && !ids.has(estado.sel)) estado.sel = null;
      estado.comparar = estado.comparar.filter((id) => ids.has(id));
      // Comparacao inicial: os dois mais votados com mais eixos lidos.
      if (!temCmp) {
        const lidos = (p) => Object.values(p.radar).filter((v) => v != null).length;
        estado.comparar = [...d.papers].filter((p) => lidos(p) >= 4).slice(0, 2).map((p) => p.id);
      }
      pronto = true;
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
  const diasRecorte = $derived.by(() => {
    const ds = todos.map((p) => p.d).filter(Boolean).sort();
    return ds.length ? [ds[0], ds[ds.length - 1]] : [];
  });
  // "claude-haiku-5-5" -> "Claude Haiku 5.5"
  const nomeModelo = (m) => String(m).split('/').pop().replace(/-(\d+)-(\d+)$/, ' $1.$2').split('-').map((w) => w[0].toUpperCase() + w.slice(1)).join(' ');
  const ORDENS = [['votos', 'Votos'], ['ganho', 'Ganho'], ['solidez', 'Solidez']];
  const geradoEm = $derived(estado.dados?.gerado_em ? new Date(estado.dados.gerado_em).toLocaleString('pt-BR', { dateStyle: 'long', timeStyle: 'short' }) : '');
</script>

<a class="pular" href="#papers">Pular para os papers</a>
<Topo total={papers.length} base={todos.length} dias={diasRecorte} />

<main class="wrap">
  {#if estado.erro}
    <div class="vazio erro">Não foi possível carregar os dados.<small class="mono">{estado.erro}</small><button onclick={() => location.reload()}>Tentar de novo</button></div>
  {:else if !estado.dados}
    <div class="esqueleto" aria-busy="true" aria-label="Carregando">
      <div class="sk t"></div>
      <div class="sk-ass">{#each Array(14) as _}<div class="sk"></div>{/each}</div>
      <div class="sk t"></div>
      <div class="sk big"></div>
      <div class="sk-2"><div class="sk card"></div><div class="sk card"></div></div>
    </div>
  {:else}
    <Secao id="papers" n="01" titulo="Papers" sub="Cada forma é o radar do paper nos seis eixos; a cor indica a solidez da prova. Clique para abrir; use o + para comparar.">
      {#snippet aside()}
        <div class="leg-sec"><Legenda /></div>
        <div class="ordem"><span class="eyebrow">Ordem</span>
          <div class="seg sm" role="group" aria-label="Ordenar papers por">
            {#each ORDENS as [v, r]}<button aria-pressed={estado.ordem === v} onclick={() => (estado.ordem = v)}>{r}</button>{/each}
          </div>
        </div>
      {/snippet}
      {#if papers.length || faltam.length}
        <Assinaturas {papers} faltam={estado.lente ? [] : faltam} />
      {:else}
        <div class="vazio">Nenhum paper neste recorte.<button onclick={() => { estado.lente = null; estado.periodo = 'tudo'; }}>Ver todos os papers</button></div>
      {/if}
    </Secao>

    <Secao id="comparar" n="02" titulo="Comparar" sub="Os seis eixos lado a lado, contra a mediana do recorte.">
      <CardRadar {papers} todos={estado.dados.papers} />
    </Secao>

    <Secao id="resultados" n="03" titulo="Resultados" sub="Onde os papers competem e por quanto vencem o melhor rival da própria tabela.">
      <div class="g2"><CardArenas {papers} /><CardGanho {papers} /></div>
    </Secao>

    <Secao id="prova" n="04" titulo="Prova" sub="Quanto a atenção acompanha a evidência, e o que os próprios papers admitem.">
      <div class="g-prova">
        <CardVotos {papers} />
        <div class="lm"><h3 class="h-lm">A letra miúda</h3><LetraMiuda {papers} /></div>
      </div>
    </Secao>

    <Secao id="adocao" n="05" titulo="Adoção" sub="O que dá para usar já, o que fica mais barato e sobre quais modelos se constrói.">
      <div class="g3"><CardAdocao {papers} /><CardCusto {papers} /><CardRegua {papers} /></div>
    </Secao>

    <footer class="rodape">
      <span>{plural(estado.dados.papers.length, 'paper lido', 'papers lidos')} na íntegra{#if estado.dados.modelo}{' '}pelo {nomeModelo(estado.dados.modelo)}{/if}.</span>
      {#if geradoEm}<span>Atualizado em {geradoEm}.</span>{/if}
      <span>Fonte: Hugging Face Daily Papers e arXiv.</span>
    </footer>

    <PainelPaper {papers} todos={estado.dados.papers} />
  {/if}
</main>

<style>
  main { padding-block: 0 var(--s-16); }
  .pular { position: absolute; left: -999px; top: 8px; z-index: 30; background: var(--ink); color: var(--surface); padding: 8px 12px; border-radius: var(--r); }
  .pular:focus { left: 8px; }
  .ordem { display: flex; align-items: center; gap: var(--s-2); }
  .leg-sec { display: block; }
  @media (min-width: 1320px) { .leg-sec { display: none; } }

  .g2, .g3, .g-prova { display: grid; grid-template-columns: 1fr; gap: var(--s-4); align-items: stretch; }
  .g-prova > :global(.card) { height: 100%; }
  @media (min-width: 860px) { .g2 { grid-template-columns: repeat(2, minmax(0, 1fr)); } .g-prova { grid-template-columns: minmax(0, 5fr) minmax(0, 7fr); } }
  @media (min-width: 860px) and (max-width: 1179px) { .g3 { grid-template-columns: repeat(2, minmax(0, 1fr)); } .g3 > :global(:last-child) { grid-column: 1 / -1; } }
  @media (min-width: 1180px) { .g3 { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
  .g2 > :global(.card), .g3 > :global(.card) { height: 100%; }
  .h-lm { font-size: var(--t-16); font-weight: 600; letter-spacing: -.011em; margin: 5px 0 var(--s-3); }

  .rodape { margin-top: var(--s-16); padding-top: var(--s-5); border-top: 1px solid var(--line); display: flex; flex-wrap: wrap; gap: 4px var(--s-4); font-size: var(--t-12); color: var(--muted); }

  .erro { margin-top: var(--s-12); }
  .erro small { display: block; color: var(--faint); }
  .esqueleto { display: grid; gap: var(--s-5); padding-top: var(--s-12); }
  .sk { border-radius: var(--r-lg); background: linear-gradient(100deg, var(--sunk) 30%, var(--hover) 50%, var(--sunk) 70%); background-size: 300% 100%; animation: brilho 1.2s linear infinite; }
  .sk.t { height: 36px; width: 220px; }
  .sk-ass { display: grid; grid-template-columns: repeat(auto-fill, minmax(112px, 1fr)); gap: var(--s-2); }
  .sk-ass .sk { height: 124px; }
  .sk.big { height: 380px; border-radius: var(--r-xl); }
  .sk-2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: var(--s-4); }
  .sk.card { height: 320px; border-radius: var(--r-xl); }
  @keyframes brilho { to { background-position: -100% 0; } }
</style>
