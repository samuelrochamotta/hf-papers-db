<script>
  // Comparacao: ate 3 papers nos seis eixos. O radar da a forma; a tabela da o
  // fato de cada eixo na unidade dele (votos, nivel de prova, % de ganho...).
  // Cada paper tem letra, cor, traco e marcador proprios: a cor nunca e o
  // unico sinal. Na tabela, barra e negrito seguem o valor real: 5 e 9
  // benchmarks nao empatam, perda sai para a esquerda do zero e a abertura
  // mostra os quatro artefatos, um a um.
  import Grafico from '../lib/Grafico.svelte';
  import Icone from '../lib/Icone.svelte';
  import Menu from './Menu.svelte';
  import { EIXOS, EIXO_DICA, FATO, SEM_FATO, ART, ART_EST, nBench, ganhoDe, median, curto, esc, radarValores } from '../lib/dados.js';
  import { base, dica, corCmp } from '../lib/tema.js';
  import { estado, alternaComparar, abrir, MAX_COMPARAR } from '../lib/estado.svelte.js';

  let { papers, todos } = $props();
  let larg = $state(600);
  const t = $derived(estado.tema);
  const porId = $derived(new Map(todos.map((p) => [p.id, p])));
  const sel = $derived(estado.comparar.map((id) => porId.get(id)).filter(Boolean));
  const medBruta = $derived(EIXOS.map(([k]) => median(papers.map((p) => p.radar[k]))));
  const opcoes = $derived(todos.filter((p) => !estado.comparar.includes(p.id)).sort((a, b) => b.u - a.u));
  const noRecorte = $derived(new Set(papers.map((p) => p.id)));
  // O numero que decide o negrito: o valor real em ganho e amplitude, a nota
  // do radar nos outros eixos. Com todos empatados, ninguem leva a linha.
  const medida = (k, p) => (k === 'ganho' ? ganhoDe(p) : k === 'amplitude' ? nBench(p) : p.radar[k]);
  const melhor = $derived(EIXOS.map(([k]) => {
    const vs = sel.map((p) => medida(k, p)).filter((x) => x != null), m = Math.max(...vs);
    return vs.length > 1 && vs.some((x) => x < m) ? m : null;
  }));
  // Posicao na barra, de 0 a 100. A amplitude vai ate o paper com mais
  // benchmarks do periodo; o ganho usa a nota do radar, em que 50 e o zero.
  const maxBench = $derived(Math.max(1, ...todos.map((p) => nBench(p) ?? 0)));
  const pos = (k, p) => (k === 'amplitude' ? (nBench(p) == null ? null : (100 * nBench(p)) / maxBench) : p.radar[k]);
  const medPos = $derived(EIXOS.map(([k]) => median(papers.map((p) => pos(k, p)))));
  const artefatos = (p) => Object.keys(ART).map((a) => `${ART[a]} ${ART_EST[p.ab[a]] ?? 'não lido'}`).join(' · ');
  const TRACO = ['solid', [6, 3], [2, 3]], MARCA = ['circle', 'rect', 'triangle'];
  // o radar ocupa o que a largura deixa (os nomes dos eixos pedem uns 75 px de cada lado) e a altura acompanha: sem vao em cima nem embaixo
  const raio = $derived(Math.round(Math.max(60, Math.min((larg - 150) / 2, 165))));

  const opcao = $derived(!t.ink || !sel.length ? null : {
    ...base(t),
    tooltip: { ...base(t).tooltip, trigger: 'item', formatter: (q) => {
      if (q.data.mediana) return dica('Mediana do recorte', ...EIXOS.map(([, r], i) => `${r}: <b>${medBruta[i] == null ? '–' : Math.round(medBruta[i])}</b>`));
      const p = porId.get(q.data.pid);
      return dica(`${q.data.letra} · ${esc(p.t)}`, ...EIXOS.map(([k, r]) => `${r}: <b>${FATO[k](p) ?? SEM_FATO[k]}</b>`));
    } },
    radar: {
      indicator: EIXOS.map(([, r]) => ({ name: r, max: 100 })), radius: raio, center: ['50%', '50%'], splitNumber: 4, shape: 'polygon',
      axisName: { color: t.ink2, fontSize: 12, fontWeight: 500, fontFamily: t.fUi },
      splitLine: { lineStyle: { color: t.line } }, splitArea: { show: false }, axisLine: { lineStyle: { color: t.line } },
    },
    series: [{ type: 'radar', data: [
      { name: 'Mediana', mediana: true, value: radarValores(medBruta), symbol: 'none', lineStyle: { color: t.muted, type: [4, 4], width: 1 }, areaStyle: { color: t.lineStrong, opacity: .08 } },
      ...sel.map((p, i) => { const c = corCmp(t, i);
        return { name: p.t, pid: p.id, letra: 'ABC'[i], value: radarValores(EIXOS.map(([k]) => p.radar[k])),
          // com eixo nao lido o vertice e so passagem: sem marcador, para nao parecer medida
          symbol: EIXOS.some(([k]) => p.radar[k] == null) ? 'none' : MARCA[i], symbolSize: 7,
          itemStyle: { color: c }, lineStyle: { color: c, width: 2, type: TRACO[i] }, areaStyle: { color: c, opacity: 0.08 },
          emphasis: { areaStyle: { opacity: 0.22 }, lineStyle: { width: 3 } } }; }),
    ] }],
  });

  const maisVotados = () => { estado.comparar = [...papers].sort((a, b) => b.u - a.u).filter((p) => Object.values(p.radar).filter((v) => v != null).length >= 4).slice(0, 2).map((p) => p.id); };
  const v = (x) => (x == null ? null : Math.round(x));
