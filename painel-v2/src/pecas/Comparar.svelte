<script>
  // Comparacao: ate 3 papers nos seis eixos. O radar da a forma; a tabela da o
  // fato de cada eixo na unidade dele (votos, nivel de prova, % de ganho...).
  // Cada paper tem letra, cor, traco e marcador proprios: a cor nunca e o
  // unico sinal. Variantes do experimento: 'sobre' (radar sobreposto e barras),
  // 'lado' (um radar por paper), 'pontos' (radar e trilho comum por eixo).
  import Grafico from '../lib/Grafico.svelte';
  import Icone from '../lib/Icone.svelte';
  import Menu from './Menu.svelte';
  import { EIXOS, EIXO_DICA, FATO, SEM_FATO, nBench, median, curto, esc, radarValores } from '../lib/dados.js';
  import { base, dica, corCmp } from '../lib/tema.js';
  import { estado, alternaComparar, abrir, MAX_COMPARAR } from '../lib/estado.svelte.js';

  let { papers, todos } = $props();
  let larg = $state(600);
  const t = $derived(estado.tema);
  const forma = $derived(estado.v.radar);
  const porId = $derived(new Map(todos.map((p) => [p.id, p])));
  const sel = $derived(estado.comparar.map((id) => porId.get(id)).filter(Boolean));
  const medBruta = $derived(EIXOS.map(([k]) => median(papers.map((p) => p.radar[k]))));
  const opcoes = $derived(todos.filter((p) => !estado.comparar.includes(p.id)).sort((a, b) => b.u - a.u));
  const noRecorte = $derived(new Set(papers.map((p) => p.id)));
  const melhor = $derived(EIXOS.map(([k]) => Math.max(-1, ...sel.map((p) => p.radar[k] ?? -1))));
  const TRACO = ['solid', [6, 3], [2, 3]], MARCA = ['circle', 'rect', 'triangle'];

  const radar = (ps, idx) => ({
    ...base(t),
    tooltip: { ...base(t).tooltip, trigger: 'item', formatter: (q) => {
      if (q.data.mediana) return dica('Mediana do recorte', ...EIXOS.map(([, r], i) => `${r}: <b>${medBruta[i] == null ? '–' : Math.round(medBruta[i])}</b>`));
      const p = porId.get(q.data.pid);
      return dica(`${q.data.letra} · ${esc(p.t)}`, ...EIXOS.map(([k, r]) => `${r}: <b>${FATO[k](p) ?? SEM_FATO[k]}</b>`));
    } },
    radar: {
      indicator: EIXOS.map(([, r]) => ({ name: r, max: 100 })), radius: (ps.length === 1 && forma === 'lado') || larg < 400 ? '54%' : '64%', center: ['50%', '52%'], splitNumber: 4, shape: 'polygon',
      axisName: { color: t.ink2, fontSize: 12, fontWeight: 500, fontFamily: t.fUi },
      splitLine: { lineStyle: { color: t.line } }, splitArea: { show: false }, axisLine: { lineStyle: { color: t.line } },
    },
    series: [{ type: 'radar', data: [
      { name: 'Mediana', mediana: true, value: radarValores(medBruta), symbol: 'none', lineStyle: { width: 0 }, areaStyle: { color: t.lineStrong, opacity: .18 } },
      ...ps.map((p, j) => { const i = idx[j], c = corCmp(t, i);
        return { name: p.t, pid: p.id, letra: 'ABC'[i], value: radarValores(EIXOS.map(([k]) => p.radar[k])),
          // com eixo nao lido o vertice e so passagem: sem marcador, para nao parecer medida
          symbol: EIXOS.some(([k]) => p.radar[k] == null) ? 'none' : MARCA[i], symbolSize: 7,
          itemStyle: { color: c }, lineStyle: { color: c, width: 2, type: TRACO[i] }, areaStyle: { color: c, opacity: 0.08 },
          emphasis: { areaStyle: { opacity: 0.22 }, lineStyle: { width: 3 } } }; }),
    ] }],
  });
  const opSobre = $derived(t.ink && sel.length ? radar(sel, sel.map((_, i) => i)) : null);
  const opLado = $derived(t.ink ? sel.map((p, i) => radar([p], [i])) : []);

  const maisVotados = () => { estado.comparar = [...papers].sort((a, b) => b.u - a.u).filter((p) => Object.values(p.radar).filter((v) => v != null).length >= 4).slice(0, 2).map((p) => p.id); };
  const v = (x) => (x == null ? null : Math.round(x));
