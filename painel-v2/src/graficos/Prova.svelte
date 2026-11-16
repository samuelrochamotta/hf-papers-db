<script>
  // Onde ha votos sem prova: cada paper e um ponto na linha do seu nivel de
  // prova, na posicao dos seus votos. Pontos que se tocariam se afastam dentro
  // da linha, para nenhum esconder outro, e cada linha diz quantos papers tem.
  // A zona marcada e a resposta; os papers dela aparecem pelo nome logo
  // abaixo, para abrir sem cacar ponto.
  import Quadro from '../pecas/Quadro.svelte';
  import Grafico from '../lib/Grafico.svelte';
  import Nomes from '../pecas/Nomes.svelte';
  import { SOLIDEZ, SOL_ROT, SOL_FRASE, median, esc, nome, nomeMenor, plural } from '../lib/dados.js';
  import { base, pontoProva, enxame, rotNum, rotCat, grade, dica, limitesLog, curtoNum, toca, larguraTexto as largura } from '../lib/tema.js';
  import { estado, lente, lentesDe } from '../lib/estado.svelte.js';

  let { papers, todos = papers } = $props();
  const t = $derived(estado.tema);
  const TITULO = 'muito voto, pouca prova';
  // a regua e a mediana do periodo: filtrar nao muda o que conta como "muito voto"
  const med = $derived(median(todos.map((p) => p.u)) || 1);
  const maisVotado = $derived(papers.reduce((m, p) => (!m || p.u > m.u ? p : m), null));
  const naZona = (p) => (p.sol === 'fragil' || p.sol === 'basico') && p.u >= med;
  const zona = $derived(papers.filter(naZona).sort((a, b) => b.u - a.u));
  // prova nao lida nao e pouca prova: fica fora da zona, mas a resposta diz quantos sao
  const semLer = $derived(papers.filter((p) => p.sol === 'sem_leitura' && p.u >= med).length);
  const conta = $derived(Object.fromEntries(SOLIDEZ.map((s) => [s, papers.filter((p) => p.sol === s).length])));
  const ativas = $derived(lentesDe('sol'));
  // onde o nome da zona nao cabe dentro dela (tela estreita), ele vira o titulo dos nomes logo abaixo
  let semTitulo = $state(false);

  // votos: escala linear enquanto o maior nao passa de dez vezes o menor
  const escala = $derived.by(() => {
    const us = papers.map((p) => Math.max(1, +p.u || 1));
    const lo = Math.min(...us), hi = Math.max(...us);
    if (hi / lo >= 10) return { log: true, lim: limitesLog(us) };
    const vao = hi - lo || hi, passo = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000].find((s) => vao / s <= 6) || 10000;
    return { log: false, lim: [Math.max(0, Math.floor((lo - vao * 0.05) / passo) * passo), Math.ceil((hi + vao * 0.05) / passo) * passo || passo] };
  });


  // a altura acompanha a fila mais cheia: em tela estreita os pontos de mesmo voto se empilham, e a faixa
  // de cada nivel cresce ate caber a pilha inteira, sem um ponto encobrir outro
  let larg = $state(480);
  const estreito = $derived(larg < 420);
  const raio = $derived(estreito ? 5 : 6.5);
  const altura = $derived.by(() => {
    if (!papers.length) return 320;
    const { log, lim } = escala, w = Math.max(120, larg - 100), f = (v) => (log ? Math.log10(v) : v);
    const pts = papers.map((p) => ({ x: (f(Math.max(1, p.u)) - f(Math.max(log ? 1 : 0, lim[0]))) / ((f(lim[1]) - f(Math.max(log ? 1 : 0, lim[0]))) || 1) * w, y: SOLIDEZ.indexOf(p.sol) }));
    const pilha = Math.max(0, ...enxame(pts, Infinity, raio).map(Math.abs));
    return Math.max(320, Math.ceil(SOLIDEZ.length * (2 * (pilha + raio + 1) + 8) + 56));
  });

  const opcao = $derived.by(() => {
    if (!t.ink || !papers.length) return null;
    const R = raio;
    const { log, lim } = escala, fonte = `12px ${t.fUi}`, fonteT = `500 12px ${t.fUi}`;
    const linha = (p) => SOLIDEZ.indexOf(p.sol), votos = (p) => Math.max(1, p.u);
    const iz = [SOLIDEZ.indexOf('basico'), SOLIDEZ.indexOf('fragil')];

    // Uma passada por desenho: posicao de cada ponto, a caixa da zona e os
    // nomes que cabem. O nome so entra onde nao encobre ponto, titulo nem outro nome.
    let arranjo = null;
    function arranjar(api, area) {
      const faixa = Math.abs(api.size([0, 1])[1]);
      const pts = papers.map((p) => { const c = api.coord([votos(p), linha(p)]); return { x: c[0], y: c[1] }; });
      const dy = enxame(pts, faixa, R), pos = pts.map((q, i) => [q.x, q.y + dy[i]]);
      const a = api.coord([med, iz[0]]), b = api.coord([lim[1], iz[1]]);
      const z = [a[0], a[1] - faixa / 2, b[0] - a[0], b[1] - a[1] + faixa];
      const bolas = pos.map(([x, y]) => [x - R, y - R, 2 * R, 2 * R]);
      const wt = largura(TITULO, fonteT);
      // nome fora da zona guarda distancia dela: encostado na borda, parece titulo da zona
      const zAr = [z[0] - 4, z[1] - 4, z[2] + 8, z[3] + 8];
      // ganham nome os papers da zona e o mais votado do recorte ("o mais votado tem prova?")
      const fila = papers.map((_, i) => i).filter((i) => naZona(papers[i]) || papers[i] === maisVotado).sort((i, j) => papers[j].u - papers[i].u);
      // O titulo da zona tem dois cantos possiveis. Vale o canto que deixa mais papers com o nome inteiro:
      // o titulo nunca empurra um nome para a forma abreviada se o outro canto resolve
      const cantos = [[z[0] + z[2] - 8 - wt, z[1] + 5, wt, 14], [z[0] + z[2] - 8 - wt, z[1] + z[3] - 19, wt, 14]]
        .filter((c) => c[0] > z[0] + 4 && !bolas.some((o) => toca(c, o)));
      const nomear = (tit) => {
        const caixas = tit ? [tit] : [], rot = papers.map(() => null); let inteiros = 0;
        for (const i of fila) {
          const [x, y] = pos[i], dentro = naZona(papers[i]);
          // primeiro o nome curto do painel; so onde ele nao cabe, o menor
          achar: for (const txt of new Set([nome(papers[i]), nomeMenor(papers[i])])) {
            const w = largura(txt, fonte);
            // ao lado do ponto; fora da zona, tambem logo abaixo ou acima dele, e com um anel no ponto
            const lados = { right: [x + R + 5 + (dentro ? 0 : 3), y - 7], left: [x - R - 5 - (dentro ? 0 : 3) - w, y - 7], below: [x + R + 3 - w, y + R + 4], above: [x + R + 3 - w, y - R - 18] };
            for (const lado of dentro ? ['right', 'left'] : ['left', 'right', 'below', 'above']) {
              const c = [...lados[lado], w, 14];
              if (dentro && (c[0] < z[0] + 4 || c[0] + w > z[0] + z[2] + 12)) continue;      // o nome fica dentro da zona
              if (!dentro && (c[0] < area.x + 2 || c[0] + w > area.x + area.width + 12 || c[1] < area.y || c[1] + 14 > area.y + area.height || toca(c, zAr))) continue;
              if (bolas.some((o, j) => j !== i && toca(c, o)) || caixas.some((o) => toca(c, o))) continue;
              caixas.push(c); rot[i] = { txt, c, anel: !dentro }; if (txt === nome(papers[i])) inteiros++; break achar;
            }
          }
        }
        return { tit, rot, pontos: 2 * inteiros + rot.filter(Boolean).length };
      };
      const tentativas = (cantos.length ? cantos : [null]).map(nomear);
      const { tit, rot } = tentativas.reduce((m, o) => (o.pontos > m.pontos ? o : m));
      if (!tit !== semTitulo) queueMicrotask(() => (semTitulo = !tit));
      return { pos, z, tit, rot };
    }
    const pronto = (q, api) => (arranjo = q.dataIndexInside === 0 || !arranjo ? arranjar(api, q.coordSys) : arranjo);

    return {
      ...base(t),
      grid: { left: 0, right: 16, top: 24, bottom: 32, containLabel: true },
      tooltip: { ...base(t).tooltip, trigger: 'item', formatter: (q) => {
        const p = papers.find((x) => x.id === q.data?.pid); if (!p) return '';
        return dica(esc(p.t), `<b>${p.u.toLocaleString('pt-BR')}</b> votos`, `${SOL_FRASE[p.sol]}${p.nl ? ` · cumpre ${p.T} de ${p.nl} sinais lidos` : ''}`);
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
          renderItem: (q, api) => { arranjo = arranjar(api, q.coordSys); const { z, tit } = arranjo;
            return { type: 'group', children: [
              { type: 'rect', shape: { x: z[0], y: z[1], width: z[2], height: z[3], r: 4 }, style: { fill: t.alertSoft } },
              ...(tit ? [{ type: 'text', x: tit[0], y: tit[1], style: { text: TITULO, fill: t.alert, font: fonteT } }] : []),
            ] }; },
          markLine: { silent: true, symbol: 'none', data: [{ xAxis: med }], lineStyle: { color: t.muted, type: [2, 3], width: 1 },
            label: { show: true, position: 'start', formatter: `mediana do período ${med.toLocaleString('pt-BR', { maximumFractionDigits: 1 })}`, color: t.muted, fontSize: 12, fontFamily: t.fUi } } },
        { type: 'custom', z: 3, encode: { x: 0, y: 1 }, data: papers.map((p) => ({ pid: p.id, value: [votos(p), linha(p)] })),
          renderItem: (q, api) => {
            const { pos, rot } = pronto(q, api), i = q.dataIndex, r = rot[i];
            const extra = { cursor: 'pointer', emphasis: { style: { stroke: t.ink, lineWidth: 2, lineDash: null } },
              ...(r ? { textContent: { type: 'text', style: { text: r.txt, fill: t.ink, font: fonte } }, textConfig: { position: [r.c[0] - (pos[i][0] - R), r.c[1] - (pos[i][1] - R) + 1] } } : {}) };
            // o ponto com nome fora da zona ganha um anel: o nome e dele, nao do vizinho por onde o texto passa
            const anel = r?.anel ? [{ type: 'circle', silent: true, shape: { cx: pos[i][0], cy: pos[i][1], r: R + 3.5 }, style: { fill: 'none', stroke: t.ink, lineWidth: 1 } }] : [];
            return { type: 'group', children: [...anel, ...pontoProva(t, papers[i], pos[i][0], pos[i][1], R, { extra })] };
          } },
      ],
    };
  });
  const clicar = (q) => {
    if (q.componentType !== 'yAxis') return;
    if (conta[q.value]) { lente('sol', q.value); return true; }
  };
