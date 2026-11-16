<script>
  // Onde esta a disputa: resultados por arena, separados pelo desfecho contra
  // o melhor rival. Clicar numa arena aplica a lente.
  import Quadro from '../pecas/Quadro.svelte';
  import Grafico from '../lib/Grafico.svelte';
  import Nomes from '../pecas/Nomes.svelte';
  import { ARENA, plural, esc } from '../lib/dados.js';
  import { base, rotNum, grade, larguraTexto } from '../lib/tema.js';
  import { estado, lente, lentesDe } from '../lib/estado.svelte.js';

  let { papers } = $props();
  const t = $derived(estado.tema);
  const ESTADOS = [['ganha', 'Vence o rival'], ['ruido', 'Dentro do ruído'], ['perde', 'Perde'], ['sem_rival', 'Sem rival externo']];
  const nome = (k) => ARENA[k] || k;

  const linhas = $derived.by(() => {
    const m = new Map();
    for (const p of papers) for (const r of p.res) {
      if (!m.has(r.ar)) m.set(r.ar, { k: r.ar, ps: new Set(), n: 0, c: { ganha: 0, ruido: 0, perde: 0, sem_rival: 0 } });
      const o = m.get(r.ar);
      o.ps.add(p.id); o.n++;
      const e = r.e === 'empata' ? 'ruido' : r.e === 'sem_nosso' ? 'sem_rival' : r.e;
      o.c[e] = (o.c[e] || 0) + 1;
    }
    // a arena residual vai sempre por ultimo: "Outras" nao e uma disputa
    return [...m.values()].sort((a, b) => (a.k === 'outra') - (b.k === 'outra') || b.ps.size - a.ps.size || b.n - a.n);
  });
  const topo = $derived(linhas[0] || null);
  const empate = $derived(topo ? linhas.filter((l) => l.k !== 'outra' && l.ps.size === topo.ps.size).length : 0);
  // com um paper por arena nao ha disputa: a frase diz isso, em vez de eleger uma "arena mais cheia"
  const resposta = $derived(!topo ? 'nenhum resultado em tabela'
    : topo.ps.size === 1 ? (linhas.length > 1 ? 'paper por arena: nenhuma arena tem disputa neste recorte' : `paper em ${nome(topo.k)}, sem disputa neste recorte`)
    : empate > 1 ? `papers em cada uma das ${empate} arenas mais cheias`
    : `papers disputam ${nome(topo.k)}, a arena mais cheia`);
  const ativas = $derived(lentesDe('ar'));
  // "E quem vence nela?": na arena em foco (a do filtro, ou a mais cheia), os
  // papers que mais vencem o melhor rival, pela proporcao das disputas que
  // vencem ("3 de 3" antes de "5 de 15"); no empate, quem vence mais vezes.
  // Sem filtro de arena, so ha "quem vence" onde ha disputa (dois papers ou mais): com um paper por arena, o quadro nao elege vencedor
  const foco = $derived(ativas.length === 1 && linhas.some((l) => l.k === ativas[0]) ? ativas[0] : topo && topo.k !== 'outra' && topo.ps.size > 1 ? topo.k : null);
  const placar = $derived.by(() => {
    const m = new Map();
    if (foco) for (const p of papers) {
      const rs = p.res.filter((r) => r.ar === foco), v = rs.filter((r) => r.e === 'ganha').length;
      if (v) m.set(p.id, { p, v, n: rs.length, c: rs.filter((r) => r.e !== 'sem_rival' && r.e !== 'sem_nosso').length });
    }
    return m;
  });
  const taxa = (o) => o.v / Math.max(1, o.c);
  const vencem = $derived([...placar.values()].sort((a, b) => taxa(b) - taxa(a) || b.v - a.v || b.p.u - a.p.u).map((o) => o.p));

  // a barra conta resultados; a coluna da esquerda conta papers e a da direita diz o placar. So vence
  // quem tem rival: o resultado sem rival externo nao entra na conta
  let larg = $state(480);
  const estreito = $derived(larg < 420);
  const comRival = (l) => l.n - l.c.sem_rival;
  const placarDe = (l) => (comRival(l) ? `${l.c.ganha} de ${comRival(l)}` : 'sem rival');

  const opcao = $derived.by(() => {
    if (!t.ink) return null;
    const cor = { ganha: t.resGanha, ruido: t.resRuido, perde: t.resPerde, sem_rival: t.surface };
    const apaga = (k) => (ativas.length && !ativas.includes(k) ? 0.3 : 1);
    const wPlacar = Math.ceil(Math.max(larguraTexto('vencem', `12px ${t.fNum}`), ...linhas.map((l) => larguraTexto(placarDe(l), `12px ${t.fUi}`))));
    return {
      ...base(t),
      grid: { left: 0, right: 0, top: 22, bottom: 36, containLabel: true },
      tooltip: { ...base(t).tooltip, trigger: 'axis', axisPointer: { type: 'shadow', shadowStyle: { color: t.sunk, opacity: .6 } },
        formatter: (qs) => {
          const l = linhas[qs[0].dataIndex];
          const le = ESTADOS.filter(([e]) => l.c[e]).map(([e, r]) => `<span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:${cor[e]};box-shadow:inset 0 0 0 1px ${e === 'sem_rival' ? t.lineStrong : cor[e]};margin-right:6px"></span>${r}: <b>${l.c[e]}</b>`);
          return `<div style="font-weight:600">${esc(nome(l.k))}</div><div style="opacity:.8;margin-bottom:6px">${plural(l.ps.size, 'paper', 'papers')} · ${plural(l.n, 'resultado', 'resultados')}</div>${le.join('<br>')}`;
        } },
      xAxis: { type: 'value', minInterval: 1, splitNumber: estreito ? 3 : 5, splitLine: grade(t), axisLabel: { ...rotNum(t), hideOverlap: true },
        name: 'resultados em tabela', nameLocation: 'middle', nameGap: 26, nameTextStyle: rotNum(t) },
      yAxis: [{
        type: 'category', inverse: true, data: linhas.map((l) => nome(l.k)), triggerEvent: true,
        axisTick: { show: false }, axisLine: { show: false },
        // cabecalho da coluna de numeros: sao papers, e e por eles que as arenas estao ordenadas
        name: 'papers', nameLocation: 'start', nameGap: 8, nameTextStyle: { ...rotNum(t), align: 'right', padding: [0, 12, 0, 0] },
        axisLabel: { fontSize: 12, margin: 12,
          formatter: (v, i) => `{${ativas.length && !ativas.includes(linhas[i].k) ? 'off' : 'a'}|${v}}  {${ativas.length && !ativas.includes(linhas[i].k) ? 'noff' : 'n'}|${linhas[i].ps.size}}`,
          rich: { a: { color: t.ink, fontWeight: 500, fontFamily: t.fUi, fontSize: 12 }, off: { color: t.muted, fontFamily: t.fUi, fontSize: 12 },
            n: { color: t.ink, fontWeight: 600, fontFamily: t.fNum, fontSize: 12, width: 16, align: 'right' }, noff: { color: t.muted, fontFamily: t.fNum, fontSize: 12, width: 16, align: 'right' } } },
      }, {
        // o placar em coluna propria, fora da grade: nenhuma linha passa por cima dele
        type: 'category', inverse: true, position: 'right', data: linhas.map(placarDe), axisTick: { show: false }, axisLine: { show: false },
        name: 'vencem', nameLocation: 'start', nameGap: 8, nameTextStyle: { ...rotNum(t), align: 'left', padding: [0, 0, 0, 12 + wPlacar - larguraTexto('vencem', `12px ${t.fNum}`)] },
        axisLabel: { margin: 12, formatter: (v, i) => `{${v === 'sem rival' ? 'sr' : 'p'}|${v}}`,
          rich: { p: { color: t.ink2, fontFamily: t.fUi, fontSize: 12, width: wPlacar, align: 'right' }, sr: { color: t.muted, fontFamily: t.fUi, fontSize: 12, width: wPlacar, align: 'right' } } },
      }],
      series: ESTADOS.map(([e, rot]) => ({
        type: 'bar', name: rot, stack: 'r', barWidth: 14, cursor: 'pointer',
        itemStyle: { color: cor[e], borderRadius: 2, borderColor: e === 'sem_rival' ? t.lineStrong : t.surface, borderWidth: e === 'sem_rival' ? 1.5 : 1 },
        emphasis: { disabled: true },
        data: linhas.map((l) => ({ value: l.c[e] || 0, arena: l.k, itemStyle: { opacity: l.c[e] ? apaga(l.k) : 0 } })),
      })),
    };
  });
  const clicar = (q) => {
    const k = q.componentType === 'yAxis' ? linhas[q.dataIndex ?? linhas.findIndex((l) => q.value?.includes?.(nome(l.k)))]?.k : q.data?.arena;
    if (k) { lente('ar', k); return true; }
  };
