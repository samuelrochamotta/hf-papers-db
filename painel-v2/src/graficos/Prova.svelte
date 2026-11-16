<script>
  // Onde ha votos sem prova: cada paper e um ponto na linha do seu nivel de
  // prova, na posicao dos seus votos. Pontos que se tocariam se afastam dentro
  // da linha, para nenhum esconder outro, e cada linha diz quantos papers tem.
  // A zona marcada e a resposta; os papers dela aparecem pelo nome logo
  // abaixo, para abrir sem cacar ponto.
  import Quadro from '../pecas/Quadro.svelte';
  import Grafico from '../lib/Grafico.svelte';
  import Chave from '../pecas/Chave.svelte';
  import { SOLIDEZ, SOL_ROT, SOL_FRASE, median, esc, curto } from '../lib/dados.js';
  import { base, marca, enxame, rotNum, rotCat, grade, dica, limitesLog, curtoNum } from '../lib/tema.js';
  import { estado, lente, lentesDe, abrir } from '../lib/estado.svelte.js';

  let { papers } = $props();
  const t = $derived(estado.tema);
  const R = 6.5, TITULO = 'muito voto, pouca prova';
  const med = $derived(median(papers.map((p) => p.u)) || 1);
  const naZona = (p) => (p.sol === 'fragil' || p.sol === 'basico') && p.u >= med;
  const zona = $derived(papers.filter(naZona).sort((a, b) => b.u - a.u));
  const conta = $derived(Object.fromEntries(SOLIDEZ.map((s) => [s, papers.filter((p) => p.sol === s).length])));
  const ativas = $derived(lentesDe('sol'));

  // votos: escala linear enquanto o maior nao passa de dez vezes o menor
  const escala = $derived.by(() => {
    const us = papers.map((p) => Math.max(1, +p.u || 1));
    const lo = Math.min(...us), hi = Math.max(...us);
    if (hi / lo >= 10) return { log: true, lim: limitesLog(us) };
    const vao = hi - lo || hi, passo = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000].find((s) => vao / s <= 6) || 10000;
    return { log: false, lim: [Math.max(0, Math.floor((lo - vao * 0.05) / passo) * passo), Math.ceil((hi + vao * 0.05) / passo) * passo || passo] };
  });

  let tela;
  const largura = (txt, fonte) => { tela ||= document.createElement('canvas').getContext('2d'); tela.font = fonte; return tela.measureText(txt).width; };
  const toca = (a, b) => a[0] < b[0] + b[2] && b[0] < a[0] + a[2] && a[1] < b[1] + b[3] && b[1] < a[1] + a[3];

  const opcao = $derived.by(() => {
    if (!t.ink || !papers.length) return null;
    const { log, lim } = escala, fonte = `12px ${t.fUi}`, fonteT = `500 12px ${t.fUi}`;
    const linha = (p) => SOLIDEZ.indexOf(p.sol), votos = (p) => Math.max(1, p.u);
    const iz = [SOLIDEZ.indexOf('basico'), SOLIDEZ.indexOf('fragil')];

    // Uma passada por desenho: posicao de cada ponto, a caixa da zona e os
    // nomes que cabem. O nome so entra onde nao encobre ponto, titulo nem outro nome.
    let arranjo = null;
    function arranjar(api) {
      const faixa = Math.abs(api.size([0, 1])[1]);
      const pts = papers.map((p) => { const c = api.coord([votos(p), linha(p)]); return { x: c[0], y: c[1] }; });
      const dy = enxame(pts, faixa, R), pos = pts.map((q, i) => [q.x, q.y + dy[i]]);
      const a = api.coord([med, iz[0]]), b = api.coord([lim[1], iz[1]]);
      const z = [a[0], a[1] - faixa / 2, b[0] - a[0], b[1] - a[1] + faixa];
      const bolas = pos.map(([x, y]) => [x - R, y - R, 2 * R, 2 * R]);
      const wt = largura(TITULO, fonteT);
      const tit = [[z[0] + z[2] - 8 - wt, z[1] + 5, wt, 14], [z[0] + z[2] - 8 - wt, z[1] + z[3] - 19, wt, 14]]
        .find((c) => c[0] > z[0] + 4 && !bolas.some((o) => toca(c, o))) || null;
      const caixas = tit ? [tit] : [], rot = papers.map(() => null);
      const fila = papers.map((_, i) => i).filter((i) => naZona(papers[i])).sort((i, j) => papers[j].u - papers[i].u);
      for (const i of fila) {
        const txt = curto(papers[i].t, 18), w = largura(txt, fonte), [x, y] = pos[i];
        for (const lado of ['right', 'left']) {
          const c = [lado === 'right' ? x + R + 5 : x - R - 5 - w, y - 7, w, 14];
          if (c[0] < z[0] + 4 || c[0] + w > z[0] + z[2] + 12) continue;      // o nome fica dentro da zona
          if (bolas.some((o, j) => j !== i && toca(c, o)) || caixas.some((o) => toca(c, o))) continue;
          caixas.push(c); rot[i] = { txt, lado }; break;
        }
      }
      return { pos, z, tit, rot };
    }
    const pronto = (q, api) => (arranjo = q.dataIndexInside === 0 || !arranjo ? arranjar(api) : arranjo);

    return {
      ...base(t),
      grid: { left: 0, right: 16, top: 24, bottom: 32, containLabel: true },
      tooltip: { ...base(t).tooltip, trigger: 'item', formatter: (q) => {
        const p = papers.find((x) => x.id === q.data?.pid); if (!p) return '';
        return dica(esc(p.t), `<b>${p.u.toLocaleString('pt-BR')}</b> votos`, `${SOL_FRASE[p.sol]}${p.nl ? ` · ${p.T} de ${p.nl} sinais lidos` : ''}`);
      } },
      xAxis: { type: log ? 'log' : 'value', logBase: 10, min: lim[0], max: lim[1], axisLabel: { ...rotNum(t), formatter: curtoNum, hideOverlap: true }, splitLine: grade(t),
        name: 'votos', nameLocation: 'middle', nameGap: 26, nameTextStyle: rotNum(t) },
      yAxis: { type: 'category', data: SOLIDEZ, inverse: true, triggerEvent: true, axisTick: { show: false }, axisLine: { lineStyle: { color: t.line } },
        axisLabel: { ...rotCat(t), interval: 0, hideOverlap: false, margin: 12,
          formatter: (k) => `{${(ativas.length && !ativas.includes(k)) || !conta[k] || k === 'sem_leitura' ? 'off' : 'on'}|${SOL_ROT[k]}}{n|${conta[k]}}`,
          rich: { on: { color: t.ink, fontSize: 12, fontWeight: 500, fontFamily: t.fUi }, off: { color: t.muted, fontSize: 12, fontFamily: t.fUi },
            n: { color: t.muted, fontSize: 12, fontFamily: t.fNum, width: 22, align: 'right' } } } },
      series: [
        { type: 'custom', silent: true, z: 1, tooltip: { show: false }, data: [[med, iz[0]]],
          renderItem: (q, api) => { arranjo = arranjar(api); const { z, tit } = arranjo;
            return { type: 'group', children: [
              { type: 'rect', shape: { x: z[0], y: z[1], width: z[2], height: z[3], r: 4 }, style: { fill: t.alertSoft } },
              ...(tit ? [{ type: 'text', x: tit[0], y: tit[1], style: { text: TITULO, fill: t.alert, font: fonteT } }] : []),
            ] }; },
          markLine: { silent: true, symbol: 'none', data: [{ xAxis: med }], lineStyle: { color: t.muted, type: [2, 3], width: 1 },
            label: { show: true, position: 'start', formatter: `mediana ${med.toLocaleString('pt-BR', { maximumFractionDigits: 1 })}`, color: t.muted, fontSize: 12, fontFamily: t.fUi } } },
        { type: 'custom', z: 3, encode: { x: 0, y: 1 }, data: papers.map((p) => ({ pid: p.id, value: [votos(p), linha(p)] })),
          renderItem: (q, api) => {
            const { pos, rot } = pronto(q, api), i = q.dataIndex, r = rot[i];
            return { type: 'circle', shape: { cx: pos[i][0], cy: pos[i][1], r: R }, style: marca(t, papers[i]), cursor: 'pointer',
              emphasis: { style: { stroke: t.ink, lineWidth: 2, lineDash: null } },
              ...(r ? { textContent: { type: 'text', style: { text: r.txt, fill: t.ink, font: fonte } }, textConfig: { position: r.lado, distance: 5 } } : {}) };
          } },
      ],
    };
  });
  const clicar = (q) => {
    if (q.componentType !== 'yAxis') return;
    if (conta[q.value]) { lente('sol', q.value); return true; }
  };
