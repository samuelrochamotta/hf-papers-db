<script>
  // Painel do paper, em tres profundidades: Resumo (visual, quase sem texto),
  // Trechos (frases literais) e Ficha (tabelas, entidades, links). Folha de
  // baixo no celular, gaveta lateral no desktop, sobre a pagina, sem
  // reorganizar a grade por baixo.
  import Grafico from './Grafico.svelte';
  import Icone from './Icone.svelte';
  import { fly, fade } from 'svelte/transition';
  import { cubicOut } from 'svelte/easing';
  import { tick } from 'svelte';
  import {
    ordenar, ENTREGA, CAMADA, ESFORCO, EIXOS, SIG, ART, ART_EST, SOL_ROT, sgn, fmt, dataCurta, median, urlSegura, radarValores, intervalo } from './dados.js';
  import { base, corSolidez, dica } from './tema.js';
  import { estado, fechar, alternaComparar, abrir, mov } from './estado.svelte.js';

  let { papers, todos } = $props();
  const p = $derived(estado.sel ? todos.find((x) => x.id === estado.sel) : null);
  const t = $derived(estado.tema);
  let celula = $state(0);
  let largo = $state(false);
  let painel = $state(null);
  let origem = null;
  $effect(() => { const mq = matchMedia('(min-width: 1024px)'); largo = mq.matches; const f = () => (largo = mq.matches); mq.addEventListener('change', f); return () => mq.removeEventListener('change', f); });
  $effect(() => { estado.sel; celula = 0; });
  $effect(() => { document.body.classList.toggle('painel-aberto', !!p); });
  // no celular a folha e modal: o resto da pagina sai do alcance do Tab
  $effect(() => {
    const modal = !!p && !largo;
    for (const el of document.querySelectorAll('main.wrap, header.topo, a.pular')) el.inert = modal;
    return () => { for (const el of document.querySelectorAll('main.wrap, header.topo, a.pular')) el.inert = false; };
  });
  // foco: entra no painel ao abrir e volta para quem abriu ao fechar
  let aberto = false;
  $effect(() => {
    const ok = !!p;
    if (ok && !aberto) { origem = document.activeElement; tick().then(() => painel?.querySelector('h2')?.focus({ preventScroll: true })); }
    if (!ok && aberto && origem && document.contains(origem)) origem.focus({ preventScroll: true });
    aberto = ok;
  });

  // anterior / proximo na ordem do recorte
  const lista = $derived(ordenar(papers, estado.ordem));
  const pos = $derived(p ? lista.findIndex((x) => x.id === p.id) : -1);
  const vai = (d) => { const n = lista[pos + d]; if (n) abrir(n.id, estado.prof); };

  const medBruta = $derived(EIXOS.map(([k]) => median(papers.map((x) => x.radar[k]))));
  const mediana = $derived(radarValores(medBruta));
  const cor = $derived(p ? (p.sol === 'sem_leitura' ? t.sNada : p.sol === 'fragil' ? (t.escuro ? t.sBasico : t.sFirme) : corSolidez(t, p.sol)) : '');
  const naoLidos = $derived(p ? EIXOS.filter(([k]) => p.radar[k] == null).map(([, r]) => r) : []);
  const opRadar = $derived.by(() => {
    if (!p || !t.ink) return null;
    return {
      ...base(t),
      tooltip: { ...base(t).tooltip, trigger: 'item', formatter: (q) => q.data.mediana
        ? dica('Mediana do recorte', ...EIXOS.map(([, r], i) => `${r}: <b>${medBruta[i] == null ? '–' : Math.round(medBruta[i])}</b>`))
        : dica('Este paper', ...EIXOS.map(([k, r]) => `${r}: <b>${p.radar[k] == null ? 'não lido' : p.radar[k]}</b>`)) },
      radar: { indicator: EIXOS.map(([k, r]) => (p.radar[k] == null ? { name: `${r}\nnão lido`, max: 100, color: t.muted } : { name: r, max: 100 })),
        radius: '62%', center: ['50%', '50%'], splitNumber: 4,
        axisName: { color: t.ink2, fontSize: 11.5, fontFamily: t.body, lineHeight: 14 }, splitLine: { lineStyle: { color: t.line } },
        splitArea: { areaStyle: { color: [t.sunk, 'transparent'] } }, axisLine: { lineStyle: { color: t.line } } },
      series: [{ type: 'radar', data: [
        { name: 'Mediana', mediana: true, value: mediana, symbol: 'none', lineStyle: { color: t.muted, type: [4, 4], width: 1 } },
        { name: p.t, value: radarValores(EIXOS.map(([k]) => p.radar[k])), symbol: naoLidos.length ? 'none' : 'circle', symbolSize: 5,
          itemStyle: { color: cor }, lineStyle: { color: cor, width: 2 }, areaStyle: { color: cor, opacity: .22 } },
      ] }],
    };
  });

  const corEstado = (e) => ({ ganha: 'var(--win)', ruido: 'var(--noise)', empata: 'var(--noise)', perde: 'var(--lose)' }[e] || 'var(--norival)');
  const ROT_ESTADO = { ganha: 'vence o melhor rival', ruido: 'dentro do ruído', empata: 'empata', perde: 'perde do melhor rival', sem_rival: 'sem rival externo', sem_nosso: 'sem linha própria' };
  const HW = { nao_reportado: 'Não reportado', '1_gpu': '1 GPU', '1_no': '1 nó', cluster: 'Cluster' };
  const PAPEL = { base: 'Base', baseline: 'Comparado', objeto_medido: 'Medido', juiz_ferramenta: 'Juiz ou ferramenta', professor: 'Professor', dados_treino: 'Dados de treino', avaliacao: 'Avaliação', criada_aqui: 'Criado aqui' };
  const LINHA = { nosso: 'este paper', externo: 'rival', base: 'ponto de partida', variante_propria: 'variante própria' };
  const ALEG = { superlativa: 'Afirmação superlativa', negativa: 'Limite admitido', tese: 'Tese sem experimento' };
  // "7 Limitations" -> "§7 Limitations"; "Resumo" fica como esta
  const secao = (s) => { if (!s || s === 'None') return ''; const m = String(s).match(/^(\d+(?:\.\d+)*)\s*(.*)$/); return m ? `§${m[1]}${m[2] ? ' ' + m[2][0].toUpperCase() + m[2].slice(1).toLowerCase() : ''}` : s; };
  const cmpIdx = $derived(p ? estado.comparar.indexOf(p.id) : -1);
  const vence = $derived(p ? p.res.filter((r) => r.e === 'ganha').length : 0);
  const sinaisSim = $derived(p ? SIG.filter(([k]) => p.sig[k] === true).length : 0);
  function tecla(e) {
    if (!p) return;
    if (e.key === 'Escape') fechar();
    if (e.target.closest?.('input,select,textarea')) return;
    // Alt+setas tambem e o "voltar" do navegador: o painel fica com o atalho
    if (e.altKey && (e.key === 'ArrowRight' || e.key === 'ArrowLeft')) {
      e.preventDefault();
      if (pos >= 0) vai(e.key === 'ArrowRight' ? 1 : -1);
    }
  }
  function irComparar() { if (!largo) fechar(); document.getElementById('comparar')?.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' }); }
  const ABAS = [[1, 'Resumo'], [2, 'Trechos'], [3, 'Ficha']];
</script>

<svelte:window onkeydown={tecla} />

{#if p}
  {#if !largo}<button class="veu" aria-label="Fechar o paper" onclick={fechar} transition:fade={{ duration: mov(200) }}></button>{/if}
  <div class="painel" bind:this={painel} aria-labelledby="paper-titulo" role="dialog" aria-modal={!largo}
    transition:fly={largo ? { x: 40, duration: mov(260), easing: cubicOut, opacity: 0 } : { y: 600, duration: mov(320), easing: cubicOut, opacity: 1 }}>
    {#if !largo}<div class="alca" aria-hidden="true"></div>{/if}
    <div class="barra">
      {#if pos < 0}<span class="fora">Fora do recorte atual</span>{:else}
      <div class="nav">
        <button class="icon-btn" onclick={() => vai(-1)} disabled={pos <= 0} aria-label="Paper anterior" title="Anterior (Alt ←)"><Icone nome="esq" /></button>
        <span class="pos"><b class="num">{pos + 1}</b> de {lista.length}</span>
        <button class="icon-btn" onclick={() => vai(1)} disabled={pos < 0 || pos >= lista.length - 1} aria-label="Próximo paper" title="Próximo (Alt →)"><Icone nome="dir" /></button>
      </div>{/if}
      <button class="icon-btn" aria-label="Fechar o paper" title="Fechar (Esc)" onclick={fechar}><Icone nome="x" /></button>
    </div>

    <div class="corpo">
      {#key p.id}
      <div in:fade={{ duration: mov(180) }}>
        <div class="tipo"><i class="dot" class:nada={p.sol === 'sem_leitura'} class:fragil={p.sol === 'fragil'} style:background={corSolidez(t, p.sol)}></i>
          Solidez {SOL_ROT[p.sol].toLowerCase()}<span class="sep">·</span>{ENTREGA[p.ent] || p.ent}{#if p.cam}<span class="sep">·</span>{CAMADA[p.cam] || p.cam}{/if}</div>
        <h2 id="paper-titulo" tabindex="-1">{p.t}</h2>
        <div class="meta"><span class="num">{p.u} votos</span><span class="sep">·</span>{intervalo(p.d, p.d)}{#if p.org}<span class="sep">·</span>{p.org}{/if}<span class="sep">·</span><a class="mono" href={p.url} target="_blank" rel="noopener" title="Abrir no arXiv">arXiv {p.id}</a><span class="sep">·</span><a href="https://huggingface.co/papers/{p.id}" target="_blank" rel="noopener">Hugging Face</a></div>

        <div class="seg abas" role="tablist" aria-label="Profundidade">
          {#each ABAS as [n, r]}
            <button role="tab" aria-selected={estado.prof === n} onclick={() => (estado.prof = n)}>{r}</button>
          {/each}
        </div>

        {#if estado.prof === 1}
          <dl class="fatos">
            <div><dt>Melhor resultado</dt><dd>{#if p.best}<b class="num">{sgn(p.best.r)}%</b> contra {p.best.x}{:else}<span class="nd">sem rival externo</span>{/if}</dd></div>
            <div><dt>Abertura</dt><dd>{#if p.radar.abertura == null}<span class="nd">Não lida</span>{:else}{p.rel ? 'Algo liberado' : p.prom ? 'Só prometido' : 'Nada liberado'}{/if}</dd></div>
          </dl>

          <div class="radar">
            {#if opRadar}<Grafico opcao={opRadar} altura={250} rotulo="Radar do paper contra a mediana do recorte" />{/if}
            <div class="leg-r"><span><i class="sw" style:background={cor}></i>Este paper</span><span><i class="tr"></i>Mediana</span></div>
          </div>
          <div class="cmp">
            <button class="btn sec" aria-pressed={cmpIdx >= 0} onclick={() => alternaComparar(p.id)}>
              <Icone nome={cmpIdx >= 0 ? 'check' : 'mais'} />{cmpIdx >= 0 ? 'Na comparação' : 'Comparar'}
            </button>
            {#if estado.comparar.length}<button class="btn ghost" onclick={irComparar}>Ver comparação ({estado.comparar.length})<Icone nome="dir" /></button>{/if}
          </div>

          {#if p.res.length}
            <div class="bloco">
              <div class="rot"><h4>Resultados</h4><span class="num">{vence} de {p.res.length} {vence === 1 ? 'vence' : 'vencem'} o rival</span></div>
              {#if p.res.length > 1}<div class="cels" role="group" aria-label="Resultados do paper">
                {#each p.res as r, i}
                  <button class="cel" class:on={celula === i} style:background={corEstado(r.e)} aria-pressed={celula === i}
                    aria-label="{r.b}: {ROT_ESTADO[r.e]}" title="{r.b}: {ROT_ESTADO[r.e]}" onclick={() => (celula = i)}></button>
                {/each}
              </div>{/if}
              {#if p.res[celula]}
                {@const r = p.res[celula]}
                <div class="info">
                  <div class="i-t"><b>{r.b}</b><span>{r.m}</span></div>
                  {#if r.nos && r.ext}
                    <div class="i-v">
                      <span><small>Este paper</small><b class="num">{fmt(r.nos[1], 2)}</b></span>
                      <span><small>{r.ext[0]}</small><b class="num">{fmt(r.ext[1], 2)}</b></span>
                      <span class="d" style:color={corEstado(r.e)}><small>Diferença</small><b class="num">{sgn(r.rext)}%</b></span>
                    </div>
                  {:else}<div class="nd">{ROT_ESTADO[r.e]}</div>{/if}
                </div>
              {/if}
            </div>
          {/if}

          <div class="bloco">
            <div class="rot"><h4>Sinais de prova</h4><span class="num">{sinaisSim} de {p.nl} lidos</span></div>
            <ul class="sinais">
              {#each SIG as [k, rot]}
                {@const v = p.sig[k]}
                <li class:sim={v === true} class:nao={v === false} class:nl={v == null}>
                  <span class="ic" aria-hidden="true">{#if v === true}<Icone nome="check" tam={12} />{:else if v === false}<Icone nome="x" tam={10} />{:else}–{/if}</span>
                  {rot}<span class="vh">: {v == null ? 'não lido' : v ? 'sim' : 'não'}</span>
                </li>
              {/each}
            </ul>
          </div>

          <div class="selos">
            <div><span>Esforço</span><b>{ESFORCO[p.esf]}</b><i class="degraus" aria-hidden="true">{#each [1, 2, 3, 4, 5] as n}<i class:on={p.esf >= n}></i>{/each}</i></div>
            <div><span>Hardware</span><b>{HW[p.hw] || p.hw}</b></div>
            <div><span>Abertura</span>
              <div class="ab">{#each Object.entries(p.ab) as [k, v]}<span class="a {v}" title="{ART[k]}: {ART_EST[v]}"><i></i>{ART[k]}</span>{/each}</div></div>
          </div>
          <button class="btn ghost seguir" onclick={() => (estado.prof = 2)}>Ler os trechos<Icone nome="dir" /></button>

        {:else if estado.prof === 2}
          {#if p.entTr}<blockquote><span>O que entrega</span><q lang="en">{p.entTr}</q></blockquote>{/if}
          {#if p.man}
            <blockquote class="man" class:no={p.man.conf === false}><span>Manchete <em class:ok={p.man.conf} class:no={p.man.conf === false}>{p.man.conf ? 'confere com a tabela' : p.man.conf === false ? 'não confere com a tabela' : 'sem tabela para conferir'}</em></span><q lang="en">{p.man.tr}</q></blockquote>
          {/if}
          {#each p.aleg.filter((a) => a[0] !== 'manchete') as a}
            <blockquote class={a[0]}><span>{ALEG[a[0]] || a[0]}{#if secao(a[2])}<small class="mono">{secao(a[2])}</small>{/if}</span><q lang="en">{a[1]}</q></blockquote>
          {/each}
          {#each p.ress.filter((r) => r[1] !== p.entTr) as r}<blockquote class="ress"><span>Ressalva{#if secao(r[2])}<small class="mono">{secao(r[2])}</small>{/if}</span><q lang="en">{r[1]}</q></blockquote>{/each}
          {#if !p.entTr && !p.man && !p.aleg.length && !p.ress.length}<div class="vazio">A leitura não trouxe trechos deste paper.</div>{/if}
          <p class="nota">{p.L.c === 'completa' ? 'Texto lido por inteiro.' : `Leitura parcial${p.L.fim ? `: parou em ${p.L.fim}` : ''}.`}</p>
          <button class="btn ghost seguir" onclick={() => (estado.prof = 3)}>Ver ficha<Icone nome="dir" /></button>

        {:else}
          {#each p.res.slice(0, 10) as r}
            <table>
              <caption><b>{r.b}</b><span>{r.tab || ''}{#if r.tab && r.m} · {/if}{r.m}</span></caption>
              <tbody>
                {#each r.lin as l}
                  <tr class:nos={l[1] === 'nosso'}><th scope="row">{l[0]}</th><td><span class="papel {l[1]}">{LINHA[l[1]] || l[1]}</span></td><td class="num">{fmt(l[2], 2)}{#if l[3] != null}<small> ±{fmt(l[3], 2)}</small>{/if}</td></tr>
                {/each}
              </tbody>
            </table>
          {/each}
          {#if p.ents.length}
            <div class="rot"><h4>Entidades</h4></div>
            <dl class="ents">
              {#each Object.entries(Object.groupBy ? Object.groupBy(p.ents, (e) => e[2]) : {}) as [papel, es]}
                <div><dt>{PAPEL[papel] || papel}</dt><dd>{es.map((e) => e[0] + (e[3] ? ` (${e[3]})` : '')).join(', ')}</dd></div>
              {/each}
            </dl>
          {/if}
          {#if p.naoex.length}<p class="nota">Ficou fora da leitura: {p.naoex.map((n) => n.local).join(', ')}.</p>{/if}
          <div class="links">
            <a class="btn sec" href={p.url} target="_blank" rel="noopener">arXiv<Icone nome="fora" tam={14} /></a>
            <a class="btn sec" href="https://huggingface.co/papers/{p.id}" target="_blank" rel="noopener">Hugging Face<Icone nome="fora" tam={14} /></a>
            {#each p.art.filter((a) => urlSegura(a[2])) as a}<a class="btn sec" href={urlSegura(a[2])} target="_blank" rel="noopener">{ART[a[0]] || a[0]}<Icone nome="fora" tam={14} /></a>{/each}
          </div>
        {/if}
      </div>
      {/key}
    </div>
  </div>
{/if}

<style>
  .veu { position: fixed; inset: 0; z-index: 19; background: var(--scrim); }
  .painel { position: fixed; z-index: 20; left: 0; right: 0; bottom: 0; max-height: 90dvh; display: flex; flex-direction: column;
    background: var(--surface); border-radius: var(--r-xl) var(--r-xl) 0 0; box-shadow: var(--shadow-3); padding-bottom: env(safe-area-inset-bottom, 0px); }
  @media (min-width: 1024px) {
    .painel { left: auto; top: calc(env(safe-area-inset-top, 0px) + 108px); right: max(16px, env(safe-area-inset-right, 0px)); bottom: 16px;
      width: min(460px, 40vw); max-height: none; border-radius: var(--r-xl); }
  }
  /* em tela larga a pagina abre espaco para a gaveta, sem animar a largura */
  @media (min-width: 1280px) { :global(body.painel-aberto main.wrap) { padding-right: calc(min(460px, 40vw) + 32px); max-width: none; margin-left: 0; } }
  .alca { width: 36px; height: 4px; border-radius: 2px; background: var(--line-strong); margin: 8px auto 0; }
  .barra { display: flex; align-items: center; justify-content: space-between; padding: var(--s-2) var(--s-3); border-bottom: 1px solid var(--line); }
  .fora { font-size: var(--t-12); color: var(--muted); padding-left: var(--s-2); }
  .nav { display: flex; align-items: center; gap: 2px; }
  .pos { font-size: var(--t-12); color: var(--muted); min-width: 56px; text-align: center; }
  .pos b { color: var(--ink); font-weight: 500; }
  .corpo { overflow-y: auto; padding: var(--s-4) var(--s-5) var(--s-6); overscroll-behavior: contain; }

  .tipo { font-size: var(--t-12); color: var(--ink2); display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
  .sep { color: var(--faint); margin: 0 2px; }
  h2 { font-family: var(--display); font-weight: 500; font-size: var(--t-25); line-height: 1.15; letter-spacing: -.015em; margin: var(--s-2) 0 var(--s-2); text-wrap: balance; }
  h2:focus { outline: none; }
  .meta { font-size: var(--t-12); color: var(--muted); display: flex; flex-wrap: wrap; align-items: center; gap: 2px 4px; }
  .meta a { color: var(--muted); text-decoration: underline; text-decoration-color: var(--line-strong); text-underline-offset: 3px; }
  .meta a:hover { color: var(--ink); }
  .abas { display: flex; margin: var(--s-4) 0 var(--s-4); }
  .abas button { flex: 1; }

  .fatos { display: grid; grid-template-columns: 1fr 1fr; gap: 1px; margin: 0; background: var(--line); border-radius: var(--r); overflow: hidden; box-shadow: 0 0 0 1px var(--line); }
  .fatos div { background: var(--surface); padding: 10px 12px; }
  dt { font-size: var(--t-11); font-weight: 500; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
  dd { margin: 2px 0 0; font-size: var(--t-13); }
  dd b { font-weight: 600; }
  .nd { color: var(--muted); font-size: var(--t-13); }

  .radar { margin-top: var(--s-2); }
  .leg-r { display: flex; justify-content: center; gap: var(--s-4); font-size: var(--t-12); color: var(--ink2); margin-top: 4px; }
  .leg-r span { display: inline-flex; align-items: center; gap: 6px; }
  .sw { width: 10px; height: 10px; border-radius: 3px; }
  .tr { width: 16px; border-top: 1.5px dashed var(--muted); }
  .cmp { display: flex; gap: var(--s-2); justify-content: center; margin-top: var(--s-3); flex-wrap: wrap; }

  .bloco { margin-top: var(--s-6); }
  .rot { display: flex; justify-content: space-between; align-items: baseline; gap: var(--s-3); margin: var(--s-6) 0 var(--s-3); }
  .bloco .rot { margin-top: 0; }
  .rot h4 { margin: 0; font-size: var(--t-13); font-weight: 600; }
  .rot span { font-size: var(--t-12); color: var(--muted); }
  .cels { display: flex; flex-wrap: wrap; gap: 6px; }
  .cel { width: 28px; height: 28px; border-radius: 7px; transition: transform var(--dur-1) var(--ease), box-shadow var(--dur-1); }
  .cel:hover { transform: translateY(-1px); }
  .cel.on { box-shadow: 0 0 0 2px var(--surface), 0 0 0 4px var(--ink); }
  .cels + .info { margin-top: var(--s-3); }
  .info { padding: var(--s-3); border-radius: var(--r); background: var(--sunk); }
  .i-t { display: flex; flex-wrap: wrap; gap: 2px 8px; align-items: baseline; font-size: var(--t-13); }
  .i-t span { color: var(--muted); font-size: var(--t-12); }
  .i-v { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--s-2); margin-top: var(--s-2); }
  .i-v span { display: grid; gap: 1px; min-width: 0; }
  .i-v small { font-size: var(--t-11); color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .i-v b { font-size: var(--t-16); font-weight: 600; color: var(--ink); }
  .i-v .d b { color: inherit; }

  .sinais { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: 1fr 1fr; gap: 6px 12px; font-size: var(--t-13); }
  .sinais li { display: flex; align-items: center; gap: 8px; color: var(--ink2); }
  .ic { width: 18px; height: 18px; border-radius: 50%; display: grid; place-items: center; flex: none; font-size: 11px; }
  .sim .ic { background: var(--s-firme); color: var(--on-accent); }
  .sim { color: var(--ink) !important; }
  .nao .ic { box-shadow: inset 0 0 0 1.2px var(--line-strong); color: var(--muted); }
  .nl .ic { color: var(--faint); box-shadow: inset 0 0 0 1px var(--line); }
  .nl { color: var(--muted) !important; }
  @media (max-width: 400px) { .sinais { grid-template-columns: 1fr; } }

  .selos { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1px; margin-top: var(--s-6); background: var(--line); border-radius: var(--r); overflow: hidden; box-shadow: 0 0 0 1px var(--line); }
  .selos > div { background: var(--surface); padding: 10px 12px; display: grid; gap: 4px; align-content: start; min-width: 0; }
  .selos span { font-size: var(--t-11); font-weight: 500; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
  .selos b { font-size: var(--t-13); font-weight: 600; }
  .degraus { display: flex; gap: 2px; }
  .degraus i { width: 12px; height: 4px; border-radius: 2px; background: var(--sunk); }
  .degraus i.on { background: var(--ink2); }
  .ab { display: grid; gap: 3px; }
  .a { display: flex; align-items: center; gap: 6px; font-size: var(--t-12); color: var(--muted); }
  .a i { width: 8px; height: 8px; border-radius: 2px; background: var(--sunk); box-shadow: inset 0 0 0 1px var(--line-strong); }
  .a.liberado { color: var(--ink); } .a.liberado i { background: var(--win); box-shadow: none; }
  .a.prometido i { box-shadow: inset 0 0 0 1.5px var(--win); background: none; }
  .a.nao_lido i { background: repeating-linear-gradient(135deg, var(--line-strong) 0 2px, transparent 2px 4px); box-shadow: none; }
  .seguir { margin-top: var(--s-5); width: 100%; justify-content: space-between; box-shadow: inset 0 0 0 1px var(--line); }

  blockquote { margin: 0 0 var(--s-3); padding: var(--s-3) var(--s-4); border-left: 2px solid var(--line-strong); }
  blockquote span { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: var(--t-11); font-weight: 500; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); margin-bottom: 6px; }
  blockquote span small { letter-spacing: 0; text-transform: none; font-weight: 400; color: var(--faint); }
  blockquote q { font-family: var(--display); font-size: 17px; line-height: 1.45; color: var(--ink); }
  q::before { content: '“'; } q::after { content: '”'; }
  blockquote.negativa, blockquote.ress, blockquote.man.no { border-left-color: var(--warn); }
  blockquote.man { border-left-color: var(--accent); }
  em { font-style: normal; text-transform: none; letter-spacing: 0; padding: 1px 8px; border-radius: 999px; font-size: var(--t-11); background: var(--sunk); color: var(--ink2); }
  em.ok { background: var(--accent-soft); color: var(--accent-ink); } em.no { background: var(--warn-soft); color: var(--warn); }
  .nota { font-size: var(--t-12); color: var(--muted); margin: var(--s-4) 0 0; }

  table { width: 100%; border-collapse: collapse; margin-bottom: var(--s-4); font-size: var(--t-13); }
  caption { text-align: left; padding: 0 0 6px; display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
  caption span { color: var(--muted); font-size: var(--t-12); text-align: right; }
  th, td { padding: 7px 0; border-top: 1px solid var(--line); text-align: left; font-weight: 400; }
  th { padding-right: 8px; }
  td:last-child { text-align: right; white-space: nowrap; padding-left: 8px; }
  td small { color: var(--muted); }
  tr.nos th, tr.nos td:last-child { font-weight: 600; }
  .papel { font-size: var(--t-11); padding: 2px 8px; border-radius: 999px; background: var(--sunk); color: var(--ink2); white-space: nowrap; }
  .papel.nosso { background: var(--ink); color: var(--surface); }
  .ents { display: grid; gap: var(--s-3); margin: 0; }
  .ents dd { color: var(--ink); line-height: 1.45; }
  .links { display: flex; flex-wrap: wrap; gap: var(--s-2); margin-top: var(--s-6); }
  .links a { text-decoration: none; }

  @media (max-width: 560px) { .corpo { padding-inline: var(--s-4); } h2 { font-size: 21px; } }
</style>
