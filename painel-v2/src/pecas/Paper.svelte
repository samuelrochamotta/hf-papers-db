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
  import { ordenar, ENTREGA, CAMADA, ESFORCO, EIXOS, SIG, ART, ART_EST, SOL_FRASE, HW, sgn, median, urlSegura, radarValores, intervalo, ganhoDe, FATO, SEM_FATO, nBench, passaDoEixo, tetoDoEixo, aberturaFrase, faltaLer, LIMITE_TIPO, LIMITE_GRAVE } from '../lib/dados.js';
  import { base, corSolidez, dica, marcasRadar } from '../lib/tema.js';
  import { estado, fechar, alternaComparar, abrir, mov } from '../lib/estado.svelte.js';

  // `periodo`: todos os papers do periodo, sem filtro: a mediana e sempre a do periodo
  let { papers, todos, periodo = papers } = $props();
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

  const medBruta = $derived(EIXOS.map(([k]) => median(periodo.map((x) => x.radar[k]))));
  // onde o paper fica frente a mediana do periodo, em cada eixo (mesma conta do radar). Na adocao, mais nota e mais facil
  const IDX = Object.fromEntries(EIXOS.map(([k], i) => [k, i]));
  const frente = (k) => { const v = p.radar[k], m = medBruta[IDX[k]]; return v == null || m == null ? null : { v, m, rot: v === m ? 'na mediana' : k === 'facilidade' ? (v > m ? 'mais fácil que a mediana' : 'mais difícil que a mediana') : v > m ? 'acima da mediana' : 'abaixo da mediana' }; };
  const cor = $derived(p ? (p.sol === 'sem_leitura' ? t.solNada : corSolidez(t, p.sol)) : '');
  const naoLidos = $derived(p ? EIXOS.filter(([k]) => p.radar[k] == null).map(([, r]) => r) : []);
  // O radar desenha a nota de 0 a 100; ao lado do nome de cada eixo vai o fato,
  // na unidade dele. Os avisos ficam no desenho: a faixa da abertura, do
  // confirmado ao maximo possivel, e a marca de corte onde a amplitude passa do teto.
  let largR = $state(360);
  // o radar usa a largura que os nomes dos eixos deixam (uns 95 px de cada lado), ate um teto: no tablet ele nao fica miudo no meio da folha
  const raioR = $derived(Math.round(Math.max(54, Math.min(96, (largR - 190) / 2))));
  const cyR = $derived(raioR + 52);
  const cortesR = $derived(p ? EIXOS.map(([k]) => passaDoEixo(k, p)) : []), faixasR = $derived(p ? EIXOS.map(([k]) => tetoDoEixo(k, p)) : []);
  const fatoR = (k) => (k === 'amplitude' && nBench(p) != null ? `${nBench(p)} bench.` : FATO[k](p));
  const opRadar = $derived.by(() => {
    if (!p || !t.ink) return null;
    return {
      ...base(t),
      tooltip: { ...base(t).tooltip, trigger: 'item', formatter: (q) => q.data.mediana
        ? dica('Mediana do período', ...EIXOS.map(([, r], i) => `${r}: <b>${medBruta[i] == null ? '–' : Math.round(medBruta[i])}</b>`))
        : dica('Este paper', ...EIXOS.map(([k, r]) => `${r}: <b>${FATO[k](p) ?? SEM_FATO[k](p)}</b>${p.radar[k] == null ? '' : ` · nota ${p.radar[k]}`}`)) },
      radar: { indicator: EIXOS.map(([k, r]) => (fatoR(k) == null ? { name: `${r}\n${SEM_FATO[k](p).toLowerCase()}`, max: 100, color: t.muted } : { name: `${r}\n{v|${fatoR(k)}}`, max: 100 })),
        radius: raioR, center: ['50%', cyR], splitNumber: 4, axisNameGap: 20,
        axisName: { color: t.ink2, fontSize: 12, fontFamily: t.fUi, lineHeight: 16, rich: { v: { fontFamily: t.fUi, fontSize: 12, color: t.ink, fontWeight: 600 } } },
        splitLine: { lineStyle: { color: t.line } }, splitArea: { show: false }, axisLine: { lineStyle: { color: t.line } } },
      graphic: marcasRadar(t, { cx: largR / 2, cy: cyR, r: raioR, itens: [{ valores: radarValores(EIXOS.map(([k]) => p.radar[k])), cor, simbolo: 'circle', faixas: faixasR, cortes: cortesR }] }),
      series: [{ type: 'radar', data: [
        { name: 'Mediana', mediana: true, value: radarValores(medBruta), symbol: 'none', lineStyle: { color: t.muted, type: [4, 4], width: 1 } },
        { name: p.t, value: radarValores(EIXOS.map(([k]) => p.radar[k])), symbol: naoLidos.length ? 'none' : 'circle', symbolSize: 5,
          itemStyle: { color: cor }, lineStyle: { color: cor, width: 2 }, areaStyle: { color: cor, opacity: .14 } },
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
    return { curta: 'leitura parcial', frase: ate ? `Leitura parcial: o texto foi lido até “${ate}”; o que vem depois ficou fora.` : 'Leitura parcial.' };
  });

  function tecla(e) {
    if (!p) return;
    if (e.key === 'Escape') { fechar(); return; }
    if (e.target.closest?.('input,select,textarea')) return;
    if (e.altKey && (e.key === 'ArrowRight' || e.key === 'ArrowLeft')) { e.preventDefault(); if (pos >= 0) vai(e.key === 'ArrowRight' ? 1 : -1); }
  }
  const ABAS = [[1, 'Resumo'], [2, 'Trechos'], [3, 'Ficha']];
  // Quando a faixa das abas prende no topo, ela passa a dizer de que paper e a ficha e ganha a linha de baixo.
  // A sentinela fica logo acima da faixa: so conta como presa quando o cabecalho inteiro (titulo, votos, links)
  // ja saiu da tela, nunca com os metadados ainda a vista
  let presa = $state(false);
  function olhaFaixa(no) {
    const raiz = no.closest('.corpo');
    const io = new IntersectionObserver(([e]) => (presa = !e.isIntersecting && e.boundingClientRect.top < (e.rootBounds?.top ?? 0) + 14), { root: raiz, rootMargin: '12px 0px 0px 0px' });
    io.observe(no);
    return { destroy() { io.disconnect(); presa = false; } };
  }
  // Na ficha, os numeros de uma tabela tem todos as mesmas casas: a virgula fica numa coluna so.
  const nCasas = (n) => { if (n == null || !Number.isFinite(n)) return 0; const s = String(+Math.abs(n).toFixed(2)), i = s.indexOf('.'); return i < 0 ? 0 : s.length - i - 1; };
  const casasDe = (r, j) => Math.max(0, ...r.lin.map((l) => nCasas(l[j])));
  const fixo = (n, c) => n.toLocaleString('pt-BR', { minimumFractionDigits: c, maximumFractionDigits: c });
  // os dois numeros de um resultado saem com as mesmas casas: "98,8 contra 98,0"
  const par = (r, v) => fixo(v, Math.min(2, Math.max(nCasas(r.nos[1]), nCasas(r.ext[1]))));
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
        <h2 id="paper-titulo" class="titulo" tabindex="-1">{p.t}</h2>
        <!-- a frase e do modelo, nao dos autores (decisao 8): vai marcada e sem a serifa das palavras do paper -->
        {#if p.prob}<p class="prob"><span class="rot">Problema, segundo o modelo</span><span class="fr">{p.prob}</span></p>{/if}
        <p class="meta t-12 mut"><span class="pts"><span><span class="num">{p.u}</span> votos</span><span>{intervalo(p.d, p.d)}</span>{#if p.org}<span>{p.org}</span>{/if}</span><span class="pts"><span><a class="lk" href={p.url} target="_blank" rel="noopener">arXiv <span class="num">{p.id}</span></a></span><span><a class="lk" href="https://huggingface.co/papers/{p.id}" target="_blank" rel="noopener">Hugging Face</a></span></span></p>

        <div class="sentinela" use:olhaFaixa></div>
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

          <div class="kpis">
          <dl class="fatos">
            <div><dt class="rot">Ganho</dt>
              {#if ganhoDe(p) != null}<dd class="v titulo" class:neg={ganhoDe(p) < 0}>{sgn(ganhoDe(p))}%</dd><dd class="d">{comRival > 1 ? `mediana de ${comRival} resultados, contra o melhor rival externo` : p.best ? `ganho relativo em 1 resultado, contra ${p.best.x}` : 'ganho relativo em 1 resultado'}</dd>
              {:else}<dd class="v titulo nd">{p.res.length ? 'Sem rival' : 'Não lido'}</dd><dd class="d">{p.res.length ? 'os resultados não trazem rival externo' : 'nenhum resultado em tabela lido'}</dd>{/if}{@render frenteMed('ganho')}</div>
            <div><dt class="rot">Prova</dt>
              <dd class="v titulo" class:nd={p.sol === 'sem_leitura'}>{p.sol === 'sem_leitura' ? 'Não avaliada' : SOL_FRASE[p.sol].replace('Prova ', '').replace(/^./, (c) => c.toUpperCase())}</dd>
              <dd class="d">{sinais}</dd>{@render frenteMed('solidez')}</div>
            <div><dt class="rot">Adoção</dt>
              <dd class="v titulo" class:nd={p.radar.facilidade == null}>{ESFORCO[p.esf]}</dd>
              <dd class="d">{[aberturaFrase(p), faltaLer(p)].filter(Boolean).join(' · ')}</dd>{@render frenteMed('facilidade')}</div>
          </dl>
          <!-- a base da comparacao, uma vez so, para as tres reguas -->
          {#if ['ganho', 'solidez', 'facilidade'].some((k) => frente(k))}<p class="chv-k t-12 mut"><i aria-hidden="true"></i>mediana do período</p>{/if}
          </div>

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
              <div><dt>Facilidade</dt><dd class:mut={p.radar.facilidade == null}>{#if p.radar.facilidade != null}<Degraus esf={p.esf} />{/if}{ESFORCO[p.esf]}</dd></div>
              <div><dt>Hardware</dt><dd class:mut={p.hw === 'nao_reportado'}>{HW[p.hw] || p.hw}</dd></div>
              {#each Object.entries(p.ab) as [k, v]}
                <div><dt>{ART[k]}</dt><dd class:mut={v !== 'liberado'}>{#if linkDe(k)}<a class="lk" href={linkDe(k)} target="_blank" rel="noopener">{#each curtaUrl(linkDe(k)).split('/') as parte, pi}{#if pi}/<wbr />{/if}{parte}{/each}</a>{:else}{ART_EST[v]}{/if}</dd></div>
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
                    <span class="det mut">{#if r.nos && r.ext}<span class="vh">{ROT_ESTADO[r.e]}: </span><span class="num">{par(r, r.nos[1])}</span> contra <span class="num">{par(r, r.ext[1])}</span> de {r.ext[0]}{:else}{ROT_ESTADO[r.e]}{/if}{#if ri < LIM_FICHA && r.lin.length}<button class="lk ver" aria-label="Ver a tabela de {r.b}" onclick={() => verTabela(ri)}>tabela</button>{/if}</span>
                  </li>
                {/each}
              </ul>
              {#if p.res.length > LIM_RES}<button class="btn sec mais" aria-expanded={todosRes} onclick={() => (todosRes = !todosRes)}>{todosRes ? 'Mostrar menos' : `Ver os ${p.res.length} resultados`}</button>{/if}
            </section>
          {/if}

          <section class="bloco">
            <header><h3>Os seis eixos</h3></header>
            <div bind:clientWidth={largR}>{#if opRadar}<Grafico opcao={opRadar} altura={2 * raioR + 100} rotulo="Radar do paper nos seis eixos, contra a mediana do período" />{/if}</div>
            <!-- a chave fica embaixo do desenho, como na comparacao -->
            <p class="t-12 mut chv"><span><i class="tr"></i>mediana do período</span><span>anéis em 50 e 100, a nota de cada eixo</span>{#if faixasR.some((x) => x != null)}<span><i class="fx"></i>até onde a parte não lida pode levar</span>{/if}{#if cortesR.some(Boolean)}<span><b aria-hidden="true">»</b>passa do eixo</span>{/if}</p>
          </section>
          <p class="nota t-12 mut">{leitura.frase}</p>

        {:else if estado.prof === 2}
          {#if p.entTr}<blockquote><span class="rot">O que entrega</span><q lang="en">{p.entTr}</q></blockquote>{/if}
          {#if p.man}
            <blockquote class:alerta={p.man.conf === false}><span class="rot pts"><span>Manchete</span><span>{p.man.conf ? 'confere com a tabela' : p.man.conf === false ? 'número fora das tabelas lidas' : 'sem tabela para conferir'}</span></span><q lang="en">{p.man.tr}</q>{#if p.man.n != null}<span class="num-man t-12">o número: <b class="num">{p.man.n.toLocaleString('pt-BR')}</b>{p.man.u ? ` ${p.man.u}` : ''}{#if p.man.contra}{' '}contra {p.man.contra}{/if} · <button class="lk" onclick={() => (estado.prof = 3)}>ver as tabelas</button></span>{/if}</blockquote>
          {/if}
          {#each p.aleg.filter((a) => a[0] !== 'manchete') as a}
            <blockquote><span class="rot pts"><span>{ALEG[a[0]] || a[0]}</span>{#if secao(a[2])}<span>{secao(a[2])}</span>{/if}</span><q lang="en">{a[1]}</q></blockquote>
          {/each}
          {#each p.ress.filter((r) => r[1] !== p.entTr) as r}<blockquote class:alerta={LIMITE_GRAVE.includes(r[0])}><span class="rot pts"><span>{LIMITE_GRAVE.includes(r[0]) ? 'Limite grave' : 'Limite admitido'}</span>{#if LIMITE_TIPO[r[0]]}<span>{LIMITE_TIPO[r[0]]}</span>{/if}{#if secao(r[2])}<span>{secao(r[2])}</span>{/if}</span><q lang="en">{r[1]}</q></blockquote>{/each}
          {#if !p.entTr && !p.man && !p.aleg.length && !p.ress.length}<div class="vazio">A leitura não trouxe trechos deste paper.</div>{/if}
          <p class="nota t-12 mut">{leitura.frase}</p>

        {:else}
          <div class="tabelas">
          {#each p.res.slice(0, LIM_FICHA) as r, ri}
            {@const cv = casasDe(r, 2)}
            {@const cd = casasDe(r, 3)}
            {@const temDp = r.lin.some((l) => l[3] != null)}
            <table id="tab-{ri}">
              <caption class="pts"><b>{r.b}</b>{#if r.tab}<span class="mut">{r.tab}</span>{/if}{#if r.m && r.m !== r.b}<span class="mut">{r.m}</span>{/if}</caption>
              <thead><tr><th scope="col">Sistema</th><th scope="col">Papel</th><th scope="col" class="num">Valor</th>{#if temDp}<th scope="col" class="num">± reportado</th>{/if}</tr></thead>
              <tbody>
                {#each r.lin as l}
                  {@const rival = l[1] === 'externo' && r.ext && l[0] === r.ext[0] && l[2] === r.ext[1]}
                  <tr class:nos={l[1] === 'nosso'} class:rival><th scope="row">{l[0]}</th><td class="mut papel">{rival ? 'melhor rival' : LINHA[l[1]] || l[1]}</td><td class="num v">{l[2] == null ? '–' : fixo(l[2], cv)}</td>{#if temDp}<td class="num dp">{#if l[3] != null}±{fixo(l[3], cd)}{/if}</td>{/if}</tr>
                {/each}
              </tbody>
            </table>
          {/each}
          </div>
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
  /* celular: a folha ocupa a tela inteira; a faixa do fundo escurecido nao tira altura da leitura */
  @media (max-width: 639px) { .paper { inset: 0; border-radius: 0; padding-top: env(safe-area-inset-top, 0px); } }
  @media (min-width: 1024px) {
    .paper { inset: 0 0 0 auto; width: min(var(--gaveta), 44vw); border-radius: 0; border-left: 1px solid var(--line); box-shadow: var(--sombra-2); }
  }
  .cabeca { display: flex; align-items: center; justify-content: space-between; gap: var(--sp-2); padding: var(--sp-2) var(--sp-3); border-bottom: 1px solid var(--line); min-height: var(--barra); }
  .nav, .acoes { display: flex; align-items: center; gap: var(--sp-1); }
  .nav b { color: var(--ink); font-weight: 500; }
  .corpo { --pad: var(--sp-4); overflow-y: auto; overscroll-behavior: contain; padding: 0 var(--pad) var(--sp-12); }
  @media (min-width: 768px) { .corpo { --pad: var(--sp-6); } }
  .corpo > div { max-width: 680px; margin-inline: auto; padding-top: var(--sp-5); }      /* folha larga (tablet): a coluna de leitura nao estica */

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
  .sentinela { height: 0; }
  .tcurto { height: var(--sp-5); line-height: var(--sp-5); font-size: var(--fs-12); font-weight: 500; color: var(--ink2); opacity: 0; transition: opacity var(--dur-1); }
  .presa .tcurto { opacity: 1; }
  .abas { display: flex; }
  table { scroll-margin-top: 96px; }

  blockquote { padding: var(--sp-3) 0 var(--sp-3) var(--sp-4); border-left: 2px solid var(--line-strong); display: grid; gap: var(--sp-1); margin-bottom: var(--sp-4); }
  blockquote.alerta { border-left-color: var(--alert); }
  .num-man { color: var(--ink2); }
  blockquote.alerta .rot { color: var(--alert); }
  q { font-family: var(--f-display); font-size: var(--fs-17); line-height: var(--lh-17); quotes: '“' '”'; }
  .entrega { margin-bottom: var(--sp-5); }

  .kpis { padding-block: var(--sp-4); border-block: 1px solid var(--line); }
  .fatos { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); column-gap: var(--sp-4); }
  .chv-k { display: flex; align-items: center; gap: 6px; margin-top: var(--sp-3); }
  .chv-k i { width: 2px; height: 10px; border-radius: 1px; background: var(--ink); }
  .fatos > div { display: grid; grid-row: span 4; grid-template-rows: subgrid; row-gap: 0; align-content: start; }   /* rotulo, valor, frase e regua em linhas comuns as tres colunas: as reguas alinham entre si */
  .fatos .v { font-size: var(--fs-24); line-height: var(--lh-24); margin-top: 2px; }
  .fatos .v.nd { color: var(--muted); }
  .fatos .v.neg { color: var(--alert); }
  .fatos .d { font-size: var(--fs-12); line-height: var(--lh-12); color: var(--muted); margin-top: 2px; }

  .bloco { margin-top: var(--sp-6); }
  .bloco header { display: flex; align-items: baseline; justify-content: space-between; gap: var(--sp-3); margin-bottom: var(--sp-2); flex-wrap: wrap; }
  h3 { font-size: var(--fs-14); line-height: var(--lh-14); font-weight: 600; }
  .chave { display: inline-flex; align-items: center; gap: 4px; flex-wrap: wrap; }
  .chave .s:not(:first-child) { margin-left: var(--sp-2); }
  .s { width: 16px; height: 16px; border-radius: 50%; display: inline-grid; place-items: center; flex: none; font-size: 12px; line-height: 1; font-style: normal; }
  .s.sim { background: var(--ink); color: var(--surface); }
  .s.nao { color: var(--alert); box-shadow: inset 0 0 0 1.5px var(--alert); }
  .s.nl { color: var(--muted); box-shadow: inset 0 0 0 1px var(--line-strong); }
  .sinais { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: var(--sp-2) var(--sp-4); }
  .sinais li { display: flex; align-items: center; gap: var(--sp-2); min-height: var(--alvo); }      /* com ou sem o link "trecho", as linhas tem a mesma altura */
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
    .sinais li { min-height: 36px; }
    .det .ver::after { inset: -14px -8px; }
    .pares .lk { position: relative; } .pares .lk::after { content: ''; position: absolute; inset: -12px 0; }
  }
  .chave.res { display: flex; gap: var(--sp-1) var(--sp-3); margin-bottom: var(--sp-1); }
  .chave.res span { display: inline-flex; align-items: center; gap: 6px; }
  .chave.res .cel { margin: 0; }
  .mais { width: 100%; margin-top: var(--sp-2); }
  .pos { display: grid; gap: var(--sp-1); margin-top: var(--sp-2); font-size: var(--fs-12); line-height: var(--lh-12); color: var(--ink2); }
  .trilho { display: block; position: relative; height: 4px; border-radius: 2px; background: var(--sunk); }
  .trilho i { display: block; height: 100%; border-radius: 2px; background: var(--line-strong); }
  .trilho b { position: absolute; top: -3px; bottom: -3px; width: 2px; margin-left: -1px; border-radius: 1px; background: var(--ink); box-shadow: 0 0 0 1px var(--surface); }
  .tr { width: 16px; border-top: 1.5px dashed var(--muted); display: inline-block; vertical-align: middle; margin-right: 6px; }
  .chv { display: flex; flex-wrap: wrap; gap: var(--sp-1) var(--sp-4); justify-content: center; margin-top: var(--sp-1); }
  .chv > span { display: inline-flex; align-items: center; white-space: nowrap; }
  .chv .fx { display: inline-block; width: 14px; height: 6px; background: color-mix(in srgb, var(--ink2) 30%, transparent); border-right: 2px solid var(--ink2); margin-right: 6px; vertical-align: middle; }
  .chv b { font-weight: 600; color: var(--ink2); margin-right: 6px; }
  .nota { margin-top: var(--sp-5); }

  /* folha larga (tablet): duas tabelas lado a lado, cada numero perto do seu nome */
  .tabelas { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 288px), 1fr)); column-gap: var(--sp-6); align-items: start; }
  table { width: 100%; margin-bottom: var(--sp-5); font-size: var(--fs-12); line-height: var(--lh-12); }
  caption { text-align: left; padding-bottom: var(--sp-2); font-size: var(--fs-14); line-height: var(--lh-14); }
  th, td { text-align: left; padding: 6px 0; border-top: 1px solid var(--line); font-weight: 400; vertical-align: baseline; }
  td { padding-left: var(--sp-3); white-space: nowrap; }
  /* o nome do sistema so quebra entre palavras; quem cede largura e a coluna do papel */
  tbody th { overflow-wrap: break-word; }
  td.papel { white-space: normal; }
  td.num { text-align: right; font-size: var(--fs-12); width: 1%; }
  td.dp { color: var(--muted); padding-left: var(--sp-2); font-weight: 400; }
  tr.nos th, tr.nos td { font-weight: 600; color: var(--ink); }
  /* o rival que entra na conta do ganho: o mesmo que o Resumo cita */
  tr.rival th, tr.rival td { font-weight: 500; color: var(--ink); }
  thead th { border-top: 0; padding: 0 0 var(--sp-1); font-size: var(--fs-12); color: var(--muted); font-weight: 500; }
  thead th + th { padding-left: var(--sp-3); }
  thead th.num { text-align: right; white-space: nowrap; }
  .links { display: flex; flex-wrap: wrap; gap: var(--sp-2); margin-top: var(--sp-5); }
  .prob { display: flex; flex-wrap: wrap; align-items: baseline; gap: 2px var(--sp-2); margin: 0 0 var(--sp-2); }
  .prob .fr { font-size: var(--fs-14); line-height: var(--lh-14); color: var(--ink2); font-style: italic; }
</style>