</script>

<Quadro id="prova" pergunta="Onde há votos sem prova?" valor={zona.length} vazio={!papers.length} resposta={`${zona.length === 1 ? 'paper' : 'papers'} com votos acima da mediana e prova frágil ou básica${semLer ? `, mais ${semLer} com prova não lida` : ''}`}>
  {#if opcao}<div class="cresce" bind:clientWidth={larg}><Grafico {opcao} {altura} aoClicar={clicar} rotulo="Votos de cada paper por nível de prova" /></div>
  {:else}<div class="vazio">Nenhum paper neste recorte.</div>{/if}
  <Nomes papers={zona} titulo={semTitulo ? 'Muito voto, pouca prova' : ''} rotulo="Papers com muito voto e pouca prova" valor={(p) => p.u.toLocaleString('pt-BR')} alerta />
  <!-- o mais votado tem nome proprio embaixo do grafico: e a resposta a "o mais votado tem prova?", e o anel no ponto aponta para ele -->
  {#if maisVotado && !zona.includes(maisVotado)}<Nomes papers={[maisVotado]} titulo="O mais votado" rotulo="O paper mais votado do recorte" valor={(p) => `${p.u.toLocaleString('pt-BR')} · ${SOL_FRASE[p.sol].toLowerCase()}`} />{/if}
</Quadro>