</script>

<Quadro id="arenas" pergunta="Onde está a disputa?" valor={topo ? topo.ps.size : 0} {resposta} vazio={!linhas.length}>
  {#if opcao && linhas.length}
    <div class="cresce" bind:clientWidth={larg}><Grafico {opcao} altura={Math.max(176, linhas.length * 28 + 78)} aoClicar={clicar} rotulo="Resultados por arena, separados em vitória, ruído, derrota e sem rival externo" /></div>
  {:else}<div class="vazio">Nenhum resultado com benchmark neste recorte.</div>{/if}
  <Nomes papers={vencem} max={4} titulo="Mais vencem em {nome(foco)}" rotulo="Papers que mais vencem em {nome(foco)}" valor={(p) => `${placar.get(p.id).v} de ${placar.get(p.id).c}`} />
  {#snippet legenda()}
    <ul class="leg" aria-label="Desfecho contra o melhor rival">
      {#each ESTADOS as [e, rot]}<li><i class="sw {e}"></i>{rot}</li>{/each}
    </ul>
  {/snippet}
</Quadro>

<style>
  .leg { display: flex; flex-wrap: wrap; gap: var(--sp-1) var(--sp-3); font-size: var(--fs-12); line-height: var(--lh-12); color: var(--ink2); }
  .leg li { display: inline-flex; align-items: center; gap: 6px; }
  .sw { width: 10px; height: 10px; border-radius: 2px; background: var(--res-ganha); }
  .sw.ruido { background: var(--res-ruido); } .sw.perde { background: var(--res-perde); }
  .sw.sem_rival { background: transparent; box-shadow: inset 0 0 0 1.5px var(--line-strong); }
</style>
