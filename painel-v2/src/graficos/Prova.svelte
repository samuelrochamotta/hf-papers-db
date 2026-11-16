<script>
  // Onde ha votos sem prova: cada paper e um ponto, por nivel de prova e por
  // votos. A zona marcada e a resposta; os papers dela aparecem pelo nome logo
  // abaixo, para abrir sem cacar ponto.
  import Quadro from '../pecas/Quadro.svelte';
  import Grafico from '../lib/Grafico.svelte';
  import Chave from '../pecas/Chave.svelte';
  import { SOL_ROT, SOL_FRASE, median, esc, curto } from '../lib/dados.js';
  import { base, estiloPonto, rotNum, rotCat, grade, dica, realce, limitesLog, curtoNum } from '../lib/tema.js';
  import { estado, lente, abrir } from '../lib/estado.svelte.js';

  let { papers } = $props();
  const t = $derived(estado.tema);
  const deitado = $derived(estado.v.g === 'b');
  const ordem = $derived(deitado ? ['forte', 'firme', 'basico', 'fragil', 'sem_leitura'] : ['fragil', 'basico', 'firme', 'forte', 'sem_leitura']);
  const med = $derived(median(papers.map((p) => p.u)) || 1);
  const naZona = (p) => (p.sol === 'fragil' || p.sol === 'basico') && p.u >= med;
  const zona = $derived(papers.filter(naZona).sort((a, b) => b.u - a.u));
  const ativa = $derived(estado.lente?.k === 'sol' ? estado.lente.v : null);

  // votos: escala linear enquanto o maior nao passa de dez vezes o menor
  const escala = $derived.by(() => {
    const us = papers.map((p) => Math.max(1, +p.u || 1));
    const lo = Math.min(...us), hi = Math.max(...us);
    if (hi / lo >= 10) return { log: true, lim: limitesLog(us) };
    const vao = hi - lo || hi, passo = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000].find((s) => vao / s <= 6) || 10000;
    return { log: false, lim: [Math.max(0, Math.floor((lo - vao * 0.05) / passo) * passo), Math.ceil((hi + vao * 0.05) / passo) * passo || passo] };
  });

  const opcao = $derived.by(() => {
    if (!t.ink || !papers.length) return null;
    const { log, lim } = escala;
    const cat = { type: 'category', data: ordem.map((s) => SOL_ROT[s]), triggerEvent: true, inverse: deitado,
      jitter: deitado ? 22 : 34, jitterOverlap: false, jitterMargin: 3,
      axisTick: { show: false }, axisLine: { lineStyle: { color: t.line } },
      axisLabel: { ...rotCat(t), interval: 0, hideOverlap: false, margin: 12,
        formatter: (v) => ((ativa && SOL_ROT[ativa] !== v) || v === SOL_ROT.sem_leitura ? `{off|${v}}` : v), rich: { off: { color: t.muted, fontSize: 12, fontFamily: t.fUi } } } };
    const val = { type: log ? 'log' : 'value', logBase: 10, min: lim[0], max: lim[1], axisLabel: { ...rotNum(t), formatter: curtoNum, hideOverlap: true }, splitLine: grade(t),
      ...(deitado ? { name: 'votos', nameLocation: 'middle', nameGap: 26, nameTextStyle: rotNum(t) } : {}) };
    // a zona cobre as faixas inteiras de fragil e basica, da mediana para cima
    const iz = [ordem.indexOf('fragil'), ordem.indexOf('basico')].sort((a, b) => a - b);
    const zonaSerie = { type: 'custom', silent: true, z: 1, tooltip: { show: false }, data: [deitado ? [med, iz[0]] : [iz[0], med]],
      renderItem: (_, api) => {
        const p1 = api.coord(deitado ? [med, iz[0]] : [iz[0], med]), p2 = api.coord(deitado ? [lim[1], iz[1]] : [iz[1], lim[1]]);
        const meia = Math.abs(api.size(deitado ? [0, 1] : [1, 0])[deitado ? 1 : 0]) / 2;
        let x = Math.min(p1[0], p2[0]), y = Math.min(p1[1], p2[1]), w = Math.abs(p2[0] - p1[0]), h = Math.abs(p2[1] - p1[1]);
        if (deitado) { y -= meia; h += 2 * meia; } else { x -= meia; w += 2 * meia; }
        return { type: 'group', children: [
          { type: 'rect', shape: { x, y, width: w, height: h, r: 4 }, style: { fill: t.alertSoft } },
          { type: 'text', x: deitado ? x + w - 8 : x, y: deitado ? y + 6 : y - 18, style: { text: 'muito voto, pouca prova', fill: t.alert, font: `500 12px ${t.fUi}`, align: deitado ? 'right' : 'left' } },
        ] };
      } };
    return {
      ...base(t),
      grid: deitado ? { left: 0, right: 16, top: 24, bottom: 32, containLabel: true } : { left: 0, right: 56, top: 44, bottom: 4, containLabel: true },
      graphic: deitado ? [] : [{ type: 'text', left: 0, top: 2, silent: true, style: { text: 'votos', fill: t.muted, font: `12px ${t.fNum}` } }],
      tooltip: { ...base(t).tooltip, trigger: 'item', formatter: (q) => {
        const p = papers.find((x) => x.id === q.data.pid); if (!p) return '';
        return dica(esc(p.t), `<b>${p.u.toLocaleString('pt-BR')}</b> votos`, `${SOL_FRASE[p.sol]}${p.nl ? ` · ${p.T} de ${p.nl} sinais lidos` : ''}`);
      } },
      xAxis: deitado ? val : cat, yAxis: deitado ? cat : val,
      series: [zonaSerie, {
        type: 'scatter', symbolSize: 13, cursor: 'pointer', emphasis: realce(t), z: 3,
        labelLayout: { hideOverlap: true },
        data: papers.map((p) => { const i = ordem.indexOf(p.sol), u = Math.max(1, p.u);
          return { pid: p.id, value: deitado ? [u, i] : [i, u], itemStyle: estiloPonto(t, p),
            label: { show: deitado && naZona(p), formatter: curto(p.t, 18), position: 'right', distance: 6, color: t.ink, fontSize: 12, fontFamily: t.fUi } }; }),
        markLine: { silent: true, symbol: 'none', data: [deitado ? { xAxis: med } : { yAxis: med }], lineStyle: { color: t.muted, type: [2, 3], width: 1 },
          label: { show: true, position: deitado ? 'start' : 'end', formatter: 'mediana', color: t.muted, fontSize: 12, fontFamily: t.fUi } },
      }],
    };
  });
  const clicar = (q) => {
    if (q.componentType !== (deitado ? 'yAxis' : 'xAxis')) return;
    const s = ordem.find((k) => SOL_ROT[k] === q.value);
    if (s) { lente('sol', s); return true; }
  };
</script>

<Quadro id="prova" pergunta="Onde há votos sem prova?" valor={zona.length} resposta={`${zona.length === 1 ? 'paper' : 'papers'} com votos acima da mediana e prova frágil ou básica`}>
  {#if opcao}<Grafico {opcao} altura={deitado ? 268 : 296} aoClicar={clicar} rotulo="Votos de cada paper por nível de prova" />
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
