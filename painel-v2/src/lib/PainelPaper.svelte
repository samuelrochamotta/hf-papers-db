<script>
  // Painel do paper: tres profundidades. 1 cartao (visual, quase sem texto),
  // 2 trechos literais, 3 ficha completa. Folha de baixo no celular, painel
  // lateral no desktop.
  import Grafico from './Grafico.svelte';
  import { fly, fade } from 'svelte/transition';
  import { cubicOut } from 'svelte/easing';
  import {
    ENTREGA, CAMADA, ESFORCO, EIXOS, EIXO_DICA, SIG, ART, ART_EST, SOL_ROT, linhaFixa, sgn, fmt, dataCurta, median, urlSegura, radarValores } from './dados.js';
  import { base, corSolidez } from './tema.js';
  import { estado, fechar, alternaComparar } from './estado.svelte.js';

  let { papers, todos } = $props();
  const p = $derived(estado.sel ? todos.find((x) => x.id === estado.sel) : null);
  const t = $derived(estado.tema);
  let celula = $state(0);
  let sinal = $state(null);
  let largo = $state(false);
  $effect(() => { const mq = matchMedia('(min-width: 1024px)'); largo = mq.matches; const f = () => (largo = mq.matches); mq.addEventListener('change', f); return () => mq.removeEventListener('change', f); });
  $effect(() => { estado.sel; celula = 0; sinal = null; });
  $effect(() => { document.body.classList.toggle('painel-aberto', !!p); });

  const mediana = $derived(radarValores(EIXOS.map(([k]) => median(papers.map((x) => x.radar[k])))));
  const cor = $derived(p ? (p.sol === 'sem_leitura' ? t.sNada : corSolidez(t, p.sol)) : '');
  const opRadar = $derived.by(() => {
    if (!p || !t.ink) return null;
    return {
      ...base(t),
      tooltip: { ...base(t).tooltip, trigger: 'item', formatter: (q) => q.data.mediana ? 'Mediana do período'
        : EIXOS.map(([k, r]) => `${r}: <b>${p.radar[k] == null ? 'não lido' : p.radar[k]}</b>`).join('<br>') },
      radar: { indicator: EIXOS.map(([k, r]) => (p.radar[k] == null ? { name: `${r}\nnão lido`, max: 100, color: t.muted } : { name: r, max: 100 })), radius: '66%', center: ['50%', '54%'], splitNumber: 4,
        axisName: { color: t.ink2, fontSize: 11 }, splitLine: { lineStyle: { color: t.line } },
        splitArea: { areaStyle: { color: [t.sunk, 'transparent'] } }, axisLine: { lineStyle: { color: t.line } } },
      series: [{ type: 'radar', data: [
        { name: 'Mediana', mediana: true, value: mediana, symbol: 'none', lineStyle: { color: t.muted, type: [4, 4], width: 1 }, silent: true },
        { name: p.t, value: radarValores(EIXOS.map(([k]) => p.radar[k])), symbol: naoLidos.length ? 'none' : 'circle', symbolSize: 5,
          itemStyle: { color: t.accent }, lineStyle: { color: t.accent, width: 2 }, areaStyle: { color: t.accent, opacity: .2 } },
      ] }],
    };
  });
  const corEstado = (e) => ({ ganha: 'var(--win)', ruido: 'var(--noise)', empata: 'var(--noise)', perde: 'var(--lose)' }[e] || 'var(--sunk)');
  const ROT_ESTADO = { ganha: 'vence o melhor rival', ruido: 'dentro do ruído', empata: 'empata', perde: 'perde do melhor rival', sem_rival: 'sem rival externo', sem_nosso: 'sem linha própria' };
  const HW = { nao_reportado: 'não reportado', '1_gpu': '1 GPU', '1_no': '1 nó', cluster: 'cluster' };
  const PAPEL = { base: 'Base', baseline: 'Comparado', objeto_medido: 'Medido', juiz_ferramenta: 'Juiz ou ferramenta', professor: 'Professor', dados_treino: 'Dados de treino', avaliacao: 'Avaliação', criada_aqui: 'Criado aqui' };
  const naoLidos = $derived(p ? EIXOS.filter(([k]) => p.radar[k] == null).map(([, r]) => r) : []);
  const cmp = $derived(p ? estado.comparar.includes(p.id) : false);
  function tecla(e) { if (e.key === 'Escape' && p) fechar(); }
</script>

<svelte:window onkeydown={tecla} />

