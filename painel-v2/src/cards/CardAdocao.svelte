<script>
  import Card from '../lib/Card.svelte';
  import Kpi from '../lib/Kpi.svelte';
  import Grafico from '../lib/Grafico.svelte';
  import Filtros from '../lib/Filtros.svelte';
  import { ESFORCO, SOL_ROT, ART, ART_EST, esc } from '../lib/dados.js';
  import { base, estiloPonto, dica, realce } from '../lib/tema.js';
  import { estado, lente } from '../lib/estado.svelte.js';

  let { papers } = $props();
  const t = $derived(estado.tema);
  const NIVEIS = [1, 2, 3, 4, 5, 0];
  const ativa = $derived(estado.lente?.k === 'esf' ? estado.lente.v : null);
  const prontos = $derived(papers.filter((p) => p.esf >= 1 && p.esf <= 2).length);

  const opcao = $derived.by(() => {
    if (!t.ink) return null;
    const pos = new Map();
    const dados = [...papers].sort((a, b) => b.u - a.u).map((p) => {
      const n = pos.get(p.esf) || 0; pos.set(p.esf, n + 1);
      return { pid: p.id, value: [n, NIVEIS.indexOf(p.esf)], itemStyle: estiloPonto(t, p) };
    });
    const maxN = Math.max(6, ...pos.values());
    return {
      ...base(t),
      grid: { left: 0, right: 8, top: 4, bottom: 4, containLabel: true },
      tooltip: { ...base(t).tooltip, trigger: 'item', formatter: (q) => {
        const p = papers.find((x) => x.id === q.data.pid);
        const ab = Object.entries(p.ab).map(([k, v]) => `${ART[k]} ${ART_EST[v]}`).join(' · ');
        return dica(esc(p.t), `${ESFORCO[p.esf]} · solidez ${SOL_ROT[p.sol].toLowerCase()}`, ab);
      } },
      xAxis: { type: 'value', min: -0.6, max: maxN - 0.4, show: false },
      yAxis: { type: 'category', inverse: true, data: NIVEIS.map((n) => ESFORCO[n]), triggerEvent: true,
        axisTick: { show: false }, axisLine: { show: false }, splitLine: { show: true, lineStyle: { color: t.line } },
        axisLabel: { color: t.ink, fontSize: 12, fontFamily: t.body, fontWeight: 500, margin: 12,
          formatter: (v) => (ativa != null && ESFORCO[ativa] !== v ? `{off|${v}}` : v), rich: { off: { color: t.muted, fontSize: 12, fontFamily: t.body } } } },
      series: [{ type: 'scatter', symbolSize: 15, cursor: 'pointer', emphasis: realce(t), data: dados }],
    };
  });
  const clicar = (q) => {
    if (q.componentType === 'yAxis') { const i = ESFORCO.indexOf(q.value); if (i >= 0) { lente('esf', i); return true; } }
  };
</script>

<Card titulo="O que dá para adotar já?" filtra="Clique num degrau de esforço para filtrar o painel inteiro">
  {#snippet filtros()}<Filtros k="esf" rotulo="Filtrar por esforço" itens={NIVEIS.map((n) => [n, ESFORCO[n]])} />{/snippet}
  {#snippet kpi()}<Kpi valor={prontos} texto="papers dispensam treino: basta configurar ou integrar" />{/snippet}
  {#if opcao}<Grafico {opcao} altura={240} aoClicar={clicar} rotulo="Papers por esforço de adoção" />{/if}
</Card>
