<script>
  // Indice de papers. Cada linha e o radar do paper desenrolado: as colunas sao
  // os seis eixos, cada um na sua unidade (votos, nivel de prova, % de ganho,
  // degrau de esforco, artefatos, benchmarks). Ordenar por uma coluna responde
  // a maior parte das perguntas sem abrir nada; "nao lido" vai sempre para o
  // fim, separado, e nunca vira zero.
  // Teclado: a lista e uma grade (uma parada de Tab); setas andam, Enter abre,
  // seta para o lado alcanca o botao de comparar.
  import { tick } from 'svelte';
  import { flip } from 'svelte/animate';
  import MiniRadar from '../lib/MiniRadar.svelte';
  import Icone from '../lib/Icone.svelte';
  import Menu from './Menu.svelte';
  import { ordenar, buscar, ORDENS, comDado, ganhoDe, median, sgn, SOL_ROT, SOL_FRASE, ESFORCO, ENTREGA, CAMADA, liberados, intervalo, curto, plural, dataCurta, nBench } from '../lib/dados.js';
  import { corSolidez } from '../lib/tema.js';
  import { estado, abrir, alternaComparar, mov } from '../lib/estado.svelte.js';

  let { papers, faltam = [], forma = 'tabela', limite = 0, dens = 'm' } = $props();
  let tudo = $state(false);
  const PAGINA = 50;                 // linhas por vez; "Mostrar mais" traz outras 50
  let paginas = $state(1);
  let el = $state(null);

  const achados = $derived(buscar(papers, estado.busca));
  const ord = $derived(ordenar(achados, estado.ordem));
  const nCom = $derived(comDado(achados, estado.ordem));
  const visiveis = $derived(limite && !tudo && !estado.busca ? ord.slice(0, limite) : ord.slice(0, PAGINA * paginas));
  // Marca da mediana: nas ordens em que "acima da mediana" e uma pergunta
  // (votos e ganho), uma regua separa as linhas de cima das de baixo.
  const MED = { votos: [(p) => p.u, (v) => `${Math.round(v).toLocaleString('pt-BR')} votos`], ganho: [ganhoDe, (v) => `${sgn(v)}%`] };
  const mediana = $derived.by(() => {
    const m = MED[estado.ordem]; if (!m || estado.busca) return null;
    const vs = achados.map(m[0]).filter((v) => v != null); if (vs.length < 4) return null;
    const med = median(vs), i = ord.findIndex((p) => { const v = m[0](p); return v == null || v <= med; });
    return i > 0 ? { i, rot: m[1](med) } : null;
  });
  const letra = (id) => 'ABC'[estado.comparar.indexOf(id)] || '';
  const bench = nBench;
  const sub = (p) => [ENTREGA[p.ent] || p.ent, p.cam ? CAMADA[p.cam] || p.cam : null].filter(Boolean).join(' · ');
  const aberto = (p) => liberados(p) || (p.prom ? 'prometido' : p.radar.abertura == null ? null : 'nada');
  const nomeLongo = (p) => [p.t, `${p.u} votos`, SOL_FRASE[p.sol].toLowerCase(), ganhoDe(p) != null ? `ganho ${sgn(ganhoDe(p))}%` : null,
    p.radar.facilidade != null ? `esforço: ${ESFORCO[p.esf].toLowerCase()}` : null, liberados(p) ? `liberou ${liberados(p)}` : null].filter(Boolean).join('. ');

  // colunas da tabela: [chave de ordem, rotulo, classe]
  const COLS = [['recentes', 'Data', 'c-d'], ['votos', 'Votos', 'c-n'], ['solidez', 'Prova', 'c-s'], ['ganho', 'Ganho', 'c-n'],
    ['facilidade', 'Adoção', 'c-a'], ['abertura', 'Abertura', 'c-l'], ['amplitude', 'Amplitude', 'c-n']];
  const ROT_ORDEM = { recentes: 'data', votos: 'votos', solidez: 'prova', ganho: 'ganho', facilidade: 'adoção, da mais fácil à mais difícil', abertura: 'abertura', amplitude: 'amplitude, em benchmarks' };
  const SEM = { solidez: 'Prova não lida', ganho: 'Sem rival externo ou não lido', facilidade: 'Sem esforço medido', abertura: 'Abertura não lida', amplitude: 'Sem benchmark próprio' };

  // grade navegavel por setas (uma so parada de Tab)
  let foco = $state({ i: 0, c: 0 });
  $effect(() => { if (foco.i >= visiveis.length) foco = { i: Math.max(0, visiveis.length - 1), c: 0 }; });
  async function mover(e, i, c) {
    const n = visiveis.length; let ni = i, nc = c;
    if (e.key === 'ArrowDown') ni = Math.min(n - 1, i + 1);
    else if (e.key === 'ArrowUp' && i === 0 && forma === 'tabela' && el?.querySelector('.cab')?.offsetParent) {
      // da primeira linha, a seta para cima alcanca o cabecalho (ordenar por coluna)
      e.preventDefault(); (el.querySelector(`[data-h="${estado.ordem}"]`) || el.querySelector('[data-h]'))?.focus(); return;
    }
    else if (e.key === 'ArrowUp') ni = Math.max(0, i - 1);
    else if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') nc = c ? 0 : 1;
    else if (e.key === 'Home') ni = 0;
    else if (e.key === 'End') ni = n - 1;
    else if (e.key === 'PageDown') ni = Math.min(n - 1, i + 8);
    else if (e.key === 'PageUp') ni = Math.max(0, i - 8);
    else return;
    e.preventDefault();
    if (ni >= visiveis.length - 1 && visiveis.length < ord.length && e.key !== 'ArrowUp') { if (limite && !tudo) tudo = true; else paginas++; }
    foco = { i: ni, c: nc };
    await tick();
    el?.querySelector(`[data-i="${ni}"][data-c="${nc}"]`)?.focus();
  }
  const tab = (i, c) => (foco.i === i && foco.c === c ? 0 : -1);
  async function cabeca(e, k) {
    const ks = COLS.map((c) => c[0]), j = ks.indexOf(k);
    if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') { e.preventDefault(); el?.querySelector(`[data-h="${ks[(j + (e.key === 'ArrowRight' ? 1 : ks.length - 1)) % ks.length]}"]`)?.focus(); }
    else if (e.key === 'ArrowDown' || e.key === 'Escape') { e.preventDefault(); foco = { i: 0, c: 0 }; await tick(); el?.querySelector('[data-i="0"][data-c="0"]')?.focus(); }
  }
