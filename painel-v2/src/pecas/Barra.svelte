<script>
  // Barra: marca, vistas, periodo e tema; embaixo, o recorte (quantos papers,
  // de quando, quanto foi lido) e os quatro filtros. O recorte fica sempre a
  // vista: quem filtra ve o efeito e desfaz no mesmo lugar. No celular so a
  // linha do recorte acompanha a rolagem; a marca sobe com a pagina.
  import Icone from '../lib/Icone.svelte';
  import Menu from './Menu.svelte';
  import { ARENA, SOLIDEZ, SOL_ROT, ESFORCO, familia, intervalo, plural, periodos, cobertura, lenteValida, rotuloLente } from '../lib/dados.js';
  import { estado, aplicarTema } from '../lib/estado.svelte.js';

  let { vistas = [], ancoras = false, papers, todos, faltam, dias } = $props();
  const escuro = $derived(estado.tema.escuro);
  const pers = $derived(periodos(estado.dados));
  const cob = $derived(cobertura(todos, faltam));

  const conta = (lista, f) => { const m = new Map(); for (const p of lista) for (const k of f(p)) m.set(k, (m.get(k) || 0) + 1); return m; };
  const facetas = $derived.by(() => {
    const ar = conta(todos, (p) => p.ar), sol = conta(todos, (p) => [p.sol]), esf = conta(todos, (p) => [p.esf]);
    const fam = conta(todos, (p) => new Set(p.ents.filter((e) => e[1] === 'modelo').map((e) => familia(e[0]))));
    const ord = (m) => [...m.entries()].sort((a, b) => b[1] - a[1]);
    return [
      ['ar', 'Arena', ord(ar).map(([k, n]) => [k, ARENA[k] || k, n])],
      ['sol', 'Prova', SOLIDEZ.filter((s) => sol.has(s)).map((s) => [s, s === 'sem_leitura' ? 'Não lida' : SOL_ROT[s], sol.get(s)])],
      ['esf', 'Adoção', [1, 2, 3, 4, 5, 0].filter((n) => esf.has(n)).map((n) => [String(n), ESFORCO[n], esf.get(n)])],
      ['fam', 'Família', ord(fam).slice(0, 12).map(([k, n]) => [k, k, n])],
    ];
  });
  const TODAS = { ar: 'Todas as arenas', sol: 'Qualquer prova', esf: 'Qualquer esforço', fam: 'Todas as famílias' };
  const valor = (k) => (estado.lente?.k === k ? String(estado.lente.v) : '');
  function escolher(k, v) { estado.lente = v === '' ? null : lenteValida(k, v); }
  const rotulo = (k, nome, itens) => { const v = valor(k); return v === '' ? nome : itens.find((i) => String(i[0]) === v)?.[1] ?? nome; };
  function ir(v) { estado.vista = v; scrollTo({ top: 0 }); }
</script>

