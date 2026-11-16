<script>
  // O paper em tres profundidades: Resumo (o que entrega, ganho, prova e
  // adocao, quase sem texto), Trechos (frases literais, com a secao) e Ficha
  // (tabelas, entidades, links). Gaveta ao lado em tela larga, folha inteira
  // no celular. Esc fecha e devolve o foco; Alt + setas troca de paper.
  import Grafico from '../lib/Grafico.svelte';
  import Icone from '../lib/Icone.svelte';
  import Degraus from '../lib/Degraus.svelte';
  import { fly, fade } from 'svelte/transition';
  import { cubicOut } from 'svelte/easing';
  import { tick } from 'svelte';
  import { ordenar, ENTREGA, CAMADA, ESFORCO, EIXOS, SIG, ART, ART_EST, SOL_FRASE, HW, sgn, fmt, median, urlSegura, radarValores, intervalo, ganhoDe, liberados } from '../lib/dados.js';
  import { base, corSolidez, dica } from '../lib/tema.js';
  import { estado, fechar, alternaComparar, abrir, mov } from '../lib/estado.svelte.js';

  let { papers, todos } = $props();
  const p = $derived(estado.sel ? todos.find((x) => x.id === estado.sel) : null);
  const t = $derived(estado.tema);
  let todosRes = $state(false);
  const LIM_RES = 5, LIM_FICHA = 12;
  let largo = $state(false);
  let painel = $state(null);
  let origem = null;
  $effect(() => { const mq = matchMedia('(min-width: 1024px)'); largo = mq.matches; const f = () => (largo = mq.matches); mq.addEventListener('change', f); return () => mq.removeEventListener('change', f); });
  $effect(() => { estado.sel; todosRes = false; });
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

  const lista = $derived(ordenar(papers, estado.ordem));
  const pos = $derived(p ? lista.findIndex((x) => x.id === p.id) : -1);
  const vai = (d) => { const n = lista[pos + d]; if (n) abrir(n.id, estado.prof); };

  const medBruta = $derived(EIXOS.map(([k]) => median(papers.map((x) => x.radar[k]))));
  // onde o paper fica frente a mediana do recorte, em cada eixo (mesma conta do radar)
  const IDX = Object.fromEntries(EIXOS.map(([k], i) => [k, i]));
  const frente = (k) => { const v = p.radar[k], m = medBruta[IDX[k]]; return v == null || m == null ? null : { v, m, rot: v > m ? 'acima da mediana do recorte' : v < m ? 'abaixo da mediana do recorte' : 'na mediana do recorte' }; };
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
  // "cumpre 5 de 7 sinais": cumprir e ler sao coisas diferentes, e o texto diz as duas
  const sinais = $derived.by(() => {
    if (!p) return '';
    if (!p.nl) return 'nenhum sinal lido';
    const fora = SIG.length - p.nl;
    return `cumpre ${sinaisSim} de ${p.nl} ${p.nl === 1 ? 'sinal lido' : fora ? 'sinais lidos' : 'sinais'}${fora ? `; ${fora} não ${fora === 1 ? 'lido' : 'lidos'}` : ''}`;
  });
  // Ate onde a leitura foi, em palavras de gente: so o nome da secao
  const leitura = $derived.by(() => {
    if (!p) return { curta: '', frase: '' };
    if (p.L.c === 'completa') return { curta: '', frase: 'Texto lido por inteiro.' };
    if (p.L.f === 'abstract') return { curta: 'só o resumo foi lido', frase: 'Leitura parcial: só o resumo do paper foi lido.' };
    const ate = String(p.L.fim || '').split(/\s*[(;:]/)[0].trim();
    return { curta: 'leitura parcial', frase: ate ? `Leitura parcial: o texto foi lido até “${ate}”.` : 'Leitura parcial.' };
  });

  function tecla(e) {
    if (!p) return;
    if (e.key === 'Escape') { fechar(); return; }
    if (e.target.closest?.('input,select,textarea')) return;
    if (e.altKey && (e.key === 'ArrowRight' || e.key === 'ArrowLeft')) { e.preventDefault(); if (pos >= 0) vai(e.key === 'ArrowRight' ? 1 : -1); }
  }
  const ABAS = [[1, 'Resumo'], [2, 'Trechos'], [3, 'Ficha']];
  // Quando o titulo sai da tela, a faixa das abas (presa no topo) passa a dizer de que paper e a ficha.
  let presa = $state(false);
  function olhaTitulo(no) {
    const io = new IntersectionObserver(([e]) => (presa = !e.isIntersecting), { root: no.closest('.corpo') });
    io.observe(no);
    return { destroy() { io.disconnect(); presa = false; } };
  }
  // Na ficha, os numeros de uma tabela tem todos as mesmas casas: a virgula fica numa coluna so.
  const nCasas = (n) => { if (n == null || !Number.isFinite(n)) return 0; const s = String(+Math.abs(n).toFixed(2)), i = s.indexOf('.'); return i < 0 ? 0 : s.length - i - 1; };
  const casasDe = (r, j) => Math.max(0, ...r.lin.map((l) => nCasas(l[j])));
  const fixo = (n, c) => n.toLocaleString('pt-BR', { minimumFractionDigits: c, maximumFractionDigits: c });
  async function verTabela(i) {
    estado.prof = 3; await tick();
    painel?.querySelector(`#tab-${i}`)?.scrollIntoView({ block: 'start', behavior: mov(1) ? 'smooth' : 'auto' });
    painel?.querySelector('#aba-3')?.focus({ preventScroll: true });
  }
  const CHAVE_RES = [['ganha', 'vence'], ['ruido', 'dentro do ruído'], ['perde', 'perde'], ['semrival', 'sem rival externo']];
  const estadosRes = $derived(p ? new Set(p.res.map((r) => CL_ESTADO[r.e] || 'semrival')) : new Set());
  async function teclaAba(e) {
    const d = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0; if (!d) return;
    e.preventDefault(); estado.prof = ((estado.prof - 1 + d + 3) % 3) + 1; await tick();
    painel?.querySelector('[role="tab"][aria-selected="true"]')?.focus();
  }
</script>

<svelte:window onkeydown={tecla} />

{#snippet frenteMed(k)}
  {@const f = frente(k)}
  {#if f}<dd class="pos"><span class="trilho" aria-hidden="true"><i style:width="{f.v}%"></i><b style:left="{f.m}%"></b></span>{f.rot}</dd>{/if}
{/snippet}

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
        <p class="tipo"><i class="sol {p.sol}"></i><span class="pts"><b>{SOL_FRASE[p.sol]}</b>{#if leitura.curta}<span>{leitura.curta}</span>{/if}<span class="mut">{ENTREGA[p.ent] || p.ent}</span>{#if p.cam}<span class="mut">{CAMADA[p.cam] || p.cam}</span>{/if}</span></p>
        <h2 id="paper-titulo" class="titulo" tabindex="-1" use:olhaTitulo>{p.t}</h2>
        <p class="meta t-12 mut"><span class="pts"><span><span class="num">{p.u}</span> votos</span><span>{intervalo(p.d, p.d)}</span>{#if p.org}<span>{p.org}</span>{/if}</span><span class="pts"><span><a class="lk" href={p.url} target="_blank" rel="noopener">arXiv <span class="num">{p.id}</span></a></span><span><a class="lk" href="https://huggingface.co/papers/{p.id}" target="_blank" rel="noopener">Hugging Face</a></span></span></p>

        <div class="fixa" class:presa>
          <span class="tcurto um" aria-hidden="true">{p.t}</span>
          <div class="seg abas" role="tablist" aria-label="Profundidade da leitura">
            {#each ABAS as [n, r]}
              <button role="tab" id="aba-{n}" aria-selected={estado.prof === n} aria-controls="painel-aba" tabindex={estado.prof === n ? 0 : -1} onclick={() => (estado.prof = n)} onkeydown={teclaAba}>{r}</button>
            {/each}
          </div>
        </div>

        <div id="painel-aba" role="tabpanel" aria-labelledby="aba-{estado.prof}">
        {#if estado.prof === 1}
          {#if p.entTr}<blockquote class="entrega"><span class="rot">O que entrega</span><q lang="en">{p.entTr}</q></blockquote>{/if}

          <dl class="fatos">
            <div><dt class="rot">Ganho</dt>
              {#if ganhoDe(p) != null}<dd class="v titulo">{sgn(ganhoDe(p))}%</dd><dd class="d">{comRival > 1 ? `mediana de ${comRival} resultados` : 'em 1 resultado'}{#if p.best && comRival > 1}; melhor, {sgn(p.best.r)}% contra {p.best.x}{:else if p.best} contra {p.best.x}{/if}</dd>
              {:else}<dd class="v titulo nd">–</dd><dd class="d">{p.res.length ? 'sem rival externo' : 'não lido'}</dd>{/if}{@render frenteMed('ganho')}</div>
            <div><dt class="rot">Prova</dt>
              <dd class="v titulo" class:nd={p.sol === 'sem_leitura'}>{p.sol === 'sem_leitura' ? '–' : SOL_FRASE[p.sol].replace('Prova ', '').replace(/^./, (c) => c.toUpperCase())}</dd>
              <dd class="d">{sinais}</dd>{@render frenteMed('solidez')}</div>
            <div><dt class="rot">Adoção</dt>
              <dd class="v titulo" class:nd={p.radar.facilidade == null}>{ESFORCO[p.esf]}</dd>
              <dd class="d">{liberados(p) ? `${liberados(p)} ${liberados(p).includes(' ') ? 'liberados' : 'liberado'}` : p.prom ? 'só prometido' : p.radar.abertura == null ? 'abertura não lida' : 'nada liberado'}</dd>{@render frenteMed('facilidade')}</div>
          </dl>

          <section class="bloco">
            <header><h3>Sinais de prova</h3><span class="chave t-12 mut" aria-hidden="true"><i class="s sim"><Icone nome="check" tam={10} /></i>cumpre<i class="s nao"><Icone nome="x" tam={10} /></i>não cumpre<i class="s nl">–</i>não lido</span></header>
            <ul class="sinais">
              {#each SIG as [k, rot]}
                {@const v = p.sig[k]}
                <li class:nl={v == null}><i class="s" class:sim={v === true} class:nao={v === false} class:nl={v == null} aria-hidden="true">{#if v === true}<Icone nome="check" tam={10} />{:else if v === false}<Icone nome="x" tam={10} />{:else}–{/if}</i><span>{rot}<span class="vh">: {v == null ? 'não lido' : v ? 'cumpre' : 'não cumpre'}</span></span>{#if (k === 'man' && p.man) || (k === 'ress' && p.ress.length)}<button class="lk ver" aria-label="Ver o trecho de: {rot}" onclick={() => (estado.prof = 2)}>trecho</button>{/if}</li>
              {/each}
            </ul>
          </section>

          <section class="bloco">
            <header><h3>Adoção</h3></header>
            <dl class="pares">
              <div><dt>Esforço</dt><dd class:mut={p.radar.facilidade == null}>{#if p.radar.facilidade != null}<Degraus esf={p.esf} />{/if}{ESFORCO[p.esf]}</dd></div>
              <div><dt>Hardware</dt><dd class:mut={p.hw === 'nao_reportado'}>{HW[p.hw] || p.hw}</dd></div>
              {#each Object.entries(p.ab) as [k, v]}
                <div><dt>{ART[k]}</dt><dd class:mut={v !== 'liberado'}>{#if linkDe(k)}<a class="lk" href={linkDe(k)} target="_blank" rel="noopener">{curtaUrl(linkDe(k))}</a>{:else}{ART_EST[v]}{/if}</dd></div>
              {/each}
            </dl>
          </section>

          {#if p.res.length}
            <section class="bloco">
              <header><h3>Resultados</h3><span class="t-12 mut pts"><span>{vence} de {p.res.length} {vence === 1 ? 'vence' : 'vencem'} o rival</span><span>ganho relativo</span></span></header>
              <p class="chave res t-12 mut" aria-hidden="true">{#each CHAVE_RES.filter(([k]) => estadosRes.has(k)) as [k, rot]}<span><i class="cel {k}"></i>{rot}</span>{/each}</p>
              <ul class="ress">
                {#each todosRes ? p.res : p.res.slice(0, LIM_RES) as r, ri}
                  <li>
                    <i class="cel {CL_ESTADO[r.e] || 'semrival'}" aria-hidden="true"></i>
                    <span class="b pts"><b>{r.b}</b>{#if r.m && r.m !== r.b}<span class="mut">{r.m}</span>{/if}</span>
                    <span class="dif num {CL_ESTADO[r.e] || ''}" class:mut={r.rext == null}>{r.rext != null ? `${sgn(r.rext)}%` : '–'}</span>
                    <span class="det mut">{#if r.nos && r.ext}<span class="vh">{ROT_ESTADO[r.e]}: </span><span class="num">{fmt(r.nos[1], 2)}</span> contra <span class="num">{fmt(r.ext[1], 2)}</span> de {r.ext[0]}{:else}{ROT_ESTADO[r.e]}{/if}{#if ri < LIM_FICHA && r.lin.length}<button class="lk ver" aria-label="Ver a tabela de {r.b}" onclick={() => verTabela(ri)}>tabela</button>{/if}</span>
                  </li>
                {/each}
              </ul>
              {#if p.res.length > LIM_RES}<button class="btn sec mais" aria-expanded={todosRes} onclick={() => (todosRes = !todosRes)}>{todosRes ? 'Mostrar menos' : `Ver os ${p.res.length} resultados`}</button>{/if}
            </section>
          {/if}

          <section class="bloco">
            <header><h3>Os seis eixos</h3><span class="t-12 mut"><i class="tr"></i>mediana do recorte</span></header>
            {#if opRadar}<Grafico opcao={opRadar} altura={248} rotulo="Radar do paper nos seis eixos, contra a mediana do recorte" />{/if}
          </section>
          <p class="nota t-12 mut">{leitura.frase}</p>

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
          <p class="nota t-12 mut">{leitura.frase}</p>

        {:else}
          {#each p.res.slice(0, LIM_FICHA) as r, ri}
            {@const cv = casasDe(r, 2)}
            {@const cd = casasDe(r, 3)}
            {@const temDp = r.lin.some((l) => l[3] != null)}
            <table id="tab-{ri}">
              <caption class="pts"><b>{r.b}</b>{#if r.tab}<span class="mut">{r.tab}</span>{/if}{#if r.m && r.m !== r.b}<span class="mut">{r.m}</span>{/if}</caption>
              <tbody>
                {#each r.lin as l}
                  <tr class:nos={l[1] === 'nosso'}><th scope="row">{l[0]}</th><td class="mut">{LINHA[l[1]] || l[1]}</td><td class="num v">{l[2] == null ? '–' : fixo(l[2], cv)}</td>{#if temDp}<td class="num dp">{#if l[3] != null}±{fixo(l[3], cd)}{/if}</td>{/if}</tr>
                {/each}
              </tbody>
            </table>
          {/each}
          {#if p.res.length > LIM_FICHA}<p class="nota t-12 mut">{p.res.length - LIM_FICHA === 1 ? 'Há mais 1 resultado' : `Há mais ${p.res.length - LIM_FICHA} resultados`} no <a class="lk" href={p.url} target="_blank" rel="noopener">texto original</a>, fora desta ficha.</p>{/if}
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
  .corpo { --pad: var(--sp-4); overflow-y: auto; overscroll-behavior: contain; padding: 0 var(--pad) var(--sp-12); }
  @media (min-width: 768px) { .corpo { --pad: var(--sp-6); } }
  .corpo > div { max-width: 640px; margin-inline: auto; padding-top: var(--sp-5); }      /* folha larga (tablet): a coluna de leitura nao estica */

  .tipo { display: flex; align-items: flex-start; gap: var(--sp-2); font-size: var(--fs-12); line-height: var(--lh-12); }
  .tipo .sol { flex: none; margin-top: calc((var(--lh-12) - 10px) / 2); }      /* a marca fica na primeira linha, mesmo quando o texto quebra */
  .tipo .pts { min-width: 0; }
  .tipo b { font-weight: 600; }
  h2 { font-size: var(--fs-20); line-height: var(--lh-20); margin: var(--sp-2) 0; text-wrap: balance; }
  @media (min-width: 768px) { h2 { font-size: var(--fs-24); line-height: var(--lh-24); } }
  h2:focus { outline: none; }
  /* fatos e links em dois grupos: se nao cabem lado a lado, os links descem juntos, sem ponto solto no comeco da linha */
  .meta { line-height: var(--lh-14); display: flex; flex-wrap: wrap; gap: var(--sp-1) var(--sp-4); }
  .meta > span { white-space: nowrap; }
  @media (pointer: coarse) { .meta .lk { position: relative; } .meta .lk::after { content: ''; position: absolute; inset: -16px -4px -12px; } }
  /* abas presas no topo do paper; a linha de cima guarda o titulo, que so aparece quando o titulo grande sai da tela */
  .fixa { position: sticky; top: 0; z-index: 3; display: grid; background: var(--surface); margin: var(--sp-3) calc(-1 * var(--pad)); padding: 0 var(--pad) var(--sp-2); }
  .fixa.presa { box-shadow: 0 1px 0 var(--line); }
  .tcurto { height: var(--sp-5); line-height: var(--sp-5); font-size: var(--fs-12); font-weight: 500; color: var(--ink2); opacity: 0; transition: opacity var(--dur-1); }
  .presa .tcurto { opacity: 1; }
  .abas { display: flex; }
  table { scroll-margin-top: 96px; }

  blockquote { padding: var(--sp-3) 0 var(--sp-3) var(--sp-4); border-left: 2px solid var(--line-strong); display: grid; gap: var(--sp-1); margin-bottom: var(--sp-4); }
  blockquote.alerta { border-left-color: var(--alert); }
  blockquote.alerta .rot { color: var(--alert); }
  q { font-family: var(--f-display); font-size: var(--fs-17); line-height: var(--lh-17); quotes: '“' '”'; }
  .entrega { margin-bottom: var(--sp-5); }

  .fatos { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--sp-4); padding-block: var(--sp-4); border-block: 1px solid var(--line); }
  .fatos > div { display: grid; grid-template-rows: auto auto 1fr auto; }   /* as reguas da mediana alinham na base */
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
  .ver { font-size: var(--fs-12); line-height: var(--lh-12); color: var(--ink2); min-height: var(--alvo); border-radius: var(--r-1); }

  .pares > div { display: grid; grid-template-columns: 96px minmax(0, 1fr); gap: var(--sp-3); padding: var(--sp-2) 0; border-top: 1px solid var(--line); align-items: baseline; }
  .pares > div:first-child { border-top: 0; }
  .pares dt { font-size: var(--fs-12); line-height: var(--lh-14); color: var(--muted); }
  .pares dd { display: flex; align-items: center; gap: var(--sp-2); min-width: 0; flex-wrap: wrap; }

  .ress { display: grid; }
  .ress li { display: grid; grid-template-columns: 10px minmax(0, 1fr) auto; column-gap: var(--sp-2); row-gap: 2px; align-items: baseline; padding: var(--sp-2) 0; border-top: 1px solid var(--line); }
  .ress li:first-child { border-top: 0; }
  .cel { width: 10px; height: 10px; border-radius: 2px; background: none; box-shadow: inset 0 0 0 1.5px var(--line-strong); align-self: center; }
  .cel.ganha { background: var(--res-ganha); box-shadow: none; } .cel.ruido { background: var(--res-ruido); box-shadow: none; } .cel.perde { background: var(--res-perde); box-shadow: none; }
  .ress .b { min-width: 0; }
  .ress .b b { font-weight: 500; }
  .ress .dif { font-weight: 500; white-space: nowrap; }
  .ress .dif.perde { color: var(--alert); }
  .ress .det { grid-column: 2 / -1; font-size: var(--fs-12); line-height: var(--lh-12); }
  .det .ver { min-height: 0; margin-left: var(--sp-2); position: relative; }
  .det .ver::after { content: ''; position: absolute; inset: -8px -6px; }
  /* no toque: 44 px de alvo em cada link pequeno, sem que dois alvos vizinhos se cubram */
  @media (pointer: coarse) {
    .ver { position: relative; } .ver::after { content: ''; position: absolute; inset: -10px -8px; }
    .sinais li:has(.ver) { min-height: 36px; }
    .det .ver::after { inset: -14px -8px; }
    .pares .lk { position: relative; } .pares .lk::after { content: ''; position: absolute; inset: -10px 0; }
  }
  .chave.res { display: flex; gap: var(--sp-1) var(--sp-3); margin-bottom: var(--sp-1); }
  .chave.res span { display: inline-flex; align-items: center; gap: 6px; }
  .chave.res .cel { margin: 0; }
  .mais { width: 100%; margin-top: var(--sp-2); }
  .pos { display: grid; gap: var(--sp-1); margin-top: var(--sp-2); font-size: var(--fs-12); line-height: var(--lh-12); color: var(--ink2); }
  .trilho { display: block; position: relative; height: 4px; border-radius: 2px; background: var(--sunk); max-width: 96px; }
  .trilho i { display: block; height: 100%; border-radius: 2px; background: var(--line-strong); }
  .trilho b { position: absolute; top: -3px; bottom: -3px; width: 2px; margin-left: -1px; border-radius: 1px; background: var(--ink); box-shadow: 0 0 0 1px var(--surface); }
  .tr { width: 16px; border-top: 1.5px dashed var(--muted); display: inline-block; vertical-align: middle; margin-right: 6px; }
  .nota { margin-top: var(--sp-5); }

  table { width: 100%; margin-bottom: var(--sp-5); font-size: var(--fs-12); line-height: var(--lh-12); }
  caption { text-align: left; padding-bottom: var(--sp-2); font-size: var(--fs-14); line-height: var(--lh-14); }
  th, td { text-align: left; padding: 6px 0; border-top: 1px solid var(--line); font-weight: 400; vertical-align: baseline; }
  td { padding-left: var(--sp-3); white-space: nowrap; }
  td.num { text-align: right; font-size: var(--fs-12); width: 1%; }
  td.dp { color: var(--muted); padding-left: var(--sp-2); font-weight: 400; }
  tr.nos th, tr.nos td { font-weight: 600; color: var(--ink); }
  .links { display: flex; flex-wrap: wrap; gap: var(--sp-2); margin-top: var(--sp-5); }
</style>