</script>

<div class="indice f-{forma} d-{dens}" bind:this={el}>
  <div class="ferr">
    <label class="busca"><Icone nome="busca" /><span class="vh">Buscar paper</span>
      <input type="search" placeholder="Buscar paper" bind:value={estado.busca} autocomplete="off" spellcheck="false" enterkeyhint="search" />
    </label>
    <span class="ordem"><Menu nome="Ordem" rotulo="Ordem: {ORDENS.find(([k]) => k === estado.ordem)?.[1]}" descricao="Ordenar por: {ORDENS.find(([k]) => k === estado.ordem)?.[1]}" valor={estado.ordem} itens={ORDENS} aoEscolher={(v) => (estado.ordem = v)} /></span>
  </div>

  {#if forma === 'tabela'}
    <div class="cab">
      <div class="cab-g" role="group" aria-label="Ordenar por coluna (seta para cima, a partir da primeira linha)">
        <span class="c-t rot">Paper</span>
        {#each COLS as [k, r, cl]}
          <button class="{cl}" tabindex="-1" data-h={k} aria-pressed={estado.ordem === k} aria-label="Ordenar por {ROT_ORDEM[k]}" onclick={() => (estado.ordem = k)} onkeydown={(e) => cabeca(e, k)}>{r}{#if estado.ordem === k}<Icone nome="desce" tam={12} />{/if}</button>
        {/each}
      </div>
      <span class="rot c-cmp">Comparar</span>
    </div>
  {/if}

  {#if !visiveis.length}
    <div class="vazio">{estado.busca ? `Nenhum paper com “${estado.busca}”.` : 'Nenhum paper neste recorte.'}
      {#if estado.busca}<button class="btn sec" onclick={() => (estado.busca = '')}>Limpar a busca</button>{/if}</div>
  {:else if forma === 'grade'}
    <div class="tiles" role="list">
      {#each visiveis as p (p.id)}
        <div class="tile" class:ativa={estado.sel === p.id} role="listitem">
          <button class="abre" onclick={() => abrir(p.id)} aria-label={nomeLongo(p)} onmouseenter={() => (estado.hover = p.id)} onmouseleave={() => (estado.hover = null)}>
            <MiniRadar radar={p.radar} cor={corSolidez(estado.tema, p.sol)} tam={44} tracejado={p.sol === 'sem_leitura'} />
            <span class="nome">{curto(p.t, 26)}</span><span class="num mut">{p.u}</span>
          </button>
          <button class="cmp" aria-pressed={!!letra(p.id)} aria-label="{letra(p.id) ? 'Tirar da comparação' : 'Comparar'}: {p.t}" style:--c="var(--cmp-{estado.comparar.indexOf(p.id) + 1})" onclick={() => alternaComparar(p.id)}>{#if letra(p.id)}{letra(p.id)}{:else}<Icone nome="mais" tam={12} />{/if}</button>
        </div>
      {/each}
    </div>
  {:else}
    <div class="lista" role="grid" aria-label="Papers do recorte" aria-rowcount={visiveis.length}>
      {#each visiveis as p, i (p.id)}
        {@const g = ganhoDe(p)}
        <div class="grupo" role="rowgroup" animate:flip={{ duration: mov(200) }}>
        {#if estado.ordem === 'recentes' && (i === 0 || visiveis[i - 1].d !== p.d)}
          <div class="div" role="row"><span role="gridcell">{intervalo(p.d, p.d)}</span></div>
        {:else if i === nCom && nCom > 0 && SEM[estado.ordem]}
          <div class="div" role="row"><span role="gridcell">{SEM[estado.ordem]} · {visiveis.length - nCom}</span></div>
        {:else if mediana && i === mediana.i}
          <div class="div med" role="row"><span role="gridcell">Mediana do recorte · {mediana.rot}</span></div>
        {/if}
        <div class="linha" role="row" class:ativa={estado.sel === p.id} class:aceso={estado.hover === p.id}>
          <div role="gridcell" class="g-abre">
            <button class="abre" data-i={i} data-c="0" tabindex={tab(i, 0)} aria-label={nomeLongo(p)} aria-current={estado.sel === p.id ? 'true' : undefined}
              onclick={() => abrir(p.id)} onkeydown={(e) => mover(e, i, 0)} onfocus={() => (foco = { i, c: 0 })}
              onmouseenter={() => (estado.hover = p.id)} onmouseleave={() => (estado.hover = null)}>
              <span class="glifo"><MiniRadar radar={p.radar} cor={corSolidez(estado.tema, p.sol)} tam={32} tracejado={p.sol === 'sem_leitura'} /></span>
              <span class="c-t"><span class="t um">{p.t}</span><span class="s um">{sub(p)}</span></span>
              <span class="fatos">
                <span class="c-d num">{dataCurta(p.d)}</span>
                <span class="c-n num vt">{p.u}<small> votos</small></span>
                <span class="c-s"><i class="sol {p.sol}"></i><span class:mut={p.sol === 'sem_leitura'}>{p.sol === 'sem_leitura' ? 'Não lida' : SOL_ROT[p.sol]}</span></span>
                <span class="c-n num" class:mut={g == null}>{g == null ? '–' : sgn(g) + '%'}</span>
                <span class="c-a" class:mut={p.radar.facilidade == null}>{#if p.radar.facilidade != null}<i class="degraus" aria-hidden="true">{#each [1, 2, 3, 4, 5] as n}<i class:on={p.esf >= n}></i>{/each}</i>{/if}<span class="um">{p.radar.facilidade == null ? '–' : ESFORCO[p.esf]}</span></span>
                <span class="c-l um" class:mut={!liberados(p)}>{aberto(p) ?? '–'}</span>
                <span class="c-n num" class:mut={bench(p) == null}>{bench(p) ?? '–'}</span>
              </span>
            </button>
          </div>
          <div role="gridcell" class="g-cmp">
            <button class="cmp" data-i={i} data-c="1" tabindex={tab(i, 1)} aria-pressed={!!letra(p.id)} style:--c="var(--cmp-{estado.comparar.indexOf(p.id) + 1})"
              aria-label="{letra(p.id) ? 'Tirar da comparação' : 'Comparar'}: {p.t}" title={letra(p.id) ? 'Tirar da comparação' : 'Comparar'}
              onclick={() => alternaComparar(p.id)} onkeydown={(e) => mover(e, i, 1)} onfocus={() => (foco = { i, c: 1 })}>{#if letra(p.id)}{letra(p.id)}{:else}<Icone nome="mais" tam={12} />{/if}</button>
          </div>
        </div>
        </div>
      {/each}
    </div>
  {/if}

  {#if limite && ord.length > limite && !estado.busca}
    <button class="btn sec mais" aria-expanded={tudo} onclick={() => (tudo = !tudo)}>{tudo ? 'Mostrar menos' : `Ver os ${ord.length} papers`}</button>
  {/if}

  {#if (!limite || tudo || estado.busca) && ord.length > visiveis.length}
    <button class="btn sec mais" onclick={() => paginas++}>Mostrar mais {Math.min(PAGINA, ord.length - visiveis.length)} de {ord.length - visiveis.length}</button>
  {/if}

  {#if faltam.length && !estado.busca && (!limite || tudo)}
    <div class="fila">
      <h3 class="rot pts"><span>Na fila, ainda sem leitura</span><span class="num">{faltam.length}</span></h3>
      <ul>{#each faltam as f (f.id)}<li><a class="lk um" href="https://arxiv.org/abs/{f.id}" target="_blank" rel="noopener">{f.t}</a><span class="mut v"><span class="num">{f.u}</span> votos</span></li>{/each}</ul>
    </div>
  {/if}
</div>

<style>
  .indice { container-type: inline-size; min-width: 0; }
  .ferr { display: flex; gap: var(--sp-2); align-items: center; margin-bottom: var(--sp-3); }
  .busca { flex: 1 1 120px; min-width: 0; max-width: 360px; display: flex; align-items: center; gap: var(--sp-2); min-height: var(--ctl); padding: 0 var(--sp-3); border-radius: var(--r-2);
    background: var(--surface); box-shadow: inset 0 0 0 1px var(--line-strong); color: var(--muted); transition: box-shadow var(--dur-1); }
  .busca:focus-within { box-shadow: inset 0 0 0 2px var(--focus); color: var(--ink); }
  .busca input { flex: 1; min-width: 0; border: 0; background: none; font: inherit; font-size: 16px; color: var(--ink); outline: none; padding: 0; height: calc(var(--ctl) - 4px); }
  @media (min-width: 768px) { .busca input { font-size: var(--fs-14); } }
  .busca input::placeholder { color: var(--muted); opacity: 1; }
  .busca input::-webkit-search-cancel-button { cursor: pointer; }
  .ordem { display: inline-flex; flex: none; }
  .ordem :global(.sel) { min-height: var(--ctl); }

  /* grade comum a cabecalho e linhas */
  .cab-g, .abre { display: grid; align-items: center; column-gap: var(--sp-4); grid-template-columns: 32px minmax(0, 1fr) 44px 48px 84px 64px 136px 128px 72px; }
  .cab { display: none; grid-template-columns: minmax(0, 1fr) 72px; column-gap: var(--sp-3); align-items: center; padding-bottom: var(--sp-2); border-bottom: 1px solid var(--line-strong); }
  .cab-g { padding-left: var(--sp-3); }
  .cab .c-t { grid-column: 1 / 3; }
  .cab .c-cmp { text-align: center; }
  .cab button { font-size: var(--fs-12); line-height: var(--lh-12); font-weight: 500; color: var(--muted); display: inline-flex; align-items: center; gap: 2px; min-height: var(--alvo); border-radius: var(--r-1); justify-self: start; transition: color var(--dur-1); }
  .cab button.c-n, .cab button.c-d { justify-self: end; flex-direction: row-reverse; }
  .cab button:hover { color: var(--ink); }
  .cab button[aria-pressed="true"] { color: var(--ink); font-weight: 600; }

  .lista { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-3); overflow: clip; }
  .f-tabela .lista { border-radius: 0 0 var(--r-3) var(--r-3); border-top: 0; }
  .linha { display: grid; grid-template-columns: minmax(0, 1fr) 44px; align-items: center; border-top: 1px solid var(--line); position: relative; background: var(--surface); }
  .grupo:first-child > :first-child { border-top: 0; }
  .linha:hover, .linha.aceso { background: var(--hover); }
  .linha.ativa { background: var(--sunk); }
  .linha.ativa::before { content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; background: var(--accent); }
  .abre { width: 100%; min-height: 52px; padding: 6px 0 6px var(--sp-3); text-align: left; border-radius: 0; }
  .abre:focus-visible { outline-offset: -2px; border-radius: var(--r-2); }
  .glifo { display: grid; place-items: center; }
  .c-t { display: grid; min-width: 0; }
  .t { font-weight: 500; }
  .s { font-size: var(--fs-12); line-height: var(--lh-12); color: var(--muted); }
  .fatos { display: contents; }
  .c-n, .c-d { text-align: right; justify-self: end; }
  .c-d { color: var(--muted); font-size: var(--fs-12); }
  .vt small { display: none; }
  .c-s, .c-a { display: inline-flex; align-items: center; gap: 6px; min-width: 0; }
  .mut { color: var(--muted); }
  .degraus { display: inline-flex; gap: 2px; align-items: flex-end; flex: none; }
  .degraus i { width: 3px; border-radius: 1px; background: var(--line-strong); opacity: .45; }
  .degraus i:nth-child(1) { height: 4px; } .degraus i:nth-child(2) { height: 6px; } .degraus i:nth-child(3) { height: 8px; } .degraus i:nth-child(4) { height: 10px; } .degraus i:nth-child(5) { height: 12px; }
  .degraus i.on { background: var(--ink); opacity: 1; }

  .cmp { width: 28px; height: 28px; border-radius: 50%; display: grid; place-items: center; color: var(--muted); box-shadow: inset 0 0 0 1px var(--line-strong); font-size: var(--fs-12); font-weight: 600;
    transition: background var(--dur-1), color var(--dur-1), box-shadow var(--dur-1); position: relative; }
  .cmp::after { content: ''; position: absolute; inset: -6px; }                 /* alvo de 40 px */
  .cmp:hover { color: var(--ink); background: var(--surface); box-shadow: inset 0 0 0 1.5px var(--ink); }
  .cmp[aria-pressed="true"] { background: var(--c); color: var(--surface); box-shadow: none; }
  .g-cmp { display: grid; place-items: center; }

  .div { padding: var(--sp-4) var(--sp-3) var(--sp-1); font-size: var(--fs-12); line-height: var(--lh-12); font-weight: 500; color: var(--muted); border-top: 1px solid var(--line); background: var(--bg); }

  .div.med { display: flex; align-items: center; gap: var(--sp-3); padding-block: var(--sp-2); }
  .div.med::after { content: ''; flex: 1; height: 1px; background: var(--line-strong); }

  /* estreito: os fatos descem para a segunda linha */
  .abre { grid-template-columns: 32px minmax(0, 1fr); column-gap: var(--sp-3); row-gap: 2px; }
  .glifo { grid-row: 1 / 3; align-self: start; padding-top: 2px; }
  .f-linhas .t, .f-tabela .t { white-space: normal; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
  .fatos { display: flex; flex-wrap: wrap; gap: 2px var(--sp-3); grid-column: 2; font-size: var(--fs-12); line-height: var(--lh-12); color: var(--ink2); align-items: center; }
  .fatos .c-d, .fatos .c-n:last-child, .s { display: none; }
  .fatos .c-n, .fatos .c-d { justify-self: start; }
  .vt small { display: inline; font-family: var(--f-ui); letter-spacing: 0; font-size: inherit; margin-left: .3em; }
  .fatos .mut { display: none; }
  .fatos .c-s .mut { display: inline; }
  .abre { padding-block: var(--sp-3); }

  /* largo: tabela */
  @container (min-width: 880px) {
    .f-tabela .cab { display: grid; }
    .f-tabela .linha { grid-template-columns: minmax(0, 1fr) 72px; column-gap: var(--sp-3); }
    .f-tabela .ordem { display: none; }
    .f-tabela .abre { grid-template-columns: 32px minmax(0, 1fr) 44px 48px 84px 64px 136px 128px 72px; column-gap: var(--sp-4); padding-block: 6px; }
    .f-tabela .glifo { grid-row: auto; align-self: center; padding: 0; }
    .f-tabela .fatos { display: contents; font-size: inherit; }
    .f-tabela .fatos .c-d, .f-tabela .fatos .c-n:last-child, .f-tabela .s, .f-tabela .fatos .mut { display: inline-flex; }
    .f-tabela .s, .f-tabela .t { display: block; white-space: nowrap; }
    .f-tabela .fatos .c-n, .f-tabela .fatos .c-d { justify-self: end; display: block; }
    .f-tabela .vt small { display: none; }
    .f-tabela.d-c .abre { min-height: 36px; padding-block: 2px; }
    .f-tabela.d-c .s { display: none; }
    .f-tabela.d-g .abre { min-height: 64px; }
  }

  /* miniaturas (variante do experimento de densidade) */
  .tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(112px, 1fr)); gap: var(--sp-2); }
  .tile { position: relative; background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-3); }
  .tile.ativa { border-color: var(--ink); }
  .tile .abre { display: grid; grid-template-columns: 1fr; justify-items: center; gap: var(--sp-1); padding: var(--sp-3) var(--sp-2); min-height: 124px; text-align: center; border-radius: var(--r-3); }
  .tile .nome { font-size: var(--fs-12); line-height: var(--lh-12); font-weight: 500; }
  .tile .cmp { position: absolute; top: 6px; right: 6px; width: 24px; height: 24px; }

  .mais { margin-top: var(--sp-3); width: 100%; }
  .fila { margin-top: var(--sp-6); }
  .fila ul { margin-top: var(--sp-2); display: grid; gap: var(--sp-1); }
  .fila li { display: flex; gap: var(--sp-3); justify-content: space-between; align-items: baseline; min-height: var(--alvo); min-width: 0; }
  .fila .v { white-space: nowrap; flex: none; font-size: var(--fs-12); }
</style>