</script>

<section class="comparar" aria-labelledby="h-comparar" data-regiao="comparar">
  <header class="topo">
    <h2 id="h-comparar" class="titulo">Comparar</h2>
    <div class="acoes">
      <!-- o botao de adicionar fica sempre na ponta: nao muda de lugar quando entra o primeiro paper -->
      {#if sel.length}<button class="btn fan limpa" aria-label="Esvaziar a comparação" onclick={() => (estado.comparar = [])}>Esvaziar</button>{/if}
      <span class="t-12 mut"><span class="num">{sel.length}</span> de <span class="num">{MAX_COMPARAR}</span> papers</span>
      {#if opcoes.length}
        <span class="add"><Menu nome="Papers para comparar" icone={sel.length >= MAX_COMPARAR ? 'troca' : 'mais'} busca rotulo={sel.length >= MAX_COMPARAR ? 'Trocar o paper A' : 'Adicionar paper'} descricao={sel.length >= MAX_COMPARAR ? 'Trocar o paper A, o mais antigo da comparação, por outro' : 'Adicionar paper à comparação'} valor="-"
          itens={opcoes.map((p) => [p.id, p.t, p.u])} aoEscolher={alternaComparar} /></span>
      {/if}
    </div>
  </header>

  {#if !sel.length}
    <div class="vazio caixa">Nenhum paper na comparação.
      {#if papers.length > 1}<button class="btn sec" onclick={maisVotados}>Comparar os dois mais votados</button>{/if}
    </div>
  {:else}
    <div class="corpo">
      <div class="g" bind:clientWidth={larg}>
        {#if opcao}<Grafico {opcao} altura={2 * raio + 72} rotulo="Radar de seis eixos com os papers escolhidos e a mediana do recorte" />{/if}
        <p class="chave t-12 mut">
          {#each sel as p, i (p.id)}<span><svg width="26" height="10" aria-hidden="true"><line x1="1" y1="5" x2="25" y2="5" stroke="var(--cmp-{i + 1})" stroke-width="2" stroke-dasharray={i === 1 ? '6 3' : i === 2 ? '2 3' : null} /></svg><b>{'ABC'[i]}</b>{curto(p.t, 18)}</span>{/each}
          <span><i class="med"></i>mediana do recorte</span>
        </p>
      </div>

      <div class="t">
        <table>
          <thead><tr>
            <th scope="col" class="eixo"><span class="vh">Eixo</span></th>
            {#each sel as p, i (p.id)}
              <th scope="col" style:--c="var(--cmp-{i + 1})">
                <span class="cabp">
                  <i class="letra" aria-hidden="true">{'ABC'[i]}</i>
                  <button class="nome" onclick={() => abrir(p.id)} title={p.t} onmouseenter={() => (estado.hover = p.id)} onmouseleave={() => (estado.hover = null)}>
                    <span class="vh">{'ABC'[i]}: </span><span class="nm" class:fora={!noRecorte.has(p.id)}>{curto(p.t, 28)}</span></button>
                  <button class="tira" aria-label="Tirar {p.t} da comparação" title="Tirar da comparação" onclick={() => alternaComparar(p.id)}><Icone nome="x" tam={14} /></button>
                </span>
              </th>
            {/each}
          </tr></thead>
          <tbody>
            {#each EIXOS as [k, r], ei}
              {@const med = v(medPos[ei])}
              <tr>
                <th scope="row" class="eixo" title={EIXO_DICA[k]}>{r}</th>
                {#each sel as p, i (p.id)}
                  {@const x = v(pos(k, p))}
                  {@const f = FATO[k](p)}
                  <td style:--c="var(--cmp-{i + 1})" class:top={melhor[ei] != null && medida(k, p) === melhor[ei]}>
                    <span class="fato" class:mut={f == null}>{#if k === 'amplitude' && f != null}{nBench(p)} <span class="un-l">{nBench(p) === 1 ? 'benchmark' : 'benchmarks'}</span><span class="un-c">bench.</span>{:else}{f ?? SEM_FATO[k]}{/if}</span>
                    {#if k === 'abertura'}
                      <span class="pecas" title={artefatos(p)}>{#each Object.keys(ART) as a}<i class={p.ab[a] ?? 'nao_lido'}></i>{/each}<span class="vh">{artefatos(p)}</span></span>
                    {:else}
                      <span class="trilho" class:nd={x == null} aria-hidden="true">
                        {#if x != null}<i style:left="{k === 'ganho' ? Math.min(50, x) : 0}%" style:width="{k === 'ganho' ? Math.abs(x - 50) : x}%"></i>{/if}
                        {#if k === 'ganho' && x != null}<em></em>{/if}
                        {#if med != null}<b style:left="{med}%"></b>{/if}
                      </span>
                    {/if}
                  </td>
                {/each}
              </tr>
            {/each}
          </tbody>
        </table>
        <p class="chave pe t-12 mut">
          <span><i class="tique"></i>mediana do recorte</span>
          {#if sel.length > 1}<span><b>negrito</b>melhor da linha</span>{/if}
          <span><span class="pecas ex" aria-hidden="true"><i class="liberado"></i><i class="liberado"></i><i class="liberado"></i><i class="liberado"></i></span>código, pesos, dados e demo</span>
        </p>
      </div>
    </div>
  {/if}
</section>

<style>
  .comparar { min-width: 0; container-type: inline-size; }
  .topo { display: flex; align-items: center; justify-content: space-between; gap: var(--sp-3); flex-wrap: wrap; margin-bottom: var(--sp-4); }
  h2 { font-size: var(--fs-24); line-height: var(--lh-24); }
  .acoes { display: flex; align-items: center; gap: var(--sp-3); }
  .add { display: inline-flex; }
  .add :global(.sel) { min-height: var(--ctl); }
  .limpa { padding: 0 var(--sp-2); }
  .caixa { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-3); padding-block: var(--sp-12); }

  .corpo { display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--sp-4); background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-3); padding: var(--sp-4); }
  @container (min-width: 860px) { .corpo { grid-template-columns: minmax(300px, 5fr) minmax(0, 7fr); gap: var(--sp-8); padding: var(--sp-6); align-items: center; } }
  .g { min-width: 0; }
  .chave { display: flex; flex-wrap: wrap; gap: var(--sp-1) var(--sp-4); justify-content: center; margin-top: var(--sp-2); }
  .chave span { display: inline-flex; align-items: center; gap: 6px; min-width: 0; }
  .chave b { font-weight: 600; color: var(--ink); }
  .chave.pe { justify-content: flex-start; margin-top: var(--sp-4); padding-top: var(--sp-3); border-top: 1px solid var(--line); --c: var(--ink2); }
  .chave .med { width: 16px; height: 10px; border-radius: 2px; border: 1px dashed var(--muted); background: color-mix(in srgb, var(--line-strong) 12%, var(--surface)); }
  .chave .tique { width: 2px; height: 12px; border-radius: 1px; background: var(--ink2); }

  .letra { width: 20px; height: 20px; border-radius: 50%; background: var(--c); color: var(--surface); display: inline-grid; place-items: center; font-size: var(--fs-12); line-height: 1; font-weight: 600; font-style: normal; flex: none; }

  .t { min-width: 0; }
  table { width: 100%; table-layout: fixed; }
  /* o valor que quebra em duas linhas nao tira a barra do lugar: as barras de uma linha ficam alinhadas pelo pe */
  th, td { text-align: left; vertical-align: bottom; padding: var(--sp-3) var(--sp-2); border-top: 1px solid var(--line); font-weight: 400; min-width: 0; }
  tbody th { vertical-align: top; }
  thead th { border-top: 0; padding-top: 0; padding-bottom: var(--sp-3); border-bottom: 1px solid var(--line-strong); vertical-align: top; }
  tbody tr:first-child th, tbody tr:first-child td { border-top: 0; }
  .eixo { width: 88px; padding-left: 0; font-size: var(--fs-12); line-height: var(--lh-14); font-weight: 500; color: var(--muted); }
  .cabp { display: grid; grid-template-columns: 20px minmax(0, 1fr) 24px; gap: var(--sp-2); align-items: start; }
  .nome { text-align: left; overflow-wrap: break-word; font-size: var(--fs-12); line-height: var(--lh-12); font-weight: 500; border-radius: var(--r-1); min-height: var(--alvo); min-width: 0; }
  .nome .nm { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; text-decoration: underline; text-decoration-color: var(--line-strong); text-underline-offset: 3px; }
  .nome:hover .nm { text-decoration-color: currentColor; }
  @media (pointer: coarse) { .nome { position: relative; } .nome::after { content: ''; position: absolute; inset: 0 0 -22px; } }      /* para baixo: em cima fica o alvo do botao de tirar */
  .nm.fora { color: var(--muted); }
  .tira { width: 28px; height: 28px; margin: -4px -4px 0 0; border-radius: 50%; display: grid; place-items: center; color: var(--muted); transition: background var(--dur-1), color var(--dur-1); }
  .tira { position: relative; }
  .tira::after { content: ''; position: absolute; inset: -8px; }                 /* alvo de 44 px */
  .tira:hover { background: var(--hover); color: var(--ink); }
  .fato { display: block; overflow-wrap: break-word; }
  .un-c { display: none; }
  .fato.mut { color: var(--muted); }
  td.top .fato { font-weight: 600; }
  .trilho { display: block; position: relative; height: 6px; border-radius: 3px; background: var(--sunk); margin-top: var(--sp-2); }
  .trilho.nd { background: none; box-shadow: inset 0 0 0 1px var(--line); }
  .trilho i { position: absolute; top: 0; bottom: 0; min-width: 2px; border-radius: 3px; background: var(--c); transition: width var(--dur-3) var(--sai), left var(--dur-3) var(--sai); }
  .trilho em { position: absolute; left: 50%; top: -1px; bottom: -1px; width: 1px; background: var(--muted); }
  .trilho b { position: absolute; top: -3px; bottom: -3px; width: 2px; margin-left: -1px; background: var(--ink2); border-radius: 1px; }
  /* abertura: um segmento por artefato (codigo, pesos, dados, demo), no estado em que a leitura o achou */
  .pecas { display: flex; gap: 3px; margin-top: var(--sp-2); }
  .pecas i { flex: 1; height: 6px; border-radius: 3px; background: var(--sunk); }
  .pecas .liberado { background: var(--c); }
  .pecas .prometido, .pecas .so_pagina { background: none; box-shadow: inset 0 0 0 1.5px var(--c); }
  .pecas .nao_lido { background: none; box-shadow: inset 0 0 0 1px var(--line); }
  .pecas.ex { width: 56px; margin-top: 0; flex: none; }

  @container (max-width: 520px) {
    .eixo { width: 68px; }
    .cabp { grid-template-columns: minmax(0, 1fr) 28px; }
    .cabp .nome { grid-column: 1 / -1; grid-row: 2; }
    .un-l { display: none; } .un-c { display: inline; }
    .fato { font-size: var(--fs-12); line-height: var(--lh-12); }
    th, td { padding-inline: var(--sp-1); }
  }
</style>