{#if p}
  {#if !largo}<button class="veu" aria-label="Fechar" onclick={fechar} transition:fade={{ duration: 200 }}></button>{/if}
  <aside class="painel" aria-label="Paper aberto" transition:fly={largo ? { x: 460, duration: 380, easing: cubicOut, opacity: 1 } : { y: 700, duration: 380, easing: cubicOut, opacity: 1 }}>
    {#if !largo}<div class="alca"></div>{/if}
    <div class="cab">
      <div class="seg" role="group" aria-label="Profundidade">
        {#each [[1, 'Cartão'], [2, 'Trechos'], [3, 'Ficha']] as [n, r]}
          <button aria-pressed={estado.prof === n} onclick={() => (estado.prof = n)}>{r}</button>
        {/each}
      </div>
      <button class="fechar" aria-label="Fechar" onclick={fechar}>×</button>
    </div>
    <div class="corpo">
      {#key p.id}
      <div in:fade={{ duration: 220 }}>
        <div class="tipo"><i class="dot" class:nada={p.sol === 'sem_leitura'} style:background={cor}></i>{ENTREGA[p.ent] || p.ent}{#if p.cam} · {CAMADA[p.cam] || p.cam}{/if}</div>
        <h3>{p.t}</h3>
        <div class="meta mono">{p.id} · {p.u} votos · {dataCurta(p.d)}{#if p.org} · {p.org}{/if}</div>

        {#if estado.prof === 1}
          <div class="fixa">{linhaFixa(p)}</div>
          {#if opRadar}<Grafico opcao={opRadar} altura={230} rotulo="Radar do paper contra a mediana" />{/if}
          {#if naoLidos.length}<p class="nl">Não lido: {naoLidos.join(', ')}</p>{/if}
          <button class="cmpbtn" class:on={cmp} onclick={() => alternaComparar(p.id)}>{cmp ? '✓ No radar de comparação' : '+ Comparar no radar'}</button>

          {#if p.res.length}
            <div class="rot">Resultados <span class="mono">{p.res.filter((r) => r.e === 'ganha').length}/{p.res.length} à frente</span></div>
            <div class="cels">
              {#each p.res as r, i}
                <button class="cel" class:on={celula === i} style:background={corEstado(r.e)} aria-label="{r.b}: {ROT_ESTADO[r.e]}" onclick={() => (celula = i)}></button>
              {/each}
            </div>
            {#if p.res[celula]}
              {@const r = p.res[celula]}
              <div class="info">
                <b>{r.b}</b> · {r.m}<br>
                {#if r.nos && r.ext}<span class="mono">{fmt(r.nos[1], 2)}</span> contra <b>{r.ext[0]}</b> <span class="mono">{fmt(r.ext[1], 2)}</span> · <b class="mono">{sgn(r.rext)}%</b>{:else}{ROT_ESTADO[r.e]}{/if}
              </div>
            {/if}
          {/if}

          <div class="rot">Solidez <span class="mono">{SOL_ROT[p.sol]} · {p.T} de {p.nl} sinais lidos</span></div>
          <div class="regua">
            {#each SIG as [k, rot], i}
              <button class="seg7" class:sim={p.sig[k] === true} class:nao={p.sig[k] === false} class:nl={p.sig[k] == null} class:on={sinal === i}
                aria-label="{rot}: {p.sig[k] == null ? 'não lido' : p.sig[k] ? 'sim' : 'não'}" onclick={() => (sinal = i)}></button>
            {/each}
          </div>
          {#if sinal != null}<p class="sinal">{SIG[sinal][1]}: <b>{p.sig[SIG[sinal][0]] == null ? 'não lido' : p.sig[SIG[sinal][0]] ? 'sim' : 'não'}</b></p>{/if}

          <div class="selos">
            <div><span>Esforço</span><b>{p.esf}</b><small>{ESFORCO[p.esf]}</small></div>
            <div><span>Hardware</span><b class="mono hw">{HW[p.hw]}</b></div>
            <div><span>Abertura</span>
              <div class="ab">{#each Object.entries(p.ab) as [k, v]}<i class="a {v}" title="{ART[k]}: {ART_EST[v]}"></i>{/each}</div>
              <small>{p.rel ? 'algo liberado' : p.prom ? 'prometido' : 'nada liberado'}</small></div>
          </div>
          <button class="mais" onclick={() => (estado.prof = 2)}>Ver os trechos do paper ↓</button>

        {:else if estado.prof === 2}
          {#if p.entTr}<blockquote><span>Entrega</span>{p.entTr}</blockquote>{/if}
          {#if p.man}
            <blockquote class="man"><span>Manchete <em class:ok={p.man.conf} class:no={p.man.conf === false}>{p.man.conf ? 'confere com a tabela' : p.man.conf === false ? 'não confere' : 'sem tabela'}</em></span>{p.man.tr}</blockquote>
          {/if}
          {#each p.aleg.filter((a) => a[0] !== 'manchete') as a}
            <blockquote class={a[0]}><span>{({ superlativa: 'Superlativa', negativa: 'O paper admite', tese: 'Tese sem experimento' })[a[0]] || a[0]}{#if a[2]} · {a[2]}{/if}</span>{a[1]}</blockquote>
          {/each}
          {#each p.ress as r}<blockquote class="ress"><span>Ressalva{#if r[2]} · {r[2]}{/if}</span>{r[1]}</blockquote>{/each}
          <p class="nl">{p.L.c === 'completa' ? 'Leitura do texto completo.' : `Leitura parcial${p.L.fim ? `, até ${p.L.fim}` : ''}.`}</p>
          <button class="mais" onclick={() => (estado.prof = 3)}>Ver a ficha completa ↓</button>

        {:else}
          {#each p.res.slice(0, 10) as r}
            <table>
              <caption><b>{r.b}</b><span>{r.tab || ''} · {r.m}</span></caption>
              <tbody>
                {#each r.lin as l}
                  <tr class:nos={l[1] === 'nosso'}><td>{l[0]}</td><td><span class="papel {l[1]}">{l[1]}</span></td><td class="mono">{fmt(l[2], 2)}{#if l[3] != null}<small> ±{fmt(l[3], 2)}</small>{/if}</td></tr>
                {/each}
              </tbody>
            </table>
          {/each}
          {#if p.ents.length}
            <div class="rot">Entidades</div>
            <div class="ents">
              {#each Object.entries(Object.groupBy ? Object.groupBy(p.ents, (e) => e[2]) : {}) as [papel, es]}
                <div><span>{PAPEL[papel] || papel}</span>{es.map((e) => e[0] + (e[3] ? ` (${e[3]})` : '')).join(', ')}</div>
              {/each}
            </div>
          {/if}
          {#if p.naoex.length}<p class="nl">Fora da leitura: {p.naoex.map((n) => n.local).join(', ')}</p>{/if}
          <div class="links">
            <a href={p.url} target="_blank" rel="noopener">arXiv ↗</a>
            <a href="https://huggingface.co/papers/{p.id}" target="_blank" rel="noopener">Hugging Face ↗</a>
            {#each p.art.filter((a) => urlSegura(a[2])) as a}<a href={urlSegura(a[2])} target="_blank" rel="noopener">{ART[a[0]] || a[0]} ↗</a>{/each}
          </div>
        {/if}
      </div>
      {/key}
    </div>
  </aside>
{/if}

<style>
  .veu { position: fixed; inset: 0; z-index: 19; background: rgba(8,10,14,.38); }
  .painel { position: fixed; z-index: 20; left: 0; right: 0; bottom: 0; max-height: 88dvh; display: flex; flex-direction: column;
    background: var(--surface); border-radius: 22px 22px 0 0; box-shadow: var(--shadow); padding-bottom: env(safe-area-inset-bottom, 0px); }
  @media (min-width: 1024px) {
    .painel { left: auto; top: calc(env(safe-area-inset-top, 0px) + 70px); right: max(16px, env(safe-area-inset-right, 0px)); bottom: 16px; width: 430px; max-height: none; border-radius: 22px; }
    :global(body.painel-aberto main) { padding-right: 462px; transition: padding .35s cubic-bezier(.2,.8,.2,1); }
  }
  .alca { width: 40px; height: 4px; border-radius: 2px; background: var(--line); margin: 8px auto 0; }
  .cab { display: flex; align-items: center; justify-content: space-between; padding: 10px 16px 6px; }
  .fechar { width: 34px; height: 34px; border-radius: 50%; background: var(--sunk); font-size: 18px; display: grid; place-items: center; }
  .corpo { overflow-y: auto; padding: 4px 16px 18px; overscroll-behavior: contain; }
  .tipo { font-size: 12.5px; color: var(--ink2); display: flex; align-items: center; gap: 6px; }
  h3 { font-family: var(--display); font-weight: 700; font-size: 21px; line-height: 1.18; letter-spacing: -.01em; margin: 6px 0 4px; }
  .meta { font-size: 11.5px; color: var(--muted); }
  .fixa { margin: 12px 0 4px; padding: 10px 12px; border-radius: 12px; background: var(--sunk); font-size: 13.5px; }
  .nl { font-size: 12px; color: var(--muted); margin: 6px 0; }
  .cmpbtn { width: 100%; padding: 9px; border-radius: 12px; box-shadow: inset 0 0 0 1.5px var(--accent); color: var(--accent); font-weight: 600; font-size: 13.5px; margin: 4px 0 6px; transition: background .2s, color .2s; }
  .cmpbtn.on { background: var(--accent); color: var(--surface); }
  .rot { display: flex; justify-content: space-between; font-size: 11px; letter-spacing: .05em; text-transform: uppercase; color: var(--muted); margin: 16px 0 6px; }
  .rot span { text-transform: none; letter-spacing: 0; }
  .cels { display: flex; flex-wrap: wrap; gap: 5px; }
  .cel { width: 26px; height: 26px; border-radius: 7px; transition: transform .2s; }
  .cel.on { box-shadow: 0 0 0 2px var(--surface), 0 0 0 4px var(--ink); transform: scale(1.06); }
  .info { margin-top: 8px; font-size: 13px; color: var(--ink2); }
  .regua { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; }
  .seg7 { height: 14px; border-radius: 4px; background: var(--sunk); }
  .seg7.sim { background: var(--s-firme); }
  .seg7.nl { background: repeating-linear-gradient(135deg, var(--line) 0 3px, transparent 3px 6px); }
  .seg7.on { box-shadow: 0 0 0 2px var(--ink); }
  .sinal { font-size: 13px; margin: 6px 0 0; }
  .selos { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 16px; }
  .selos > div { background: var(--sunk); border-radius: 14px; padding: 10px; display: grid; gap: 2px; align-content: start; }
  .selos span { font-size: 10.5px; letter-spacing: .05em; text-transform: uppercase; color: var(--muted); }
  .selos b { font-family: var(--display); font-size: 22px; line-height: 1.1; }
  .selos b.hw { font-family: var(--mono); font-size: 13px; padding: 5px 0; }
  .selos small { font-size: 11.5px; color: var(--ink2); }
  .ab { display: flex; gap: 3px; padding: 7px 0 4px; }
  .a { width: 16px; height: 8px; border-radius: 3px; background: var(--line); }
  .a.liberado { background: var(--win); } .a.prometido { box-shadow: inset 0 0 0 1.5px var(--win); background: none; }
  .a.nao_lido { background: repeating-linear-gradient(135deg, var(--line) 0 2px, transparent 2px 4px); }
  .mais { width: 100%; margin-top: 16px; padding: 12px; border-radius: 14px; background: var(--ink); color: var(--surface); font-weight: 600; font-size: 14px; text-align: center; }
  blockquote { margin: 12px 0 0; padding: 10px 12px; border-left: 3px solid var(--line); background: var(--sunk); border-radius: 0 12px 12px 0; font-size: 13.5px; line-height: 1.4; }
  blockquote span { display: block; font-size: 10.5px; letter-spacing: .05em; text-transform: uppercase; color: var(--muted); margin-bottom: 4px; }
  blockquote.negativa, blockquote.ress { border-left-color: var(--warn); }
  blockquote.man { border-left-color: var(--accent); }
  em { font-style: normal; text-transform: none; letter-spacing: 0; padding: 1px 7px; border-radius: 999px; margin-left: 4px; font-size: 11px; }
  em.ok { background: var(--accent-soft); color: var(--accent); } em.no { background: var(--shade); color: var(--warn); }
  table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 12.5px; background: var(--sunk); border-radius: 12px; overflow: hidden; }
  caption { text-align: left; padding: 8px 10px; display: flex; justify-content: space-between; gap: 8px; background: var(--sunk); border-radius: 12px 12px 0 0; }
  caption span { color: var(--muted); font-family: var(--mono); font-size: 11px; }
  td { padding: 6px 10px; border-top: 1px solid var(--line); }
  td:last-child { text-align: right; white-space: nowrap; }
  tr.nos td { font-weight: 600; }
  .papel { font-size: 10.5px; padding: 1px 7px; border-radius: 999px; background: var(--surface); color: var(--ink2); }
  .papel.nosso { background: var(--accent); color: var(--surface); }
  .ents { display: grid; gap: 6px; font-size: 13px; }
  .ents span { display: block; font-size: 10.5px; text-transform: uppercase; letter-spacing: .05em; color: var(--muted); }
  .links { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }
  .links a { padding: 7px 12px; border-radius: 999px; background: var(--sunk); font-size: 13px; text-decoration: none; }
</style>
