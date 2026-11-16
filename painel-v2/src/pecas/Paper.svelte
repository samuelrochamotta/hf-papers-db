<script>
  // O paper em tres profundidades: Resumo (o que entrega, ganho, prova e
  // adocao, quase sem texto), Trechos (frases literais, com a secao) e Ficha
  // (tabelas, entidades, links). Gaveta ao lado em tela larga, folha inteira
  // no celular. Esc fecha e devolve o foco; Alt + setas troca de paper.
  import Grafico from '../lib/Grafico.svelte';
  import Icone from '../lib/Icone.svelte';
  import { fly, fade } from 'svelte/transition';
  import { cubicOut } from 'svelte/easing';
  import { tick } from 'svelte';
  import { ordenar, buscar, ENTREGA, CAMADA, ESFORCO, EIXOS, SIG, ART, ART_EST, SOL_FRASE, HW, sgn, fmt, median, urlSegura, radarValores, intervalo, ganhoDe, liberados } from '../lib/dados.js';
  import { base, corSolidez, dica } from '../lib/tema.js';
  import { estado, fechar, alternaComparar, abrir, mov } from '../lib/estado.svelte.js';

  let { papers, todos } = $props();
  const p = $derived(estado.sel ? todos.find((x) => x.id === estado.sel) : null);
  const t = $derived(estado.tema);
  let celula = $state(0);
  let largo = $state(false);
  let painel = $state(null);
  let origem = null;
  $effect(() => { const mq = matchMedia('(min-width: 1024px)'); largo = mq.matches; const f = () => (largo = mq.matches); mq.addEventListener('change', f); return () => mq.removeEventListener('change', f); });
  $effect(() => { estado.sel; celula = 0; });
  $effect(() => { document.body.classList.toggle('paper-aberto', !!p); });
  // no celular a folha e modal: o resto da pagina sai do alcance do Tab
  $effect(() => {
    const modal = !!p && !largo, resto = document.querySelectorAll('#app > :not(.paper):not(.veu)');
    for (const el of resto) el.inert = modal;
    return () => { for (const el of resto) el.inert = false; };
  });
  let aberto = false;
  $effect(() => {
    const ok = !!p;
    if (ok && !aberto) { origem = document.activeElement; tick().then(() => painel?.querySelector('h2')?.focus({ preventScroll: true })); }
    if (!ok && aberto && origem && document.contains(origem)) origem.focus({ preventScroll: true });
    aberto = ok;
  });

  const lista = $derived(ordenar(buscar(papers, estado.busca), estado.ordem));
  const pos = $derived(p ? lista.findIndex((x) => x.id === p.id) : -1);
  const vai = (d) => { const n = lista[pos + d]; if (n) abrir(n.id, estado.prof); };

  const medBruta = $derived(EIXOS.map(([k]) => median(papers.map((x) => x.radar[k]))));
  const cor = $derived(p ? (p.sol === 'sem_leitura' ? t.solNada : corSolidez(t, p.sol)) : '');
  const naoLidos = $derived(p ? EIXOS.filter(([k]) => p.radar[k] == null).map(([, r]) => r) : []);
  const opRadar = $derived.by(() => {
    if (!p || !t.ink) return null;
    return {
      ...base(t),
      tooltip: { ...base(t).tooltip, trigger: 'item', formatter: (q) => q.data.mediana
        ? dica('Mediana do recorte', ...EIXOS.map(([, r], i) => `${r}: <b>${medBruta[i] == null ? '–' : Math.round(medBruta[i])}</b>`))
        : dica('Este paper', ...EIXOS.map(([k, r]) => `${r}: <b>${p.radar[k] == null ? 'não lido' : p.radar[k]}</b>`)) },
      radar: { indicator: EIXOS.map(([k, r]) => (p.radar[k] == null ? { name: `${r}\nnão lido`, max: 100, color: t.muted } : { name: `${r}\n{v|${p.radar[k]}}`, max: 100 })),
        radius: '60%', center: ['50%', '52%'], splitNumber: 4,
        axisName: { color: t.ink2, fontSize: 12, fontFamily: t.fUi, lineHeight: 16, rich: { v: { fontFamily: t.fNum, fontSize: 12, color: t.ink, fontWeight: 600 } } },
        splitLine: { lineStyle: { color: t.line } }, splitArea: { show: false }, axisLine: { lineStyle: { color: t.line } } },
      series: [{ type: 'radar', data: [
        { name: 'Mediana', mediana: true, value: radarValores(medBruta), symbol: 'none', lineStyle: { color: t.muted, type: [4, 4], width: 1 } },
        { name: p.t, value: radarValores(EIXOS.map(([k]) => p.radar[k])), symbol: naoLidos.length ? 'none' : 'circle', symbolSize: 5,
          itemStyle: { color: cor }, lineStyle: { color: cor, width: 2 }, areaStyle: { color: cor, opacity: .2 } },
      ] }],
    };
  });

  const ROT_ESTADO = { ganha: 'vence o melhor rival', ruido: 'dentro do ruído', empata: 'empata', perde: 'perde do melhor rival', sem_rival: 'sem rival externo', sem_nosso: 'sem linha própria' };
  const CL_ESTADO = { ganha: 'ganha', ruido: 'ruido', empata: 'ruido', perde: 'perde' };
  const PAPEL = { base: 'Base', baseline: 'Comparado', objeto_medido: 'Medido', juiz_ferramenta: 'Juiz ou ferramenta', professor: 'Professor', dados_treino: 'Dados de treino', avaliacao: 'Avaliação', criada_aqui: 'Criado aqui' };
  const LINHA = { nosso: 'este paper', externo: 'rival', base: 'ponto de partida', variante_propria: 'variante própria' };
  const ALEG = { superlativa: 'Afirmação superlativa', negativa: 'Limite admitido', tese: 'Tese sem experimento' };
  const secao = (s) => { if (!s || s === 'None') return ''; const m = String(s).match(/^(\d+(?:\.\d+)*)\s*(.*)$/); return m ? `§${m[1]}${m[2] ? ' ' + m[2][0].toUpperCase() + m[2].slice(1).toLowerCase() : ''}` : s; };
  const curtaUrl = (u) => String(u).replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, '');
  const cmpIdx = $derived(p ? estado.comparar.indexOf(p.id) : -1);
  const vence = $derived(p ? p.res.filter((r) => r.e === 'ganha').length : 0);
  const comRival = $derived(p ? p.res.filter((r) => r.rext != null).length : 0);
  const sinaisSim = $derived(p ? SIG.filter(([k]) => p.sig[k] === true).length : 0);
  const porPapel = $derived(p ? p.ents.reduce((m, e) => { (m[e[2]] ||= []).push(e); return m; }, {}) : {});
  const linkDe = (k) => urlSegura(p.art.find((a) => a[0] === k)?.[2]);

  function tecla(e) {
    if (!p) return;
    if (e.key === 'Escape') { fechar(); return; }
    if (e.target.closest?.('input,select,textarea')) return;
    if (e.altKey && (e.key === 'ArrowRight' || e.key === 'ArrowLeft')) { e.preventDefault(); if (pos >= 0) vai(e.key === 'ArrowRight' ? 1 : -1); }
  }
  const ABAS = [[1, 'Resumo'], [2, 'Trechos'], [3, 'Ficha']];
  async function teclaAba(e) {
    const d = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0; if (!d) return;
    e.preventDefault(); estado.prof = ((estado.prof - 1 + d + 3) % 3) + 1; await tick();
    painel?.querySelector('[role="tab"][aria-selected="true"]')?.focus();
  }
