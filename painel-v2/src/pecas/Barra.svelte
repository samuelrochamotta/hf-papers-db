<script>
  // Barra: marca, vistas, periodo e tema; embaixo, o recorte (quantos papers,
  // de quando, quanto foi lido) e os quatro filtros. O recorte fica sempre a
  // vista: quem filtra ve o efeito e desfaz no mesmo lugar. No celular so a
  // linha do recorte acompanha a rolagem; a marca sobe com a pagina.
  import Icone from '../lib/Icone.svelte';
  import Menu from './Menu.svelte';
  import { ARENA, SOLIDEZ, SOL_ROT, ESFORCO, familia, intervalo, plural, periodos, cobertura, lenteValida, rotuloLente, aplicaLentes, buscar } from '../lib/dados.js';
  import { estado, aplicarTema, lente, lentesDe, semLente } from '../lib/estado.svelte.js';

  let { vistas = [], papers, todos, faltam, dias } = $props();
  const escuro = $derived(estado.tema.escuro);
  const pers = $derived(periodos(estado.dados));
  // a leitura e a do recorte; a fila (que nao tem leitura) fica ao lado da contagem
  const ativo = $derived(estado.lentes.length > 0 || !!estado.busca.trim());
  const cob = $derived(cobertura(papers, faltam));
  function limpar() { semLente(); estado.busca = ''; }
  // altura da faixa presa: o cabecalho da tabela se prende logo abaixo dela
  let altRecorte = $state(53);
  $effect(() => { document.documentElement.style.setProperty('--recorte-alt', `${altRecorte}px`); });

  const conta = (lista, f) => { const m = new Map(); for (const p of lista) for (const k of f(p)) m.set(k, (m.get(k) || 0) + 1); return m; };
  // Cada menu conta os papers que sobram com as lentes dos outros menus: o
  // numero ao lado da opcao diz quantos papers ela traz para o recorte.
  const facetas = $derived.by(() => {
    const base = (k) => (estado.v.lentes === 'varias' ? buscar(aplicaLentes(todos, estado.lentes.filter((l) => l.k !== k)), estado.busca) : todos);
    const [bAr, bSol, bEsf, bFam] = ['ar', 'sol', 'esf', 'fam'].map(base);
    const ar = conta(bAr, (p) => p.ar), sol = conta(bSol, (p) => [p.sol]), esf = conta(bEsf, (p) => [p.esf]);
    const fam = conta(bFam, (p) => new Set(p.ents.filter((e) => e[1] === 'modelo').map((e) => familia(e[0]))));
    const ord = (m) => [...m.entries()].sort((a, b) => b[1] - a[1]);
    // a opcao ligada continua na lista mesmo se o resto do recorte a esvaziou
    const ligada = (k, itens, rot) => [...itens, ...lentesDe(k).filter((v) => !itens.some((i) => String(i[0]) === String(v))).map((v) => [String(v), rot(v), 0])];
    return [
      ['ar', 'Arena', ligada('ar', ord(ar).map(([k, n]) => [k, ARENA[k] || k, n]), (v) => ARENA[v] || v), bAr.length],
      ['sol', 'Prova', ligada('sol', SOLIDEZ.filter((s) => sol.has(s)).map((s) => [s, s === 'sem_leitura' ? 'Não lida' : SOL_ROT[s], sol.get(s)]), (v) => SOL_ROT[v]), bSol.length],
      ['esf', 'Adoção', ligada('esf', [1, 2, 3, 4, 5, 0].filter((n) => esf.has(n)).map((n) => [String(n), ESFORCO[n], esf.get(n)]), (v) => ESFORCO[v]), bEsf.length],
      ['fam', 'Família', ligada('fam', ord(fam).slice(0, 12).map(([k, n]) => [k, k, n]), (v) => v), bFam.length],
    ];
  });
  const TODAS = { ar: 'Todas as arenas', sol: 'Qualquer prova', esf: 'Qualquer esforço', fam: 'Todas as famílias' };
  const varias = $derived(estado.v.lentes === 'varias');
  const valores = (k) => lentesDe(k).map(String);
  function escolher(k, v) { const ok = v === '' ? null : lenteValida(k, v); if (ok) lente(ok.k, ok.v); else semLente(k); }
  const nomes = (k, itens) => valores(k).map((v) => itens.find((i) => String(i[0]) === v)?.[1] ?? v);
  // no botao: o nome do menu, o valor ligado ou, com mais de um, quantos sao
  const rotulo = (k, nome, itens) => { const ns = nomes(k, itens); return ns.length === 0 ? nome : ns.length === 1 ? ns[0] : `${nome} · ${ns.length}`; };
  function ir(v) { estado.vista = v; scrollTo({ top: 0 }); }
