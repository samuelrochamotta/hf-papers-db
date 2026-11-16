<script>
  // O painel inteiro, em tres vistas: Papers (o indice), Panorama (os sete
  // quadros) e Comparar (ate tres papers nos seis eixos).
  import { onMount, tick } from 'svelte';
  import Barra from './pecas/Barra.svelte';
  import Indice from './pecas/Indice.svelte';
  import Paper from './pecas/Paper.svelte';
  import Comparar from './pecas/Comparar.svelte';
  import Arenas from './graficos/Arenas.svelte';
  import Ganho from './graficos/Ganho.svelte';
  import Prova from './graficos/Prova.svelte';
  import Adocao from './graficos/Adocao.svelte';
  import Custo from './graficos/Custo.svelte';
  import Regua from './graficos/Regua.svelte';
  import LetraMiuda from './graficos/LetraMiuda.svelte';
  import { carregar, aplicaLentes, buscar, buscarFila, plural, lenteValida, periodos, noPeriodo, cobertura, ORDENS } from './lib/dados.js';
  import { observarTema } from './lib/tema.js';
  import { estado, temaSalvo, lente, temLente } from './lib/estado.svelte.js';

  const VISTAS = [['papers', 'Papers', 'lista'], ['panorama', 'Panorama', 'graficos'], ['comparar', 'Comparar', 'radar']];
  const vistas = $derived(VISTAS.map(([k, r, ic]) => [k, r, k === 'comparar' && estado.comparar.length ? estado.comparar.length : '', ic]));

  // O recorte vai para o endereco: um link copiado abre o mesmo painel.
  function lerEndereco() {
    const q = new URLSearchParams(location.search);
    if (q.get('periodo')) estado.periodo = q.get('periodo');
    for (const l of q.getAll('lente')) {
      const [k, ...v] = l.split(':'), ok = lenteValida(k, v.join(':'));
      if (ok && !temLente(ok.k, ok.v)) lente(ok.k, ok.v);
    }
    if (q.get('paper')) estado.sel = q.get('paper');
    if (['2', '3'].includes(q.get('prof'))) estado.prof = +q.get('prof');
    if (q.get('comparar')) estado.comparar = q.get('comparar').split(',').filter(Boolean).slice(0, 3);
    if (ORDENS.some(([k]) => k === q.get('ordem'))) estado.ordem = q.get('ordem');
    if (q.get('q')) estado.busca = q.get('q').slice(0, 80);
    if (VISTAS.some(([k]) => k === q.get('vista'))) estado.vista = q.get('vista');
  }
  let pronto = $state(false);
  $effect(() => {
    if (!pronto) return;
    const q = new URLSearchParams();
    if (estado.vista !== 'papers') q.set('vista', estado.vista);
    if (estado.periodo !== 'tudo') q.set('periodo', estado.periodo);
    for (const l of estado.lentes) q.append('lente', `${l.k}:${l.v}`);
    if (estado.ordem !== 'votos') q.set('ordem', estado.ordem);
    if (estado.busca) q.set('q', estado.busca);
    if (estado.sel) { q.set('paper', estado.sel); if (estado.prof > 1) q.set('prof', estado.prof); }
    if (estado.comparar.length) q.set('comparar', estado.comparar.join(','));
    const s = q.toString();
    history.replaceState(null, '', (s ? `?${s}` : location.pathname) + location.hash);
  });

  onMount(() => {
    temaSalvo();
    const parar = observarTema((t) => (estado.tema = t));
    lerEndereco();
    carregar().then((d) => {
      estado.dados = d;
      const ids = new Set(d.papers.map((p) => p.id));
      if (estado.sel && !ids.has(estado.sel)) estado.sel = null;
      estado.comparar = estado.comparar.filter((id) => ids.has(id));
      if (!periodos(d).some(([k]) => k === estado.periodo)) estado.periodo = 'tudo';
      pronto = true;
    }).catch((e) => (estado.erro = String(e)));
    return parar;
  });

  const todos = $derived(estado.dados ? noPeriodo(estado.dados.papers, estado.dados.dias, estado.periodo) : []);
  const faltam = $derived(estado.dados ? noPeriodo(estado.dados.faltam, estado.dados.dias, estado.periodo) : []);
  // o recorte e um so em todas as vistas: periodo, filtros e busca
  const papers = $derived(buscar(aplicaLentes(todos, estado.lentes), estado.busca));
  // a fila nao tem leitura: com filtro ligado ela sai do recorte; a busca olha o titulo
  const fila = $derived(estado.lentes.length ? [] : buscarFila(faltam, estado.busca));
  const dias = $derived.by(() => { const ds = todos.map((p) => p.d).filter(Boolean).sort(); return ds.length ? [ds[0], ds[ds.length - 1]] : []; });
  const cob = $derived(estado.dados ? cobertura(todos, faltam) : null);   // o rodape conta o periodo escolhido, como a Barra
  // "claude-haiku-5-5" -> "Claude Haiku 5.5"
  const nomeModelo = (m) => String(m).split('/').pop().replace(/-(\d+)-(\d+)$/, ' $1.$2').split('-').map((w) => w[0].toUpperCase() + w.slice(1)).join(' ');
  const geradoEm = $derived(estado.dados?.gerado_em ? new Date(estado.dados.gerado_em).toLocaleString('pt-BR', { dateStyle: 'long', timeStyle: 'short' }) : '');

  // "/" leva a busca de qualquer lugar
  function atalho(e) {
    if (e.key !== '/' || e.ctrlKey || e.metaKey || e.altKey || e.target.closest?.('input,select,textarea,[contenteditable]')) return;
    e.preventDefault();
    const foca = () => document.querySelector('.busca input')?.focus();
    if (document.querySelector('.busca input')) foca(); else { estado.vista = 'papers'; tick().then(foca); }
  }
