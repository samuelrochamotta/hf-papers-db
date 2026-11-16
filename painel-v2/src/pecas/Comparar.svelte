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
  import { EIXOS, EIXO_DICA, FATO, SEM_FATO, ART, ART_EST, nBench, ganhoDe, median, nome, esc, radarValores, passaDoEixo, tetoDoEixo, faltaLer } from '../lib/dados.js';
  import { base, dica, corCmp, marcasRadar } from '../lib/tema.js';
  import { estado, alternaComparar, abrir, MAX_COMPARAR } from '../lib/estado.svelte.js';

  // `periodo`: todos os papers do periodo, sem filtro: a mediana e sempre a do periodo
  let { papers, todos, periodo = papers } = $props();
  let larg = $state(600);
  const t = $derived(estado.tema);
  const porId = $derived(new Map(todos.map((p) => [p.id, p])));
  const sel = $derived(estado.comparar.map((id) => porId.get(id)).filter(Boolean));
  const medBruta = $derived(EIXOS.map(([k]) => median(periodo.map((p) => p.radar[k]))));
  const opcoes = $derived(todos.filter((p) => !estado.comparar.includes(p.id)).sort((a, b) => b.u - a.u));
  const noRecorte = $derived(new Set(papers.map((p) => p.id)));
  // O numero que decide o negrito: o valor real em ganho e amplitude, a nota
  // do radar nos outros eixos. Com todos empatados, ninguem leva a linha.
  const medida = (k, p) => (k === 'ganho' ? ganhoDe(p) : k === 'amplitude' ? nBench(p) : p.radar[k]);
  const melhor = $derived(EIXOS.map(([k]) => {
    const vs = sel.map((p) => medida(k, p)).filter((x) => x != null), m = Math.max(...vs);
    return vs.length > 1 && vs.some((x) => x < m) ? m : null;
  }));
  // Posicao na barra, de 0 a 100: a mesma nota do radar ao lado, para a barra e
  // o vertice dizerem a mesma coisa (o ganho tem 50 no zero; a amplitude e a
  // escala logaritmica fixa). Os votos vao ate o mais votado do periodo.
  const maxVotos = $derived(Math.max(1, ...todos.map((p) => p.u)));
  const pos = (k, p) => (k === 'atencao' ? (100 * p.u) / maxVotos : p.radar[k]);
  const medPos = $derived(EIXOS.map(([k]) => median(periodo.map((p) => pos(k, p)))));
  const artefatos = (p) => Object.keys(ART).map((a) => `${ART[a]} ${ART_EST[p.ab[a]] ?? 'não lido'}`).join(' · ');
  const TRACO = ['solid', [6, 3], [2, 3]], MARCA = ['circle', 'rect', 'triangle'];
  // as linhas da tabela seguem a ordem das colunas da lista de papers: votos, prova, ganho, adocao, abertura, amplitude
  const LINHAS = ['atencao', 'solidez', 'ganho', 'facilidade', 'abertura', 'amplitude'].map((k) => EIXOS.findIndex(([e]) => e === k));
  // o radar ocupa o que a largura deixa (os nomes dos eixos pedem uns 75 px de cada lado) e a altura acompanha: sem vao em cima nem embaixo
  const raio = $derived(Math.round(Math.max(60, Math.min((larg - 150) / 2, 165))));

  // avisos que ficam no proprio desenho: quem passa do teto da amplitude e a faixa da abertura, do confirmado ao maximo possivel
  const cortes = $derived(sel.map((p) => EIXOS.map(([k]) => passaDoEixo(k, p))));
  const faixas = $derived(sel.map((p) => EIXOS.map(([k]) => tetoDoEixo(k, p))));
  const temCorte = $derived(cortes.some((c) => c.some(Boolean))), temFaixa = $derived(faixas.some((c) => c.some((x) => x != null)));

  const opcao = $derived(!t.ink || !sel.length ? null : {
    ...base(t),
    tooltip: { ...base(t).tooltip, trigger: 'item', formatter: (q) => {
      if (q.data.mediana) return dica('Mediana do período', ...EIXOS.map(([, r], i) => `${r}: <b>${medBruta[i] == null ? '–' : Math.round(medBruta[i])}</b>`));
      const p = porId.get(q.data.pid);
      return dica(`${q.data.letra} · ${esc(p.t)}`, ...EIXOS.map(([k, r]) => `${r}: <b>${FATO[k](p) ?? SEM_FATO[k](p)}</b>`));
    } },
    radar: {
      indicator: EIXOS.map(([, r]) => ({ name: r, max: 100 })), radius: raio, center: ['50%', '50%'], splitNumber: 4, shape: 'polygon', axisNameGap: 20,
      axisName: { color: t.ink2, fontSize: 12, fontWeight: 500, fontFamily: t.fUi },
      splitLine: { lineStyle: { color: t.line } }, splitArea: { show: false }, axisLine: { lineStyle: { color: t.line } },
    },
    graphic: marcasRadar(t, { cx: larg / 2, cy: raio + 36, r: raio, itens: sel.map((p, i) => ({ valores: radarValores(EIXOS.map(([k]) => p.radar[k])), cor: corCmp(t, i), simbolo: MARCA[i], faixas: faixas[i], cortes: cortes[i] })) }),
    series: [{ type: 'radar', data: [
      { name: 'Mediana', mediana: true, value: radarValores(medBruta), symbol: 'none', lineStyle: { color: t.muted, type: [4, 4], width: 1 }, areaStyle: { color: t.lineStrong, opacity: .1 } },
      ...sel.map((p, i) => { const c = corCmp(t, i);
        return { name: p.t, pid: p.id, letra: 'ABC'[i], value: radarValores(EIXOS.map(([k]) => p.radar[k])),
          // com eixo nao lido o vertice e so passagem: sem marcador, para nao parecer medida
          symbol: EIXOS.some(([k]) => p.radar[k] == null) ? 'none' : MARCA[i], symbolSize: 7,
          itemStyle: { color: c }, // so a mediana tem area: tres poligonos cheios, um sobre o outro, viram uma mancha
          lineStyle: { color: c, width: 2, type: TRACO[i] }, areaStyle: { color: c, opacity: 0 },
          emphasis: { areaStyle: { opacity: 0.16 }, lineStyle: { width: 3 } } }; }),
    ] }],
  });

  const comProva = $derived([...papers].sort((a, b) => b.u - a.u).filter((p) => p.sol !== 'sem_leitura' && Object.values(p.radar).filter((v) => v != null).length >= 4));
  const maisVotados = () => { estado.comparar = comProva.slice(0, 2).map((p) => p.id); };
  const v = (x) => (x == null ? null : Math.round(x));
  // no cabecalho estreito o nome quebra entre palavras, nunca no hifen ("Harness-" / "S")
  const semQuebra = (s) => s.replace(/-/g, '\u2011');
  // os estados dos artefatos que aparecem nesta comparacao: a legenda so explica o que esta na tela
  const estadosAb = $derived(new Set(sel.flatMap((p) => Object.keys(ART).map((a) => p.ab[a] ?? 'nao_lido'))));
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
      {#if comProva.length > 1}<button class="btn sec" onclick={maisVotados}>Comparar os dois lidos mais votados</button>{/if}
    </div>
  {:else}
    <div class="corpo">
      <div class="t">
        <table>
          <thead><tr>
            <th scope="col" class="eixo"><span class="vh">Eixo</span></th>
            {#each sel as p, i (p.id)}
              <th scope="col" style:--c="var(--cmp-{i + 1})">
                <span class="cabp">
                  <i class="letra" aria-hidden="true">{'ABC'[i]}</i>
                  <button class="nome" onclick={() => abrir(p.id)} title={p.t} onmouseenter={() => (estado.hover = p.id)} onmouseleave={() => (estado.hover = null)}>
                    <span class="vh">{'ABC'[i]}: </span><span class="nm" class:fora={!noRecorte.has(p.id)}>{semQuebra(nome(p))}</span></button>
                  <button class="tira" aria-label="Tirar {p.t} da comparação" title="Tirar da comparação" onclick={() => alternaComparar(p.id)}><Icone nome="x" tam={14} /></button>
                </span>
              </th>
            {/each}
          </tr></thead>
          <tbody>
            {#each LINHAS as ei}
              {@const [k, r] = EIXOS[ei]}
              {@const med = v(medPos[ei])}
              <tr>
                <th scope="row" class="eixo" title={EIXO_DICA[k]}>{r}</th>
                {#each sel as p, i (p.id)}
                  {@const x = v(pos(k, p))}
                  {@const f = FATO[k](p)}
                  <td style:--c="var(--cmp-{i + 1})" class:top={melhor[ei] != null && medida(k, p) === melhor[ei]} class:neg={k === 'ganho' && ganhoDe(p) < 0}>
                    <span class="fato" class:mut={f == null}>{#if k === 'amplitude' && f != null}{nBench(p)} <span class="un-l">{nBench(p) === 1 ? 'benchmark' : 'benchmarks'}</span><span class="un-c">bench.</span>{:else}{f ?? SEM_FATO[k](p)}{/if}{#if k === 'abertura' && faltaLer(p)}<span class="nl"><span class="sep">{' · '}</span>{faltaLer(p)}</span>{/if}{#if k === 'solidez' && f != null && p.nl}<span class="nl"><span class="sep">{' · '}</span>{p.T} de {p.nl} sinais</span>{/if}</span>
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
          <span><i class="tique"></i>mediana do período</span>
          <span><i class="zero"></i>ganho zero</span>
          {#if sel.length > 1}<span><b>negrito</b>melhor da linha</span>{/if}
          <span class="ab-k">abertura: código, pesos, dados e demo, nesta ordem</span>
          {#if estadosAb.has('liberado')}<span><span class="pecas ex um" aria-hidden="true"><i class="liberado"></i></span>liberado</span>{/if}
          {#if estadosAb.has('prometido') || estadosAb.has('so_pagina')}<span><span class="pecas ex um" aria-hidden="true"><i class="prometido"></i></span>prometido ou só a página</span>{/if}
          {#if estadosAb.has('ausente')}<span><span class="pecas ex um" aria-hidden="true"><i class="ausente"></i></span>não liberado</span>{/if}
          {#if estadosAb.has('nao_lido')}<span><span class="pecas ex um" aria-hidden="true"><i class="nao_lido"></i></span>não lido</span>{/if}
        </p>
      </div>

      <div class="g" bind:clientWidth={larg}>
        {#if opcao}<Grafico {opcao} altura={2 * raio + 72} rotulo="Radar de seis eixos com os papers escolhidos e a mediana do período" />{/if}
        <p class="chave t-12 mut">
          {#each sel as p, i (p.id)}<span><svg width="26" height="10" aria-hidden="true"><line x1="1" y1="5" x2="25" y2="5" stroke="var(--cmp-{i + 1})" stroke-width="2" stroke-dasharray={i === 1 ? '6 3' : i === 2 ? '2 3' : null} /></svg><b>{'ABC'[i]}</b>{nome(p)}</span>{/each}
          <span><i class="med"></i>mediana do período</span>
          <span>anéis em 50 e 100, a nota de cada eixo</span>
          {#if temFaixa}<span><i class="fx"></i>até onde a parte não lida pode levar</span>{/if}
          {#if temCorte}<span><b aria-hidden="true">»</b>passa do eixo</span>{/if}
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
  /* a tabela e o que responde: vem primeiro. Em tela larga o radar fica a esquerda dela */
  @container (min-width: 860px) { .corpo { grid-template-columns: minmax(300px, 5fr) minmax(0, 7fr); gap: var(--sp-8); padding: var(--sp-6); align-items: center; } .g { order: -1; } }
  .g { min-width: 0; }
  .chave { display: flex; flex-wrap: wrap; gap: var(--sp-1) var(--sp-4); justify-content: center; margin-top: var(--sp-2); }
  .chave span { display: inline-flex; align-items: center; gap: 6px; min-width: 0; }
  .chave b { font-weight: 600; color: var(--ink); }
  .chave.pe { justify-content: flex-start; margin-top: var(--sp-4); padding-top: var(--sp-3); border-top: 1px solid var(--line); --c: var(--ink2); }
  .chave .med { width: 16px; height: 10px; border-radius: 2px; border: 1px dashed var(--muted); background: color-mix(in srgb, var(--line-strong) 12%, var(--surface)); }
  .chave .tique { width: 2px; height: 12px; border-radius: 1px; background: var(--ink2); }
  .chave .zero { width: 0; height: 12px; border-left: 1px dotted var(--ink2); }
  .chave .fx { display: inline-block; width: 14px; height: 6px; background: color-mix(in srgb, var(--ink2) 30%, transparent); border-right: 2px solid var(--ink2); }
  .nl { color: var(--muted); font-weight: 400; }
  td.neg .fato { color: var(--alert); }

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
  .trilho em { position: absolute; left: 50%; top: -4px; bottom: -4px; width: 0; border-left: 1px dotted var(--ink2); }
  .trilho b { position: absolute; top: -3px; bottom: -3px; width: 2px; margin-left: -1px; background: var(--ink2); border-radius: 1px; }
  /* abertura: um segmento por artefato (codigo, pesos, dados, demo), no estado em que a leitura o achou */
  .pecas { display: flex; gap: 3px; margin-top: var(--sp-2); }
  .pecas i { flex: 1; height: 6px; border-radius: 3px; background: var(--sunk); }
  .pecas .liberado { background: var(--c); }
  .pecas .prometido, .pecas .so_pagina { background: none; box-shadow: inset 0 0 0 1.5px var(--c); }
  /* nao lido: contorno tracejado, como a marca de prova nao lida, numa posicao que se conta; ausente fica cheio e neutro */
  .pecas .nao_lido { background: none; border: 1px dashed var(--sol-nada); }
  .pecas.ex { width: 56px; margin-top: 0; flex: none; }
  .pecas.ex.um { width: 18px; }
  .chave .ab-k { flex-basis: 100%; margin-top: var(--sp-1); }

  @container (max-width: 520px) {
    .eixo { width: 68px; }
    /* cada coluna vira uma caixa: a letra, o nome e o botao de tirar ficam juntos, sem parecer "A × B × C ×" */
    .cabp { grid-template-columns: minmax(0, 1fr) 28px; background: var(--sunk); border-radius: var(--r-2); padding: 6px var(--sp-1) var(--sp-1) 6px; }
    thead th { padding-inline: 2px; }      /* a caixa do nome usa a coluna quase inteira: um nome como "Harness-S" cabe sem partir */      /* a linha de 8 px entre o botao de tirar e o nome e o que separa os dois alvos de toque */
    .cabp .nome { grid-column: 1 / -1; grid-row: 2; }
    .tira { margin: -2px -2px 0 0; }
    .un-l { display: none; } .un-c { display: inline; }
    .nl { display: block; } .nl .sep { display: none; }      /* estreito: a parte nao lida desce para a linha de baixo, nao some */
    .nome .nm { -webkit-line-clamp: 3; }
    .fato { font-size: var(--fs-12); line-height: var(--lh-12); }
    th, td { padding-inline: var(--sp-1); }
  }
</style>