</script>

<section class="comparar f-{forma}" aria-labelledby="h-comparar" data-regiao="comparar">
  <header class="topo">
    <h2 id="h-comparar" class="titulo">Comparar</h2>
    <div class="acoes">
      <!-- o botao de adicionar fica sempre na ponta: nao muda de lugar quando entra o primeiro paper -->
      {#if sel.length}<button class="btn fan limpa" onclick={() => (estado.comparar = [])}>Limpar</button>{/if}
      <span class="t-12 mut num">{sel.length} de {MAX_COMPARAR}</span>
      {#if opcoes.length}
        <span class="add"><Menu nome="Papers para comparar" icone="mais" busca rotulo={sel.length >= MAX_COMPARAR ? 'Trocar paper' : 'Adicionar paper'} descricao={sel.length >= MAX_COMPARAR ? 'Trocar um paper da comparação' : 'Adicionar paper à comparação'} valor="-"
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
        {#if forma === 'lado'}
          <div class="multi">
            {#each sel as p, i (p.id)}
              <figure><figcaption><i class="letra" style:--c="var(--cmp-{i + 1})">{'ABC'[i]}</i><span class="um">{curto(p.t, 22)}</span></figcaption>
                <Grafico opcao={opLado[i]} altura={212} rotulo="Radar de {p.t} nos seis eixos" /></figure>
            {/each}
          </div>
        {:else if opSobre}
          <Grafico opcao={opSobre} altura={340} rotulo="Radar de seis eixos com os papers escolhidos e a mediana do recorte" />
        {/if}
        <p class="chave t-12 mut">
          {#if forma !== 'lado'}{#each sel as p, i (p.id)}<span><svg width="26" height="10" aria-hidden="true"><line x1="1" y1="5" x2="25" y2="5" stroke="var(--cmp-{i + 1})" stroke-width="2" stroke-dasharray={i === 1 ? '6 3' : i === 2 ? '2 3' : null} /></svg>{'ABC'[i]}</span>{/each}{/if}
          <span><i class="med"></i><i class="tique"></i>mediana do recorte</span>
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
                  <button class="tira" aria-label="Tirar {p.t} da comparação" title="Tirar da comparação" onclick={() => alternaComparar(p.id)}><Icone nome="x" tam={12} /></button>
                </span>
              </th>
            {/each}
          </tr></thead>
          <tbody>
            {#each EIXOS as [k, r], ei}
              {@const med = v(medBruta[ei])}
              <tr>
                <th scope="row" class="eixo" title={EIXO_DICA[k]}>{r}</th>
                {#each sel as p, i (p.id)}
                  {@const x = v(p.radar[k])}
                  {@const f = FATO[k](p)}
                  <td style:--c="var(--cmp-{i + 1})" class:top={sel.length > 1 && x != null && p.radar[k] === melhor[ei]}>
                    <span class="fato" class:mut={f == null}>{#if k === 'amplitude' && f != null}{nBench(p)} <span class="un-l">{nBench(p) === 1 ? 'benchmark' : 'benchmarks'}</span><span class="un-c">bench.</span>{:else}{f ?? SEM_FATO[k]}{/if}</span>
                    {#if forma !== 'pontos'}
                      <span class="trilho" class:nd={x == null} aria-hidden="true">{#if x != null}<i style:width="{x}%"></i>{/if}{#if med != null}<b style:left="{med}%"></b>{/if}</span>
                    {/if}
                  </td>
                {/each}
              </tr>
              {#if forma === 'pontos'}
                <tr class="pontos" aria-hidden="true"><td></td><td colspan={sel.length}>
                  <span class="pista" style:height="{18 + (sel.length - 1) * 14}px">
                    {#if med != null}<b style:left="{med}%"></b>{/if}
                    {#each sel as p, i (p.id)}{#if p.radar[k] != null}<i class="letra" style:left="{p.radar[k]}%" style:top="{i * 14}px" style:--c="var(--cmp-{i + 1})">{'ABC'[i]}</i>{/if}{/each}
                  </span>
                </td></tr>
              {/if}
            {/each}
          </tbody>
        </table>
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
  @container (min-width: 860px) { .corpo { grid-template-columns: minmax(300px, 5fr) minmax(0, 7fr); gap: var(--sp-8); padding: var(--sp-6); align-items: center; }
    .f-lado .corpo { grid-template-columns: minmax(0, 1fr); } }
  .g { min-width: 0; }
  .multi { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: var(--sp-4); }
  figcaption { display: flex; align-items: center; gap: var(--sp-2); font-size: var(--fs-12); line-height: var(--lh-12); font-weight: 500; }
  .chave { display: flex; flex-wrap: wrap; gap: var(--sp-1) var(--sp-4); justify-content: center; margin-top: var(--sp-2); }
  .chave span { display: inline-flex; align-items: center; gap: 6px; }
  .chave .med { width: 12px; height: 12px; border-radius: 2px; background: color-mix(in srgb, var(--line-strong) 26%, var(--surface)); }
  .chave .tique { width: 2px; height: 12px; border-radius: 1px; background: var(--ink2); }

  .letra { width: 20px; height: 20px; border-radius: 50%; background: var(--c); color: var(--surface); display: inline-grid; place-items: center; font-size: var(--fs-12); line-height: 1; font-weight: 600; font-style: normal; flex: none; }

  .t { min-width: 0; }
  table { width: 100%; table-layout: fixed; }
  th, td { text-align: left; vertical-align: top; padding: var(--sp-3) var(--sp-2); border-top: 1px solid var(--line); font-weight: 400; min-width: 0; }
  thead th { border-top: 0; padding-top: 0; padding-bottom: var(--sp-3); border-bottom: 1px solid var(--line-strong); vertical-align: bottom; }
  tbody tr:first-child th, tbody tr:first-child td { border-top: 0; }
  .eixo { width: 88px; padding-left: 0; font-size: var(--fs-12); line-height: var(--lh-14); font-weight: 500; color: var(--muted); }
  .cabp { display: grid; grid-template-columns: 20px minmax(0, 1fr) 24px; gap: var(--sp-2); align-items: start; }
  .nome { text-align: left; overflow-wrap: break-word; font-size: var(--fs-12); line-height: var(--lh-12); font-weight: 500; border-radius: var(--r-1); min-height: var(--alvo); min-width: 0; }
  .nome .nm { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; text-decoration: underline; text-decoration-color: var(--line-strong); text-underline-offset: 3px; }
  .nome:hover .nm { text-decoration-color: currentColor; }
  .nm.fora { color: var(--muted); }
  .tira { width: 24px; height: 24px; border-radius: 50%; display: grid; place-items: center; color: var(--muted); transition: background var(--dur-1), color var(--dur-1); }
  .tira:hover { background: var(--hover); color: var(--ink); }
  .fato { display: block; overflow-wrap: break-word; }
  .un-c { display: none; }
  .fato.mut { color: var(--muted); }
  td.top .fato { font-weight: 600; }
  .trilho { display: block; position: relative; height: 6px; border-radius: 3px; background: var(--sunk); margin-top: var(--sp-2); }
  .trilho.nd { background: none; box-shadow: inset 0 0 0 1px var(--line); }
  .trilho i { display: block; height: 100%; border-radius: 3px; background: var(--c); transition: width var(--dur-3) var(--sai); }
  .trilho b, .pista b { position: absolute; top: -3px; bottom: -3px; width: 2px; margin-left: -1px; background: var(--ink2); border-radius: 1px; }
  .pontos td { border-top: 0; padding-top: 0; }
  .pista { display: block; position: relative; margin: 0 10px; background: linear-gradient(var(--line), var(--line)) 0 50% / 100% 1px no-repeat; }
  .pista b { top: 0; bottom: 0; }
  .pista .letra { position: absolute; margin-left: -9px; width: 18px; height: 18px; transition: left var(--dur-3) var(--sai); }

  @container (max-width: 520px) {
    .eixo { width: 68px; }
    .cabp { grid-template-columns: minmax(0, 1fr) 24px; }
    .cabp .nome { grid-column: 1 / -1; grid-row: 2; }
    .un-l { display: none; } .un-c { display: inline; }
    .fato { font-size: var(--fs-12); line-height: var(--lh-12); }
    th, td { padding-inline: var(--sp-1); }
  }
</style>