</script>

<svelte:window onkeydown={tecla} />

{#if p}
  {#if !largo}<button class="veu" aria-label="Fechar o paper" tabindex="-1" onclick={fechar} transition:fade={{ duration: mov(200) }}></button>{/if}
  <div class="paper" bind:this={painel} aria-labelledby="paper-titulo" role="dialog" aria-modal={!largo} data-regiao="paper"
    transition:fly={largo ? { x: 32, duration: mov(320), easing: cubicOut, opacity: 0 } : { y: 480, duration: mov(320), easing: cubicOut, opacity: 1 }}>
    <div class="cabeca">
      {#if pos < 0}<span class="mut t-12">Fora do recorte atual</span>{:else}
        <div class="nav">
          <button class="ico" onclick={() => vai(-1)} disabled={pos <= 0} aria-label="Paper anterior" title="Anterior (Alt ←)"><Icone nome="esq" /></button>
          <span class="t-12 mut"><b class="num">{pos + 1}</b> de {lista.length}</span>
          <button class="ico" onclick={() => vai(1)} disabled={pos >= lista.length - 1} aria-label="Próximo paper" title="Próximo (Alt →)"><Icone nome="dir" /></button>
        </div>{/if}
      <div class="acoes">
        <button class="btn sec cmpb" aria-pressed={cmpIdx >= 0} onclick={() => alternaComparar(p.id)}><Icone nome={cmpIdx >= 0 ? 'check' : 'mais'} tam={14} />{cmpIdx >= 0 ? 'Na comparação' : 'Comparar'}</button>
        <button class="ico" aria-label="Fechar o paper" title="Fechar (Esc)" onclick={fechar}><Icone nome="x" /></button>
      </div>
    </div>

    <div class="corpo">
      {#key p.id}
      <div in:fade={{ duration: mov(200) }}>
        <p class="tipo"><i class="sol {p.sol}"></i><span class="pts"><b>{SOL_FRASE[p.sol]}</b><span class="mut">{ENTREGA[p.ent] || p.ent}</span>{#if p.cam}<span class="mut">{CAMADA[p.cam] || p.cam}</span>{/if}</span></p>
        <h2 id="paper-titulo" class="titulo" tabindex="-1">{p.t}</h2>
        <p class="meta t-12 mut pts"><span><span class="num">{p.u}</span> votos</span><span>{intervalo(p.d, p.d)}</span>{#if p.org}<span>{p.org}</span>{/if}<span><a class="lk" href={p.url} target="_blank" rel="noopener">arXiv <span class="num">{p.id}</span></a></span><span><a class="lk" href="https://huggingface.co/papers/{p.id}" target="_blank" rel="noopener">Hugging Face</a></span></p>

        <div class="seg abas" role="tablist" aria-label="Profundidade da leitura">
          {#each ABAS as [n, r]}
            <button role="tab" id="aba-{n}" aria-selected={estado.prof === n} aria-controls="painel-aba" tabindex={estado.prof === n ? 0 : -1} onclick={() => (estado.prof = n)} onkeydown={teclaAba}>{r}</button>
          {/each}
        </div>

        <div id="painel-aba" role="tabpanel" aria-labelledby="aba-{estado.prof}">
        {#if estado.prof === 1}
          {#if p.entTr}<blockquote class="entrega"><span class="rot">O que entrega</span><q lang="en">{p.entTr}</q></blockquote>{/if}

          <dl class="fatos">
            <div><dt class="rot">Ganho</dt>
              {#if ganhoDe(p) != null}<dd class="v titulo">{sgn(ganhoDe(p))}%</dd><dd class="d">{comRival > 1 ? `mediana de ${comRival} resultados` : 'em 1 resultado'}{#if p.best && comRival > 1}; melhor, {sgn(p.best.r)}% contra {p.best.x}{:else if p.best} contra {p.best.x}{/if}</dd>
              {:else}<dd class="v titulo nd">–</dd><dd class="d">{p.res.length ? 'sem rival externo' : 'não lido'}</dd>{/if}</div>
            <div><dt class="rot">Prova</dt>
              <dd class="v titulo" class:nd={p.sol === 'sem_leitura'}>{p.sol === 'sem_leitura' ? '–' : SOL_FRASE[p.sol].replace('Prova ', '').replace(/^./, (c) => c.toUpperCase())}</dd>
              <dd class="d">{p.nl ? `${sinaisSim} de ${p.nl} sinais lidos` : 'nenhum sinal lido'}</dd></div>
            <div><dt class="rot">Adoção</dt>
              <dd class="v titulo" class:nd={p.radar.facilidade == null}>{ESFORCO[p.esf]}</dd>
              <dd class="d">{liberados(p) ? `${liberados(p)} ${liberados(p).includes(' ') ? 'liberados' : 'liberado'}` : p.prom ? 'só prometido' : p.radar.abertura == null ? 'abertura não lida' : 'nada liberado'}</dd></div>
          </dl>

          <section class="bloco">
            <header><h3>Sinais de prova</h3><span class="chave t-12 mut" aria-hidden="true"><i class="s sim"><Icone nome="check" tam={10} /></i>cumpre<i class="s nao"><Icone nome="x" tam={10} /></i>não cumpre<i class="s nl">–</i>não lido</span></header>
            <ul class="sinais">
              {#each SIG as [k, rot]}
                {@const v = p.sig[k]}
                <li class:nl={v == null}><i class="s" class:sim={v === true} class:nao={v === false} class:nl={v == null} aria-hidden="true">{#if v === true}<Icone nome="check" tam={10} />{:else if v === false}<Icone nome="x" tam={10} />{:else}–{/if}</i>{rot}<span class="vh">: {v == null ? 'não lido' : v ? 'cumpre' : 'não cumpre'}</span></li>
              {/each}
            </ul>
          </section>

          <section class="bloco">
            <header><h3>Adoção</h3></header>
            <dl class="pares">
              <div><dt>Esforço</dt><dd><i class="degraus" aria-hidden="true">{#each [1, 2, 3, 4, 5] as n}<i class:on={p.esf >= n}></i>{/each}</i>{ESFORCO[p.esf]}</dd></div>
              <div><dt>Hardware</dt><dd class:mut={p.hw === 'nao_reportado'}>{HW[p.hw] || p.hw}</dd></div>
              {#each Object.entries(p.ab) as [k, v]}
                <div><dt>{ART[k]}</dt><dd class:mut={v !== 'liberado'}>{#if linkDe(k)}<a class="lk" href={linkDe(k)} target="_blank" rel="noopener">{curtaUrl(linkDe(k))}</a>{:else}{ART_EST[v]}{/if}</dd></div>
              {/each}
            </dl>
          </section>

          {#if p.res.length}
            <section class="bloco">
              <header><h3>Resultados</h3><span class="t-12 mut">{vence} de {p.res.length} {vence === 1 ? 'vence' : 'vencem'} o rival</span></header>
              {#if p.res.length > 1}<div class="cels" role="group" aria-label="Resultados do paper">
                {#each p.res as r, i}
                  <button class="cel {CL_ESTADO[r.e] || 'semrival'}" aria-pressed={celula === i} aria-label="{r.b}: {ROT_ESTADO[r.e]}" title="{r.b}: {ROT_ESTADO[r.e]}" onclick={() => (celula = i)}></button>
                {/each}
              </div>{/if}
              {#if p.res[celula]}
                {@const r = p.res[celula]}
                <div class="res">
                  <p class="pts"><b>{r.b}</b>{#if r.m && r.m !== r.b}<span class="mut">{r.m}</span>{/if}</p>
                  {#if r.nos && r.ext}
                    <dl class="trio">
                      <div><dt>Este paper</dt><dd class="num">{fmt(r.nos[1], 2)}</dd></div>
                      <div><dt>{r.ext[0]}</dt><dd class="num">{fmt(r.ext[1], 2)}</dd></div>
                      <div><dt>Diferença</dt><dd class="num {CL_ESTADO[r.e] || ''}">{sgn(r.rext)}%</dd></div>
                    </dl>
                  {:else}<p class="mut">{ROT_ESTADO[r.e]}</p>{/if}
                </div>
              {/if}
            </section>
          {/if}

          <section class="bloco">
            <header><h3>Os seis eixos</h3><span class="t-12 mut"><i class="tr"></i>mediana do recorte</span></header>
            {#if opRadar}<Grafico opcao={opRadar} altura={248} rotulo="Radar do paper nos seis eixos, contra a mediana do recorte" />{/if}
          </section>
          <p class="nota t-12 mut">{p.L.c === 'completa' ? 'Texto lido por inteiro.' : `Leitura parcial${p.L.fim ? `: parou em ${p.L.fim}` : ''}.`}</p>

        {:else if estado.prof === 2}
          {#if p.entTr}<blockquote><span class="rot">O que entrega</span><q lang="en">{p.entTr}</q></blockquote>{/if}
          {#if p.man}
            <blockquote class:alerta={p.man.conf === false}><span class="rot pts"><span>Manchete</span><span>{p.man.conf ? 'confere com a tabela' : p.man.conf === false ? 'não confere com a tabela' : 'sem tabela para conferir'}</span></span><q lang="en">{p.man.tr}</q></blockquote>
          {/if}
          {#each p.aleg.filter((a) => a[0] !== 'manchete') as a}
            <blockquote><span class="rot pts"><span>{ALEG[a[0]] || a[0]}</span>{#if secao(a[2])}<span>{secao(a[2])}</span>{/if}</span><q lang="en">{a[1]}</q></blockquote>
          {/each}
          {#each p.ress.filter((r) => r[1] !== p.entTr) as r}<blockquote><span class="rot pts"><span>Ressalva</span>{#if secao(r[2])}<span>{secao(r[2])}</span>{/if}</span><q lang="en">{r[1]}</q></blockquote>{/each}
          {#if !p.entTr && !p.man && !p.aleg.length && !p.ress.length}<div class="vazio">A leitura não trouxe trechos deste paper.</div>{/if}
          <p class="nota t-12 mut">{p.L.c === 'completa' ? 'Texto lido por inteiro.' : `Leitura parcial${p.L.fim ? `: parou em ${p.L.fim}` : ''}.`}</p>

        {:else}
          {#each p.res.slice(0, 12) as r}
            <table>
              <caption class="pts"><b>{r.b}</b>{#if r.tab}<span class="mut">{r.tab}</span>{/if}{#if r.m && r.m !== r.b}<span class="mut">{r.m}</span>{/if}</caption>
              <tbody>
                {#each r.lin as l}
                  <tr class:nos={l[1] === 'nosso'}><th scope="row">{l[0]}</th><td class="mut">{LINHA[l[1]] || l[1]}</td><td class="num">{fmt(l[2], 2)}{#if l[3] != null}<small>&nbsp;±{fmt(l[3], 2)}</small>{/if}</td></tr>
                {/each}
              </tbody>
            </table>
          {/each}
          {#if p.res.length > 12}<p class="nota t-12 mut">Mais {p.res.length - 12} tabelas no texto original.</p>{/if}
          {#if p.ents.length}
            <section class="bloco"><header><h3>Entidades</h3></header>
              <dl class="pares">{#each Object.entries(porPapel) as [papel, es]}<div><dt>{PAPEL[papel] || papel}</dt><dd>{es.map((e) => e[0] + (e[3] ? ` (${e[3]})` : '')).join(', ')}</dd></div>{/each}</dl>
            </section>
          {/if}
          {#if !p.res.length && !p.ents.length}<div class="vazio">A leitura não trouxe tabelas nem entidades deste paper.</div>{/if}
          {#if p.naoex.length}<p class="nota t-12 mut">Ficou fora da leitura: {p.naoex.map((n) => n.local).join(', ')}.</p>{/if}
          <div class="links">
            <a class="btn sec" href={p.url} target="_blank" rel="noopener">arXiv<Icone nome="fora" tam={14} /></a>
            <a class="btn sec" href="https://huggingface.co/papers/{p.id}" target="_blank" rel="noopener">Hugging Face<Icone nome="fora" tam={14} /></a>
            {#each p.art.filter((a) => urlSegura(a[2])) as a}<a class="btn sec" href={urlSegura(a[2])} target="_blank" rel="noopener">{ART[a[0]] || a[0]}<Icone nome="fora" tam={14} /></a>{/each}
          </div>
        {/if}
        </div>
      </div>
      {/key}
    </div>
  </div>
{/if}

<style>
  .veu { position: fixed; inset: 0; z-index: 19; background: var(--veu); border-radius: 0; }
  .paper { position: fixed; z-index: 20; inset: max(24px, env(safe-area-inset-top, 0px)) 0 0 0; display: flex; flex-direction: column; background: var(--surface);
    border-radius: var(--r-3) var(--r-3) 0 0; box-shadow: var(--sombra-3); padding-bottom: env(safe-area-inset-bottom, 0px); }
  @media (min-width: 1024px) {
    .paper { inset: 0 0 0 auto; width: min(var(--gaveta), 44vw); border-radius: 0; border-left: 1px solid var(--line); box-shadow: var(--sombra-2); }
  }
  .cabeca { display: flex; align-items: center; justify-content: space-between; gap: var(--sp-2); padding: var(--sp-2) var(--sp-3); border-bottom: 1px solid var(--line); min-height: var(--barra); }
  .nav, .acoes { display: flex; align-items: center; gap: var(--sp-1); }
  .nav b { color: var(--ink); font-weight: 500; }
  .corpo { overflow-y: auto; overscroll-behavior: contain; padding: var(--sp-5) var(--sp-4) var(--sp-12); }
  @media (min-width: 768px) { .corpo { padding-inline: var(--sp-6); } }

  .tipo { display: flex; align-items: center; gap: var(--sp-2); flex-wrap: wrap; font-size: var(--fs-12); line-height: var(--lh-12); }
  .tipo b { font-weight: 600; }
  h2 { font-size: var(--fs-20); line-height: var(--lh-20); margin: var(--sp-2) 0; text-wrap: balance; }
  @media (min-width: 768px) { h2 { font-size: var(--fs-24); line-height: var(--lh-24); } }
  h2:focus { outline: none; }
  .meta { line-height: var(--lh-14); }
  .abas { display: flex; margin: var(--sp-5) 0; }

  blockquote { padding: var(--sp-3) 0 var(--sp-3) var(--sp-4); border-left: 2px solid var(--line-strong); display: grid; gap: var(--sp-1); margin-bottom: var(--sp-4); }
  blockquote.alerta { border-left-color: var(--alert); }
  blockquote.alerta .rot { color: var(--alert); }
  q { font-family: var(--f-display); font-size: var(--fs-17); line-height: var(--lh-17); quotes: '“' '”'; }
  .entrega { margin-bottom: var(--sp-5); }

  .fatos { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--sp-4); padding-block: var(--sp-4); border-block: 1px solid var(--line); }
  .fatos .v { font-size: var(--fs-24); line-height: var(--lh-24); margin-top: 2px; }
  .fatos .v.nd { color: var(--muted); }
  .fatos .d { font-size: var(--fs-12); line-height: var(--lh-12); color: var(--muted); margin-top: 2px; }

  .bloco { margin-top: var(--sp-6); }
  .bloco header { display: flex; align-items: baseline; justify-content: space-between; gap: var(--sp-3); margin-bottom: var(--sp-2); flex-wrap: wrap; }
  h3 { font-size: var(--fs-14); line-height: var(--lh-14); font-weight: 600; }
  .chave { display: inline-flex; align-items: center; gap: 4px; flex-wrap: wrap; }
  .chave .s { margin-left: var(--sp-2); }
  .s { width: 16px; height: 16px; border-radius: 50%; display: inline-grid; place-items: center; flex: none; font-size: 12px; line-height: 1; font-style: normal; }
  .s.sim { background: var(--ink); color: var(--surface); }
  .s.nao { color: var(--alert); box-shadow: inset 0 0 0 1.5px var(--alert); }
  .s.nl { color: var(--muted); box-shadow: inset 0 0 0 1px var(--line-strong); }
  .sinais { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: var(--sp-2) var(--sp-4); }
  .sinais li { display: flex; align-items: center; gap: var(--sp-2); }
  .sinais li.nl { color: var(--muted); }

  .pares > div { display: grid; grid-template-columns: 96px minmax(0, 1fr); gap: var(--sp-3); padding: var(--sp-2) 0; border-top: 1px solid var(--line); align-items: baseline; }
  .pares > div:first-child { border-top: 0; }
  .pares dt { font-size: var(--fs-12); line-height: var(--lh-14); color: var(--muted); }
  .pares dd { display: flex; align-items: center; gap: var(--sp-2); min-width: 0; flex-wrap: wrap; }
  .degraus { display: inline-flex; gap: 2px; align-items: flex-end; }
  .degraus i { width: 4px; border-radius: 1px; background: var(--line-strong); opacity: .45; }
  .degraus i:nth-child(1) { height: 5px; } .degraus i:nth-child(2) { height: 7px; } .degraus i:nth-child(3) { height: 9px; } .degraus i:nth-child(4) { height: 11px; } .degraus i:nth-child(5) { height: 13px; }
  .degraus i.on { background: var(--ink); opacity: 1; }

  .cels { display: flex; flex-wrap: wrap; gap: 3px; margin-bottom: var(--sp-3); }
  .cel { width: 24px; height: 24px; border-radius: var(--r-1); background: var(--res-semrival); position: relative; transition: transform var(--dur-1); }
  .cel.ganha { background: var(--res-ganha); } .cel.ruido { background: var(--res-ruido); } .cel.perde { background: var(--res-perde); }
  .cel[aria-pressed="true"] { outline: 2px solid var(--focus); outline-offset: 2px; }
  .cel:hover { transform: scale(1.1); }
  .res { background: var(--sunk); border-radius: var(--r-2); padding: var(--sp-3) var(--sp-4); display: grid; gap: var(--sp-2); }
  .trio { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--sp-3); }
  .trio dt { font-size: var(--fs-12); line-height: var(--lh-12); color: var(--muted); }
  .trio dd { font-size: var(--fs-17); line-height: var(--lh-17); font-weight: 500; }
  .trio dd.perde { color: var(--alert); }
  .tr { width: 16px; border-top: 1.5px dashed var(--muted); display: inline-block; vertical-align: middle; margin-right: 6px; }
  .nota { margin-top: var(--sp-5); }

  table { width: 100%; margin-bottom: var(--sp-5); font-size: var(--fs-12); line-height: var(--lh-12); }
  caption { text-align: left; padding-bottom: var(--sp-2); font-size: var(--fs-14); line-height: var(--lh-14); }
  th, td { text-align: left; padding: 6px 0; border-top: 1px solid var(--line); font-weight: 400; vertical-align: baseline; }
  td { padding-left: var(--sp-3); white-space: nowrap; }
  td.num { text-align: right; font-size: var(--fs-12); }
  td small { color: var(--muted); }
  tr.nos th, tr.nos td { font-weight: 600; color: var(--ink); }
  .links { display: flex; flex-wrap: wrap; gap: var(--sp-2); margin-top: var(--sp-5); }
</style>