</script>

<header class="topo">
  <div class="pagina l1">
    <h1 class="marca titulo"><a href="./">
      <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true"><path d="M10 1.5l7.4 4.25v8.5L10 18.5l-7.4-4.25v-8.5z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" /><path d="M10 5.2l4 2.3-.9 5.4-5.6 1.4-1.5-6.3z" fill="var(--sol-firme)" /></svg>
      <span>Papers lidos</span>
    </a></h1>
    {#if vistas.length}
      <nav class="vistas" aria-label="Vistas">
        {#each vistas as [k, r, n]}
          <button aria-current={estado.vista === k ? 'page' : undefined} onclick={() => ir(k)}>{r}{#if n}<span class="n num">{n}</span>{/if}</button>
        {/each}
      </nav>
    {/if}
    <div class="dir">
      {#if pers.length > 1}
        <div class="seg per" role="group" aria-label="Período">
          {#each pers as [k, r, n]}<button aria-pressed={estado.periodo === k} onclick={() => (estado.periodo = k)}>{r} <span class="n">{n}</span></button>{/each}
        </div>
        <!-- o mesmo nome e a mesma contagem do seletor largo: "Tudo 28", "7 dias 10" -->
        <span class="perm"><Menu nome="Período" icone="calendario" rotulo={(pers.find((p) => p[0] === estado.periodo) ?? pers.at(-1)).slice(1, 3).join(' ')} valor={estado.periodo} itens={pers} aoEscolher={(v) => (estado.periodo = v)} /></span>
      {/if}
      <button class="ico" onclick={() => aplicarTema(escuro ? 'light' : 'dark')} aria-label={escuro ? 'Usar tema claro' : 'Usar tema escuro'} title={escuro ? 'Tema claro' : 'Tema escuro'}><Icone nome={escuro ? 'sol' : 'lua'} /></button>
    </div>
  </div>
</header>
<div class="recorte" class:ativo role="region" aria-label="Recorte e filtros" bind:offsetHeight={altRecorte}>
  <div class="pagina l2" data-regiao="recorte">
    <p class="rec pts" aria-live="polite"><b>{papers.length === todos.length ? plural(todos.length, 'paper', 'papers') : `${papers.length} de ${plural(todos.length, 'paper', 'papers')}`}</b>{#if cob.fila}<span class="fila">mais <span class="num">{cob.fila}</span> na fila</span>{/if}{#if dias.length}<span class="mut quando">{intervalo(dias[0], dias[1])}</span>{/if}</p>
    <div class="filtros" role="group" aria-label="Filtrar por">
      {#each facetas as [k, nome, itens, total]}
        {#if itens.length > 1 || valores(k).length}
          {@const vs = valores(k)}
          <Menu {nome} {varias} prefixo={vs.length === 1 ? `${nome}: ` : ''} rotulo={rotulo(k, nome, itens)} descricao={vs.length ? `${nome}: ${nomes(k, itens).join(', ')}` : `Filtrar por ${nome.toLowerCase()}`} valor={varias ? vs : vs[0] ?? ''} ligado={vs.length > 0}
            itens={[['', TODAS[k], total], ...itens]} aoEscolher={(v) => escolher(k, v)} aoTirar={() => semLente(k)} />
        {/if}
      {/each}
      {#if estado.busca.trim()}<button class="sel on achado" onclick={() => (estado.busca = '')} aria-label="Tirar a busca por {estado.busca.trim()}" title="Tirar a busca"><span class="um">“{estado.busca.trim()}”</span><Icone nome="x" tam={12} /></button>{/if}
    </div>
    {#if ativo}<button class="btn fan limpa" onclick={limpar} aria-label="Limpar {[estado.lentes.length ? `o filtro ${estado.lentes.map(rotuloLente).join(', ')}` : '', estado.busca.trim() ? `a busca por ${estado.busca.trim()}` : ''].filter(Boolean).join(' e ')}"><Icone nome="x" tam={12} />Limpar</button>{/if}
    <p class="cob mut" title="Quanto do texto de cada paper foi lido">
      <span class="med" aria-hidden="true"><i style:flex={cob.inteira} class="a"></i><i style:flex={cob.parcial} class="b"></i><i style:flex={cob.insuf} class="c"></i></span>
      <span class="pts"><span>Leitura: <b>{cob.inteira}</b> {cob.inteira === 1 ? 'inteira' : 'inteiras'}</span><span><b>{cob.parcial}</b> {cob.parcial === 1 ? 'parcial' : 'parciais'}</span><span><b>{cob.insuf}</b> com prova não lida</span></span>
    </p>
  </div>
</div>

{#if vistas.length}
  <nav class="abas" aria-label="Vistas">
    {#each vistas as [k, r, n, ic]}
      <button aria-current={estado.vista === k ? 'page' : undefined} onclick={() => ir(k)}><Icone nome={ic || 'lista'} tam={18} /><span>{r}{#if n}<span class="num n">{n}</span>{/if}</span></button>
    {/each}
  </nav>
{/if}

<style>
  /* fundo opaco: nada do que rola por baixo disputa com o recorte */
  .topo, .recorte { background: var(--bg); }
  .topo { z-index: 11; padding-top: env(safe-area-inset-top, 0px); container: topo / inline-size; }
  .recorte { position: sticky; top: 0; z-index: 10; border-bottom: 1px solid var(--line); container: recorte / inline-size; }
  .l1 { display: flex; align-items: center; gap: var(--sp-4); height: var(--barra); }
  .marca { font-size: var(--fs-17); line-height: var(--lh-17); white-space: nowrap; }
  .marca a { display: inline-flex; align-items: center; gap: var(--sp-2); border-radius: var(--r-1); position: relative; }
  .marca a::after { content: ''; position: absolute; inset: -10px 0; }                 /* alvo de 44 px */
  .vistas { display: none; align-items: center; gap: var(--sp-1); margin-left: var(--sp-4); }
  .vistas button { min-height: var(--ctl); padding: 0 var(--sp-3); border-radius: var(--r-2); color: var(--ink2); font-weight: 500; display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; transition: background var(--dur-1), color var(--dur-1); }
  .vistas button:hover { background: var(--sunk); color: var(--ink); }
  .vistas [aria-current="page"] { background: var(--accent); color: var(--on-accent); }
  .vistas [aria-current="page"]:hover { background: var(--accent); color: var(--on-accent); }
  .vistas .n { font-size: var(--fs-12); opacity: .75; }
  .dir { margin-left: auto; display: flex; align-items: center; gap: var(--sp-2); min-width: 0; }
  .per { display: none; }
  .perm { display: inline-flex; }
  .perm :global(.sel) { min-height: var(--ctl); }

  .l2 { display: flex; align-items: center; gap: var(--sp-2) var(--sp-4); min-height: 44px; padding-bottom: var(--sp-2); }
  .rec { white-space: nowrap; }
  .rec b { font-weight: 600; }
  .rec .fila { color: var(--ink2); }
  .filtros { display: flex; align-items: center; flex-wrap: wrap; gap: var(--sp-2); }
  /* estreito: a contagem ocupa a primeira linha e sobe com a pagina (top negativo);
     presa no topo fica so a linha dos filtros, todos a vista, sem rolagem lateral */
  .limpa { min-height: calc(var(--ctl) - 4px); padding: 0 var(--sp-2); font-size: var(--fs-12); }
  .achado { max-width: 180px; }
  @media (max-width: 639px) {
    /* a primeira linha tem altura fixa: sem filtro ela sobe com a pagina; com
       filtro ou busca ela fica presa, com a contagem e o Limpar a mao */
    .recorte { --l1: 36px; top: calc(-1 * (var(--l1) + var(--sp-1))); }
    .recorte.ativo { top: 0; }
    .l2 { flex-wrap: wrap; row-gap: var(--sp-2); padding-top: var(--sp-1); }      /* 8 px entre as linhas: os alvos de 44 px do Limpar e dos filtros se encostam, sem se cobrir */
    .limpa::after { inset: -4px -2px; }
    .rec { flex: 1 1 0; order: 1; height: var(--l1); display: flex; align-items: center; min-width: 0; }
    .limpa { order: 2; min-height: var(--l1); }
    .filtros { flex: 1 0 100%; order: 3; gap: var(--sp-2) 6px; }      /* 8 px entre linhas: se os filtros quebram, os alvos de 44 px se encostam sem se cobrir */
    .filtros :global(.par.tem > .sel:first-child > svg:last-child) { display: none; }      /* o filtro ligado ja tem o × ao lado: sem a seta, os quatro cabem numa linha */
    .filtros :global(.pre) { display: none; }      /* preso no topo, o filtro ligado mostra so o valor */
    .filtros :global(.sel) { padding: 0 6px 0 10px; }
  }
  .cob { display: none; align-items: center; gap: var(--sp-2); margin-left: auto; font-size: var(--fs-12); line-height: var(--lh-12); white-space: nowrap; }
  .cob b { font-weight: 500; color: var(--ink2); }
  .med { display: inline-flex; width: 56px; height: 6px; border-radius: 3px; overflow: hidden; gap: 1px; }
  .med i { min-width: 0; } .med .a { background: var(--ink); } .med .b { background: var(--muted); } .med .c { background: var(--line-strong); opacity: .6; }

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
