<script>
  // O que melhora gastando menos: custo relativo ao rival contra o ganho. A
  // zona marcada e a resposta: os papers dela tem nome no desenho e aparecem
  // logo abaixo, para abrir sem cacar ponto. Nome de ponto de fora nunca entra
  // na zona nem cruza as linhas de custo igual e de ganho zero.
  import Quadro from '../pecas/Quadro.svelte';
  import Grafico from '../lib/Grafico.svelte';
  import Nomes from '../pecas/Nomes.svelte';
  import Chave from '../pecas/Chave.svelte';
  import { median, curto, sgn, esc, plural, SOL_FRASE } from '../lib/dados.js';
  import { base, pontoProva, rotNum, grade, dica, dominio, pct, rotular, toca, larguraTexto } from '../lib/tema.js';
  import { estado } from '../lib/estado.svelte.js';

  let { papers } = $props();
  const t = $derived(estado.tema);
  const cheio = $derived(estado.v.marca === 'cheio');
  const TITULO = 'mais barato e melhor';
  const fator = (e) => {
    const v = +e.valor; if (!v) return null;
    if (e.forma === 'percentual') return e.sentido === 'menos' ? 1 - v / 100 : 1 + v / 100;
    if (e.sentido === 'mais') return v;
    return v < 1 ? v : 1 / v;
  };
  const pontos = $derived(papers.map((p) => {
    const e = p.ef.find((x) => /computacao|latencia|memoria/.test(x.recurso)) || p.ef[0];
    if (!e) return null;
    const f = fator(e); if (!f || f <= 0) return null;
    const rx = p.res.map((r) => r.rext).filter((v) => v != null), rw = p.res.map((r) => r.rwk).filter((v) => v != null);
    return { p, f, g: rx.length ? median(rx) : rw.length ? median(rw) : 0 };
  }).filter(Boolean));
  const bom = (o) => o.f < 1 && o.g >= 0;
  const bons = $derived(pontos.filter(bom).sort((a, b) => b.g - a.g || a.f - b.f));
  const porId = $derived(new Map(pontos.map((o) => [o.p.id, o])));
  // o custo em palavras, igual no eixo, na dica e nos nomes: "31× menor", "1,2× maior"
  const n = (v) => v.toLocaleString('pt-BR', { maximumFractionDigits: v < 10 ? 1 : 0 });
  const vezes = (f) => (Math.abs(f - 1) < 0.005 ? 'igual' : f < 1 ? `${n(1 / f)}× menor` : `${n(f)}× maior`);

  const opcao = $derived.by(() => {
    if (!t.ink || !pontos.length) return null;
    // eixo em dobras (metade, igual, dobro): custo igual fica a vista e quem custa 1,2x nao encosta na linha
    const lx = (f) => Math.log2(f), ls = pontos.map((o) => lx(o.f));
    const lo = Math.min(-1, Math.floor(Math.min(...ls))), hi = Math.max(1, Math.ceil(Math.max(...ls)));
    const px = Math.max(1, Math.ceil((hi - lo) / 4)), x0 = -Math.ceil(-lo / px) * px, x1 = Math.ceil(hi / px) * px;
    const [y0, y1, passo] = dominio(pontos.map((o) => o.g), { inclui: [-10, 10] });
    const cl = (g) => Math.max(y0, Math.min(y1, g)), fora = (o) => o.g > y1 || o.g < y0;
    // marcas curtas, para caberem todas no celular: ÷16 e o custo dividido por 16
    const marcaX = (v) => (v === 0 ? 'igual' : `${v < 0 ? '÷' : '×'}${(2 ** Math.abs(v)).toLocaleString('pt-BR')}`);
    const fonte = `12px ${t.fUi}`, fonteB = `600 12px ${t.fUi}`, fonteT = `500 12px ${t.fUi}`;
    const texto = (o) => curto(o.p.t, 18) + (fora(o) ? ` ${sgn(o.g)}%` : '');
    const raio = (o) => (bom(o) ? 8 : 6);
    // ganha nome primeiro quem responde a pergunta; os outros, so onde ha lugar limpo
    const ordem = pontos.map((_, i) => i).sort((i, j) => bom(pontos[j]) - bom(pontos[i]) || pontos[j].p.u - pontos[i].p.u);
    const certos = new Set(ordem.filter((i) => bom(pontos[i])).slice(0, 6));

    let arranjo = null;
    function arranjar(api, area) {
      const pos = pontos.map((o) => api.coord([lx(o.f), cl(o.g)]));
      const a = api.coord([x0, y1]), b = api.coord([0, 0]);
      const z = [a[0], a[1], b[0] - a[0], b[1] - a[1]];
      const bolas = pos.map(([x, y], i) => { const r = raio(pontos[i]); return [x - r, y - r, 2 * r, 2 * r]; });
      const wt = larguraTexto(TITULO, fonteT);
      const tit = [[z[0] + 8, z[1] + 6], [z[0] + 8, z[1] + z[3] - 20]].map(([x, y]) => [x, y, wt, 14])
        .find((c) => c[0] + wt < z[0] + z[2] - 4 && !bolas.some((o) => toca(c, o))) || null;
      const caixas = rotular(
        ordem.map((i) => { const o = pontos[i]; return { x: pos[i][0], y: pos[i][1], r: raio(o), w: larguraTexto(texto(o), bom(o) ? fonteB : fonte), dentro: bom(o), obrigatorio: certos.has(i) }; }),
        { area: [area.x + 2, area.y, area.width + 10, area.height], zona: z, ocupado: tit ? [tit] : [],
          linhas: [[b[0] - 2, area.y, 4, area.height], [area.x, b[1] - 2, area.width, 4]] });
      const rot = pontos.map(() => null); ordem.forEach((i, k) => { rot[i] = caixas[k]; });
      return { pos, z, tit, rot };
    }
    const pronto = (q, api) => (arranjo = q.dataIndexInside === 0 || !arranjo ? arranjar(api, q.coordSys) : arranjo);

    return {
      ...base(t),
      grid: { left: 0, right: 16, top: 28, bottom: 32, containLabel: true },
      graphic: [{ type: 'text', left: 0, top: 2, silent: true, style: { text: 'ganho', fill: t.muted, font: `12px ${t.fNum}` } }],
      tooltip: { ...base(t).tooltip, trigger: 'item', formatter: (q) => {
        const o = porId.get(q.data?.pid); if (!o) return '';
        const v = vezes(o.f);
        return dica(esc(o.p.t), `Custo <b>${v}</b> ${v === 'igual' ? 'ao' : 'que o'} do rival`, `Ganho <b>${sgn(o.g)}%</b>`, SOL_FRASE[o.p.sol]);
      } },
      xAxis: { type: 'value', min: x0, max: x1, interval: px,
        name: 'custo em relação ao rival', nameLocation: 'middle', nameGap: 28, nameTextStyle: rotNum(t),
        axisLabel: { ...rotNum(t), formatter: marcaX, hideOverlap: true }, splitLine: grade(t), axisLine: { show: false }, axisTick: { show: false } },
      yAxis: { type: 'value', min: y0, max: y1, interval: passo,
        axisLabel: { ...rotNum(t), formatter: pct }, splitLine: grade(t) },
      series: [
        { type: 'custom', silent: true, z: -1, tooltip: { show: false }, data: [[x0, y1]],
          renderItem: (q, api) => { arranjo = arranjar(api, q.coordSys); const { z, tit } = arranjo;
            return { type: 'group', children: [
              { type: 'rect', shape: { x: z[0], y: z[1], width: z[2], height: z[3] }, style: { fill: t.sunk } },
              ...(tit ? [{ type: 'text', x: tit[0], y: tit[1], style: { text: TITULO, fill: t.ink2, font: fonteT } }] : []),
            ] }; },
          markLine: { silent: true, symbol: 'none', z: 1, label: { show: false }, lineStyle: { color: t.ink, type: 'solid', width: 1, opacity: .5 },
            data: [{ xAxis: 0 }, { yAxis: 0 }] } },
        { type: 'custom', z: 3, encode: { x: 0, y: 1 }, data: pontos.map((o) => ({ pid: o.p.id, value: [lx(o.f), cl(o.g)] })),
          renderItem: (q, api) => {
            const { pos, rot } = pronto(q, api), i = q.dataIndex, o = pontos[i], c = rot[i], r = raio(o);
            const extra = { cursor: 'pointer', emphasis: { style: { stroke: t.ink, lineWidth: 2, lineDash: null } },
              ...(c ? { textContent: { type: 'text', style: { text: texto(o), fill: bom(o) ? t.ink : t.ink2, font: bom(o) ? fonteB : fonte } },
                textConfig: { position: [c[0] - (pos[i][0] - r), c[1] - (pos[i][1] - r) + 1] } } : {}) };
            return { type: 'group', children: pontoProva(t, o.p, pos[i][0], pos[i][1], r, { cheio, extra }) };
          } },
      ],
    };
  });
</script>

<Quadro id="custo" pergunta="O que melhora gastando menos?" valor={bons.length} vazio={!pontos.length}
  resposta={`de ${plural(pontos.length, 'paper', 'papers')} com custo declarado ${bons.length === 1 ? 'gasta' : 'gastam'} menos sem perder qualidade`}>
  {#if opcao}<Grafico {opcao} altura={268} rotulo="Ganho de cada paper contra o custo em relação ao rival" />
    <Nomes papers={bons.map((o) => o.p)} rotulo="Papers que gastam menos sem perder qualidade" valor={(p) => `${vezes(porId.get(p.id).f)} · ${sgn(porId.get(p.id).g)}%`} />
  {:else}<div class="vazio">Nenhum paper deste recorte declara custo com número.</div>{/if}
  {#snippet legenda()}<Chave />{/snippet}
</Quadro>