</script>

<Quadro id="prova" pergunta="Onde há votos sem prova?" valor={zona.length} resposta={`${zona.length === 1 ? 'paper' : 'papers'} com votos acima da mediana e prova frágil ou básica`}>
  {#if opcao}<Grafico {opcao} altura={300} aoClicar={clicar} rotulo="Votos de cada paper por nível de prova" />
  {:else}<div class="vazio">Nenhum paper neste recorte.</div>{/if}
  {#if zona.length}
    <ul class="zona" aria-label="Papers com muito voto e pouca prova">
      {#each zona.slice(0, 8) as p (p.id)}
        <li><button onclick={() => abrir(p.id)} onmouseenter={() => (estado.hover = p.id)} onmouseleave={() => (estado.hover = null)}>
          <i class="sol {p.sol}"></i><span class="um">{curto(p.t, 26)}</span><span class="num mut">{p.u.toLocaleString('pt-BR')}</span></button></li>
      {/each}
      {#if zona.length > 8}<li class="mut resto">e mais {zona.length - 8}</li>{/if}
    </ul>
  {/if}
  {#snippet legenda()}<Chave />{/snippet}
</Quadro>

<style>
  .zona { display: flex; flex-wrap: wrap; gap: var(--sp-2); margin-top: var(--sp-3); }
  .zona button { display: inline-flex; align-items: center; gap: 6px; min-height: calc(var(--ctl) - 4px); padding: 0 var(--sp-3) 0 var(--sp-2); border-radius: 999px; background: var(--alert-soft); font-size: var(--fs-12); line-height: var(--lh-12); font-weight: 500; max-width: 100%;
    transition: box-shadow var(--dur-1); }
  .zona button:hover { box-shadow: inset 0 0 0 1px var(--alert); }
  .zona .mut { font-weight: 400; color: var(--ink2); }
  .resto { align-self: center; font-size: var(--fs-12); }
</style>