</script>

<svelte:window onkeydown={atalho} />

<div class="palco">
  <a class="pular" href="#conteudo">Pular para o conteúdo</a>
  <Barra {vistas} {papers} {todos} faltam={fila} {dias} />

  <main class="pagina" id="conteudo" tabindex="-1">
    {#if estado.erro}
      <div class="vazio erro" role="alert">Não foi possível carregar os dados.<small class="num">{estado.erro}</small><button class="btn sec" onclick={() => location.reload()}>Tentar de novo</button></div>
    {:else if !estado.dados}
      <div class="esqueleto" aria-busy="true" aria-label="Carregando">{#each Array(10) as _}<div class="sk"></div>{/each}</div>
    {:else if !todos.length && !faltam.length}
      <div class="vazio">Nenhum paper neste período.{#if estado.periodo !== 'tudo'}<button class="btn sec" onclick={() => (estado.periodo = 'tudo')}>Ver todos os períodos</button>{/if}</div>
    {:else}
      {#if estado.vista === 'papers'}
        <h2 class="vh">Papers</h2><Indice {papers} faltam={fila} periodo={todos} />
      {:else if estado.vista === 'panorama'}
        <section aria-labelledby="h-res"><h2 id="h-res" class="titulo sec-t">Resultados</h2><div class="g2"><Arenas {papers} /><Ganho {papers} periodo={todos} /></div></section>
        <section aria-labelledby="h-prova" class="bloco"><h2 id="h-prova" class="titulo sec-t">Prova</h2><div class="g2 gp"><Prova {papers} {todos} /><LetraMiuda {papers} /></div></section>
        <section aria-labelledby="h-adocao" class="bloco"><h2 id="h-adocao" class="titulo sec-t">Adoção</h2><div class="g3"><Adocao {papers} /><Custo {papers} /><Regua {papers} /></div></section>
      {:else}
        <Comparar {papers} todos={estado.dados.papers} periodo={todos} />
      {/if}

      <div class="mola"></div>
      <footer class="rodape">
        <span>{plural(todos.length, 'paper', 'papers')} no período{#if estado.dados.modelo}, lidos por {nomeModelo(estado.dados.modelo)}{/if}</span>
        {#if cob}<span>Leitura: {cob.inteira} {cob.inteira === 1 ? 'inteira' : 'inteiras'}, {cob.parcial} {cob.parcial === 1 ? 'parcial' : 'parciais'}{#if cob.resumo}, {cob.resumo} só do resumo{/if}{#if cob.fila}; mais {cob.fila} na fila{/if}</span>{/if}
        {#if geradoEm}<span>Atualizado em {geradoEm}</span>{/if}
        <span>Fonte: Hugging Face Daily Papers e arXiv</span>
      </footer>
    {/if}
  </main>
</div>
{#if estado.dados}<Paper {papers} todos={estado.dados.papers} periodo={todos} />{/if}

<style>
  .palco { min-height: 100vh; min-height: 100dvh; transition: padding-right var(--dur-3) var(--sai); }
  @media (min-width: 1024px) { :global(body.paper-aberto) .palco { padding-right: min(var(--gaveta), 44vw); } }
  /* pagina curta: o rodape assenta no pe da janela, nao no meio dela */
  .palco { display: flex; flex-direction: column; }
  main { padding-block: var(--sp-5) var(--sp-12); flex: 1 0 auto; width: 100%; display: flex; flex-direction: column; }
  main > :global(*) { flex: none; }
  .mola { flex: 1 0 var(--sp-12); }
  main:focus { outline: none; }
  @media (max-width: 899px) { main { padding-bottom: calc(56px + env(safe-area-inset-bottom, 0px) + var(--sp-8)); } }
  .pular { position: absolute; left: -999px; top: 8px; z-index: 30; background: var(--accent); color: var(--on-accent); padding: 8px 12px; border-radius: var(--r-2); font-weight: 500; }
  .pular:focus { left: 8px; }

  .sec-t { font-size: var(--fs-20); line-height: var(--lh-20); margin-bottom: var(--sp-3); }
  .bloco { margin-top: var(--sp-10); }
  .g2, .g3 { display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--calha); align-items: stretch; }
  @media (min-width: 900px) { .g2 { grid-template-columns: repeat(2, minmax(0, 1fr)); } .g3 { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
  @media (min-width: 1280px) { .g3 { grid-template-columns: repeat(3, minmax(0, 1fr)); } :global(body.paper-aberto) .g3 { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
  @media (min-width: 900px) and (max-width: 1279px) { :global(body.paper-aberto) .g2, :global(body.paper-aberto) .g3 { grid-template-columns: minmax(0, 1fr); } }

  .rodape { padding-top: var(--sp-4); border-top: 1px solid var(--line); display: flex; flex-wrap: wrap; gap: var(--sp-1) var(--sp-5); font-size: var(--fs-12); line-height: var(--lh-12); color: var(--muted); }
  .erro { margin-top: var(--sp-12); }
  .erro small { display: block; }
  .esqueleto { display: grid; gap: 1px; padding-top: var(--sp-10); }
  .sk { height: 52px; background: linear-gradient(100deg, var(--sunk) 30%, var(--hover) 50%, var(--sunk) 70%); background-size: 300% 100%; animation: brilho 1.2s linear infinite; }
  .sk:first-child { border-radius: var(--r-3) var(--r-3) 0 0; } .sk:last-child { border-radius: 0 0 var(--r-3) var(--r-3); }
  @keyframes brilho { to { background-position: -100% 0; } }
</style>