<header class="topo">
  <div class="pagina l1">
    <h1 class="marca titulo"><a href="./">
      <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true"><path d="M10 1.5l7.4 4.25v8.5L10 18.5l-7.4-4.25v-8.5z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" /><path d="M10 5.2l4 2.3-.9 5.4-5.6 1.4-1.5-6.3z" fill="var(--sol-firme)" /></svg>
      <span>Papers lidos</span>
    </a></h1>
    {#if vistas.length}
      <nav class="vistas" aria-label={ancoras ? 'Seções' : 'Vistas'}>
        {#each vistas as [k, r, n]}
          {#if ancoras}<a href="#{k}">{r}</a>
          {:else}<button aria-current={estado.vista === k ? 'page' : undefined} onclick={() => ir(k)}>{r}{#if n}<span class="n num">{n}</span>{/if}</button>{/if}
        {/each}
      </nav>
    {/if}
    <div class="dir">
      {#if pers.length > 1}
        <div class="seg per" role="group" aria-label="Período">
          {#each pers as [k, r, n]}<button aria-pressed={estado.periodo === k} onclick={() => (estado.periodo = k)}>{r} <span class="n">{n}</span></button>{/each}
        </div>
        <span class="perm"><Menu nome="Período" rotulo={pers.find((p) => p[0] === estado.periodo)?.[1] ?? 'Tudo'} valor={estado.periodo} itens={pers} aoEscolher={(v) => (estado.periodo = v)} /></span>
      {/if}
      <button class="ico" onclick={() => aplicarTema(escuro ? 'light' : 'dark')} aria-label={escuro ? 'Usar tema claro' : 'Usar tema escuro'} title={escuro ? 'Tema claro' : 'Tema escuro'}><Icone nome={escuro ? 'sol' : 'lua'} /></button>
    </div>
  </div>
</header>
<div class="recorte" role="region" aria-label="Recorte e filtros">
  <div class="pagina l2" data-regiao="recorte">
    <p class="rec pts" aria-live="polite"><b>{papers.length === todos.length ? plural(todos.length, 'paper', 'papers') : `${papers.length} de ${plural(todos.length, 'paper', 'papers')}`}</b>{#if dias.length}<span class="mut">{intervalo(dias[0], dias[1])}</span>{/if}</p>
    <div class="filtros" role="group" aria-label="Filtrar por">
      {#each facetas as [k, nome, itens]}
        {#if itens.length > 1}
          <Menu {nome} rotulo={valor(k) !== '' ? `${nome}: ${rotulo(k, nome, itens)}` : nome} descricao={valor(k) !== '' ? `${nome}: ${rotulo(k, nome, itens)}` : `Filtrar por ${nome.toLowerCase()}`} valor={valor(k)} ligado={valor(k) !== ''}
            itens={[['', TODAS[k], todos.length], ...itens]} aoEscolher={(v) => escolher(k, v)} />
        {/if}
      {/each}
      {#if estado.lente}<button class="btn fan limpa" onclick={() => (estado.lente = null)} aria-label="Limpar o filtro {rotuloLente(estado.lente)}"><Icone nome="x" tam={12} />Limpar</button>{/if}
    </div>
    <p class="cob mut" title="Quanto do texto de cada paper foi lido">
      <span class="med" aria-hidden="true"><i style:flex={cob.inteira} class="a"></i><i style:flex={cob.parcial} class="b"></i><i style:flex={cob.insuf} class="c"></i><i style:flex={cob.fila} class="d"></i></span>
      <span class="pts"><span>Leitura: <b>{cob.inteira}</b> {cob.inteira === 1 ? 'inteira' : 'inteiras'}</span><span><b>{cob.parcial}</b> {cob.parcial === 1 ? 'parcial' : 'parciais'}</span><span><b>{cob.insuf}</b> {cob.insuf === 1 ? 'insuficiente' : 'insuficientes'}</span>{#if cob.fila}<span><b>{cob.fila}</b> na fila</span>{/if}</span>
    </p>
  </div>
</div>

{#if vistas.length && !ancoras}
  <nav class="abas" aria-label="Vistas">
    {#each vistas as [k, r, n, ic]}
      <button aria-current={estado.vista === k ? 'page' : undefined} onclick={() => ir(k)}><Icone nome={ic || 'lista'} tam={18} /><span>{r}{#if n}<span class="num n">{n}</span>{/if}</span></button>
    {/each}
  </nav>
{/if}

<style>
  .topo, .recorte { background: color-mix(in srgb, var(--bg) 92%, transparent); backdrop-filter: saturate(1.4) blur(12px); -webkit-backdrop-filter: saturate(1.4) blur(12px); }
  .topo { z-index: 11; padding-top: env(safe-area-inset-top, 0px); container: topo / inline-size; }
  .recorte { position: sticky; top: 0; z-index: 10; border-bottom: 1px solid var(--line); container: recorte / inline-size; }
  .l1 { display: flex; align-items: center; gap: var(--sp-4); height: var(--barra); }
  .marca { font-size: var(--fs-17); line-height: var(--lh-17); white-space: nowrap; }
  .marca a { display: inline-flex; align-items: center; gap: var(--sp-2); border-radius: var(--r-1); }
  .vistas { display: none; align-items: center; gap: var(--sp-1); margin-left: var(--sp-4); }
  .vistas a, .vistas button { min-height: var(--ctl); padding: 0 var(--sp-3); border-radius: var(--r-2); color: var(--ink2); font-weight: 500; display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; transition: background var(--dur-1), color var(--dur-1); }
  .vistas a:hover, .vistas button:hover { background: var(--sunk); color: var(--ink); }
  .vistas [aria-current="page"] { background: var(--accent); color: var(--on-accent); }
  .vistas [aria-current="page"]:hover { background: var(--accent); color: var(--on-accent); }
  .vistas .n { font-size: var(--fs-12); opacity: .75; }
  .dir { margin-left: auto; display: flex; align-items: center; gap: var(--sp-2); min-width: 0; }
  .per { display: none; }
  .perm { display: inline-flex; }
  .perm :global(.sel) { min-height: var(--ctl); }

  .l2 { display: flex; align-items: center; gap: var(--sp-2) var(--sp-4); min-height: 44px; padding-bottom: var(--sp-2); overflow-x: auto; scrollbar-width: none; }
  .l2::-webkit-scrollbar { display: none; }
  .rec { white-space: nowrap; }
  .rec b { font-weight: 600; }
  .filtros { display: flex; align-items: center; gap: var(--sp-2); padding: 2px; }
  .limpa { min-height: calc(var(--ctl) - 4px); padding: 0 var(--sp-2); font-size: var(--fs-12); }
  .cob { display: none; align-items: center; gap: var(--sp-2); margin-left: auto; font-size: var(--fs-12); line-height: var(--lh-12); white-space: nowrap; }
  .cob b { font-weight: 500; color: var(--ink2); }
  .med { display: inline-flex; width: 56px; height: 6px; border-radius: 3px; overflow: hidden; gap: 1px; }
  .med i { min-width: 0; } .med .a { background: var(--ink); } .med .b { background: var(--muted); } .med .c { background: var(--line-strong); opacity: .6; } .med .d { background: var(--line); }

  .abas { position: fixed; z-index: 12; left: 0; right: 0; bottom: 0; display: flex; background: var(--surface); border-top: 1px solid var(--line); padding-bottom: env(safe-area-inset-bottom, 0px); }
  .abas button { flex: 1; min-height: 56px; display: grid; justify-items: center; align-content: center; gap: 2px; font-size: var(--fs-12); line-height: var(--lh-12); font-weight: 500; color: var(--muted); border-radius: 0; }
  .abas button[aria-current="page"] { color: var(--ink); box-shadow: inset 0 2px 0 var(--accent); }
  .abas button:focus-visible { outline-offset: -2px; }
  .abas .n { margin-left: 4px; }

  /* o periodo vira seletor quando a barra aperta (tela estreita ou paper aberto ao lado) */
  @container topo (min-width: 560px) { .per { display: inline-flex; } .perm { display: none; } }
  @media (min-width: 900px) {
    .vistas { display: flex; } .abas { display: none; } .topo { position: sticky; top: 0; } .recorte { top: var(--barra); }
    @container topo (max-width: 959px) { .per { display: none; } .perm { display: inline-flex; } }
  }
  @container recorte (min-width: 1120px) { .cob { display: inline-flex; } }
</style>
