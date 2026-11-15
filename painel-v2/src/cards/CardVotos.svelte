<script>
  import Card from '../lib/Card.svelte';
  import Kpi from '../lib/Kpi.svelte';
  import Grafico from '../lib/Grafico.svelte';
  import Filtros from '../lib/Filtros.svelte';
  import { SOLIDEZ, SOL_ROT, median, esc } from '../lib/dados.js';
  import { base, estiloPonto, rotNum, grade, dica, realce } from '../lib/tema.js';
  import { estado, lente } from '../lib/estado.svelte.js';

  let { papers } = $props();
  const t = $derived(estado.tema);
  const ORDEM = ['sem_leitura', 'fragil', 'basico', 'firme', 'forte'];
  const med = $derived(median(papers.map((p) => p.u)) || 1);
  const ruidosos = $derived(papers.filter((p) => (p.sol === 'fragil' || p.sol === 'basico') && p.u >= med).length);

  // limites redondos para o eixo log: 10, 20, 50, 100, 200, 500...
  const REDONDOS = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000];
  const lim = $derived.by(() => {
    const us = papers.map((p) => Math.max(1, +p.u));
    const lo = Math.min(...us, 1e9), hi = Math.max(...us, 1);
    return [[...REDONDOS].reverse().find((r) => r <= lo * 0.9) || 1, REDONDOS.find((r) => r >= hi * 1.1) || 10000];
  });
  const ativa = $derived(estado.lente?.k === 'sol' ? estado.lente.v : null);
  const opcao = $derived.by(() => {
    if (!t.ink || !papers.length) return null;
    return {
      ...base(t),
      grid: { left: 0, right: 46, top: 22, bottom: 4, containLabel: true },
      tooltip: { ...base(t).tooltip, trigger: 'item', formatter: (q) => {
        const p = papers.find((x) => x.id === q.data.pid);
        return dica(esc(p.t), `<b>${p.u}</b> votos`, `Solidez ${SOL_ROT[p.sol].toLowerCase()} · ${p.T} de ${p.nl} sinais lidos`);
      } },
      xAxis: { type: 'category', data: ORDEM.map((s) => SOL_ROT[s]), triggerEvent: true,
        jitter: 34, jitterOverlap: false, jitterMargin: 3,
        axisTick: { show: false }, axisLine: { lineStyle: { color: t.line } },
        axisLabel: { color: t.ink, fontSize: 12, fontFamily: t.body, fontWeight: 500, interval: 0, hideOverlap: false, margin: 12,
          formatter: (v) => (ativa && SOL_ROT[ativa] !== v ? `{off|${v}}` : v), rich: { off: { color: t.muted, fontSize: 12, fontFamily: t.body } } } },
      yAxis: { type: 'log', logBase: 10, min: lim[0], max: lim[1],
        name: 'votos', nameLocation: 'end', nameGap: 10, nameTextStyle: { ...rotNum(t), align: 'left', padding: [0, 0, 0, -24] },
        axisLabel: rotNum(t), splitLine: grade(t) },
      series: [{
        type: 'scatter', symbolSize: 13, cursor: 'pointer',
        emphasis: realce(t),
        data: papers.map((p) => ({ pid: p.id, value: [ORDEM.indexOf(p.sol), Math.max(1, p.u)], itemStyle: estiloPonto(t, p) })),
        markArea: { silent: true, itemStyle: { color: t.shade },
          label: { show: true, position: 'insideTop', distance: 6, color: t.warn, fontSize: 11, fontWeight: 500, formatter: 'muito voto, pouca prova' },
          data: [[{ xAxis: 'Frágil', yAxis: med }, { xAxis: 'Básica', yAxis: lim[1] }]] },
        markLine: { silent: true, symbol: 'none', data: [{ yAxis: med }], lineStyle: { color: t.muted, type: [2, 3], width: 1 },
          label: { show: true, position: 'end', formatter: 'mediana', color: t.muted, fontSize: 10, fontFamily: t.mono } },
      }],
    };
  });
  const clicar = (q) => {
    if (q.componentType === 'xAxis') { const i = ORDEM.findIndex((s) => SOL_ROT[s] === q.value); if (i >= 0) { lente('sol', ORDEM[i]); return true; } }
  };
</script>

<Card titulo="Onde há votos sem prova?" filtra="Clique num nível de solidez para filtrar o painel inteiro">
  {#snippet filtros()}<Filtros k="sol" rotulo="Filtrar por solidez" itens={ORDEM.map((s) => [s, SOL_ROT[s]])} />{/snippet}
  {#snippet kpi()}<Kpi valor={ruidosos} texto="papers com votos acima da mediana e prova frágil ou básica" />{/snippet}
  {#if opcao}<Grafico {opcao} altura={280} aoClicar={clicar} rotulo="Votos de cada paper por nível de solidez, em escala logarítmica" />
  {:else if !papers.length}<div class="vazio">Nenhum paper neste recorte.</div>{/if}
</Card>
