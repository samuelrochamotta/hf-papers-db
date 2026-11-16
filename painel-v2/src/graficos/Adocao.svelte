<script>
  // O que da para adotar ja: os papers por degrau de esforco. Cada ponto e um
  // paper, na cor da prova; com papers demais, viram barras empilhadas. A
  // resposta conta so quem cumpre as tres condicoes da pergunta (dispensa
  // treino, liberou algo e tem prova firme ou forte) e aparece pelo nome.
  import Quadro from '../pecas/Quadro.svelte';
  import Grafico from '../lib/Grafico.svelte';
  import Nomes from '../pecas/Nomes.svelte';
  import Chave from '../pecas/Chave.svelte';
  import { ESFORCO, SOLIDEZ, SOL_ROT, SOL_FRASE, ART, ART_EST, FATO, esc, plural, liberados } from '../lib/dados.js';
  import { base, pontoProva, corSolidez, rotNum, rotCat, dica, larguraTexto } from '../lib/tema.js';
  import { estado, lente, lentesDe } from '../lib/estado.svelte.js';

  let { papers } = $props();
  const t = $derived(estado.tema);
  const NIVEIS = [1, 2, 3, 4, 5, 0];
  const RANK = Object.fromEntries(SOLIDEZ.map((s, i) => [s, i]));
  const ativas = $derived(lentesDe('esf'));
  const semTreino = $derived(papers.filter((p) => p.esf >= 1 && p.esf <= 2));
  const ja = $derived(semTreino.filter((p) => liberados(p) && (p.sol === 'forte' || p.sol === 'firme')).sort((a, b) => a.esf - b.esf || b.u - a.u));
  const resposta = $derived(!semTreino.length ? 'nenhum paper deste recorte dispensa treino'
    : `de ${plural(semTreino.length, 'paper que dispensa', 'papers que dispensam')} treino ${ja.length === 1 ? 'tem' : 'têm'} algo liberado e prova firme ou forte`);
  const conta = $derived(NIVEIS.map((n) => papers.filter((p) => p.esf === n).length));
  const jaIds = $derived(new Set(ja.map((p) => p.id)));
  const TITULO = 'dispensam treino';
  // sem espaco para um ponto por paper, a fila vira barra empilhada
  let larg = $state(480);
  const barras = $derived(Math.max(0, ...conta) * 9 > larg - 170);

  const opcao = $derived.by(() => {
    if (!t.ink) return null;
    const eixo = { type: 'category', inverse: true, axisTick: { show: false }, axisLine: { show: false } };
    const yAxis = [
      { ...eixo, data: NIVEIS.map((n) => ESFORCO[n]), triggerEvent: true, splitLine: { show: !barras, lineStyle: { color: t.line } },
        axisLabel: { ...rotCat(t), margin: 12, formatter: (v) => (ativas.length && !ativas.some((n) => ESFORCO[n] === v) ? `{off|${v}}` : v), rich: { off: { color: t.muted, fontSize: 12, fontFamily: t.fUi } } } },
      { ...eixo, position: 'right', data: conta.map(String), axisLabel: { ...rotNum(t), margin: 8 } },
    ];
    // a faixa dos degraus que dispensam treino: e nela que a resposta conta
    const fonteT = `500 12px ${t.fUi}`;
    const zona = { type: 'custom', silent: true, z: -1, tooltip: { show: false }, data: [[0, 0]],
      renderItem: (q, api) => {
        const a = q.coordSys, alt = Math.abs(api.size([0, 1])[1]), y0 = api.coord([0, 0])[1] - alt / 2;
        const wt = larguraTexto(TITULO, fonteT), livre = (i) => barras || 8 + conta[i] * 18 + 12 < a.width - wt - 8;
        const lin = [0, 1].find(livre);
        return { type: 'group', children: [
          { type: 'rect', shape: { x: a.x, y: y0 + 2, width: a.width, height: 2 * alt - 4, r: 4 }, style: { fill: t.sunk } },
          ...(lin == null || barras ? [] : [{ type: 'text', x: a.x + a.width - 8, y: y0 + lin * alt + alt / 2 - 7, style: { text: TITULO, fill: t.ink2, font: fonteT, align: 'right' } }]),
        ] };
      } };
    if (barras) return {
      ...base(t),
      grid: { left: 0, right: 4, top: 4, bottom: 4, containLabel: true },
      tooltip: { ...base(t).tooltip, trigger: 'axis', axisPointer: { type: 'shadow', shadowStyle: { color: t.sunk, opacity: .6 } },
        formatter: (qs) => { const i = qs[0].dataIndex, ps = papers.filter((p) => p.esf === NIVEIS[i]);
          return dica(ESFORCO[NIVEIS[i]], plural(ps.length, 'paper', 'papers'), ...SOLIDEZ.map((s) => { const n = ps.filter((p) => p.sol === s).length; return n ? `${SOL_FRASE[s]}: <b>${n}</b>` : ''; })); } },
      xAxis: { type: 'value', show: false, max: Math.max(1, ...conta) },
      yAxis,
      series: [...SOLIDEZ.map((s) => ({
        type: 'bar', stack: 'e', barWidth: 14, name: SOL_ROT[s], cursor: 'pointer', emphasis: { disabled: true },
        itemStyle: s === 'sem_leitura' ? { color: t.surface, borderColor: t.solNada, borderWidth: 1.5, borderType: 'dashed', borderRadius: 2 } : { color: corSolidez(t, s), borderColor: t.surface, borderWidth: 1, borderRadius: 2 },
        data: NIVEIS.map((n) => { const v = papers.filter((p) => p.esf === n && p.sol === s).length; return { value: v, esf: n, itemStyle: { opacity: v ? 1 : 0 } }; }),
      })), zona],
    };
    // pontos em fila, do mais provado ao menos; o passo encolhe quando a fila nao cabe
    const pos = new Map();
    // os que contam na resposta vem primeiro na fila e ganham um traco embaixo
    const fila = [...papers].sort((a, b) => jaIds.has(b.id) - jaIds.has(a.id) || RANK[a.sol] - RANK[b.sol] || b.u - a.u).map((p) => {
      const n = pos.get(p.esf) || 0; pos.set(p.esf, n + 1);
      return { p, n };
    });
    const maior = Math.max(1, ...conta);
    return {
      ...base(t),
      grid: { left: 0, right: 4, top: 4, bottom: 4, containLabel: true },
      tooltip: { ...base(t).tooltip, trigger: 'item', formatter: (q) => {
        const p = papers.find((x) => x.id === q.data.pid); if (!p) return '';
        const ab = Object.entries(p.ab).filter(([, v]) => v !== 'nao_lido' && v !== 'ausente').map(([k, v]) => `${ART[k]} ${ART_EST[v]}`).join(' · ');
        return dica(esc(p.t), `${ESFORCO[p.esf]} · ${SOL_FRASE[p.sol].toLowerCase()}`, ab);
      } },
      xAxis: { type: 'value', min: 0, max: 1, show: false },
      yAxis,
      series: [{
        type: 'custom', cursor: 'pointer',
        renderItem: (pa, api) => {
          const o = fila[pa.dataIndex]; if (!o) return null;
          const y = api.coord([0, api.value(1)])[1], larg = pa.coordSys.width - 16;
          const passo = Math.min(18, larg / maior), r = Math.max(2.5, Math.min(7, passo / 2 - 1));
          const els = pontoProva(t, o.p, pa.coordSys.x + 8 + o.n * passo, y, r, { cheio: r >= 5, extra: { emphasis: { style: { stroke: t.ink, lineWidth: 2 } } } });
          if (r < 5) els[0].style = { ...els[0].style, lineWidth: 0.75 };
          const x = pa.coordSys.x + 8 + o.n * passo;
          if (jaIds.has(o.p.id)) els.push({ type: 'line', silent: true, shape: { x1: x - passo / 2, y1: y + r + 4, x2: x + passo / 2, y2: y + r + 4 }, style: { stroke: t.ink, lineWidth: 2 } });
          return { type: 'group', children: els };
        },
        data: fila.map((o) => ({ pid: o.p.id, value: [0, NIVEIS.indexOf(o.p.esf)] })),
      }, zona],
    };
  });
  const clicar = (q) => {
    const n = q.componentType === 'yAxis' ? ESFORCO.indexOf(q.value) : q.data?.esf ?? -1;
    if (n >= 0 && (q.componentType === 'yAxis' || barras)) { lente('esf', n); return true; }
  };
</script>

<Quadro id="adocao" pergunta="O que dá para adotar já?" valor={ja.length} {resposta} vazio={!papers.length}>
  {#if opcao && papers.length}<div bind:clientWidth={larg}><Grafico {opcao} altura={228} aoClicar={clicar} rotulo="Papers por esforço de adoção, do menor ao maior, na cor da prova" /></div>
    <Nomes papers={ja} rotulo="Papers que dá para adotar já" valor={(p) => [liberados(p), FATO.ganho(p)].filter(Boolean).join(' · ')} />
  {:else}<div class="vazio">Nenhum paper neste recorte.</div>{/if}
  {#snippet legenda()}<div class="leg"><Chave />{#if ja.length && !barras}<span class="k"><i class="sub"></i>dá para adotar já</span>{/if}</div>{/snippet}
</Quadro>

<style>
  .leg { display: flex; flex-wrap: wrap; gap: var(--sp-2) var(--sp-5); font-size: var(--fs-12); line-height: var(--lh-12); color: var(--ink2); align-items: center; }
  .k { display: inline-flex; align-items: center; gap: 6px; }
  .sub { width: 16px; height: 2px; background: var(--ink); align-self: flex-end; margin-bottom: 3px; }
</style>
