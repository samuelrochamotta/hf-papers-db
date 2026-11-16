/* O recorte do painel v2 (painel-v2/src/lib): o que cada filtro, ordem, busca
 * e periodo deixa na tela. Sao funcoes puras, as mesmas que vao para o
 * navegador.
 *
 * Contratos:
 * 1. Filtros do mesmo menu se alternam (ou); menus diferentes se somam (e).
 * 2. Em toda ordem, paper sem o dado vai para o fim: "nao lido" nunca disputa
 *    posicao com valor medido.
 * 3. O periodo so oferece a opcao que muda o recorte.
 * 4. No radar, eixo nao lido nao vira zero.
 * 5. O enxame do grafico de prova e deterministico e nao sobrepoe pontos.
 * 6. A busca diz onde casou: marca o termo no texto visivel e nomeia o campo
 *    quando o termo nao esta na linha.
 * 7. Nome de ponto nao encobre ponto nem outro nome e fica do mesmo lado da
 *    zona que o ponto; quem responde a pergunta do quadro ganha nome sempre.
 * 8. O eixo so corta o que foge muito: valor a menos de um passo da borda entra.
 * 9. A marca de prova nao depende so da cor: o disco enche conforme o nivel
 *    (inteiro, 3/4, metade, 1/4) e "nao lida" e um anel tracejado.
 * 10. Fato que falta diz por que falta: nenhuma tela poe traco no lugar dele.
 * 11. No radar, o que a nota de 0 a 100 esconde aparece no desenho: marca de
 *     corte em quem passa do teto da amplitude, vertice vazado onde a abertura
 *     so conta parte dos artefatos, e a escala escrita nos aneis.
 * 12. A fila (paper sem leitura) entra na busca pelo titulo e pelo id.
 * 13. O nome curto de um paper e um so em todo o painel.
 * 14. A abertura usa as mesmas palavras em toda tela e diz quantos artefatos
 *     a leitura nao alcancou; os limites dos autores tem um nome so.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  aplicaLentes, lenteValida, rotuloLente, ordenar, comDado, ORDENS, buscar, periodos, noPeriodo,
  radarValores, median, ganhoDe, intervalo, plural, sgn, curto, cobertura, esc, urlSegura, SOLIDEZ, realcar, ondeAchou,
  buscarFila, SEM_FATO, FATO, EIXOS, ESFORCO, TETO_AMPLITUDE, passaDoEixo, tetoDoEixo, naoLidosDe, nBench, nome, nomeMenor,
  aberturaFrase, faltaLer, faltaLerNomes, LIMITE_TIPO, LIMITE_GRAVE,
} from '../../painel-v2/src/lib/dados.js';
import { enxame, rotular, toca, dominio, pontoProva, marcasRadar } from '../../painel-v2/src/lib/tema.js';

const RADAR = { atencao: 50, solidez: 50, ganho: 50, facilidade: 50, abertura: 50, amplitude: 50 };
function paper(id, o = {}) {
  return {
    id, t: `Paper ${id}`, d: '2026-11-10', u: 10, org: null, sol: 'firme', esf: 2, ar: ['robotica_acao'], ents: [], res: [],
    ab: { codigo: 'ausente', pesos: 'ausente', dados: 'ausente', demo: 'ausente' }, ent: 'metodo', cam: null, L: { c: 'parcial' },
    ...o, radar: { ...RADAR, ...(o.radar || {}) },
  };
}
const ids = (ps) => ps.map((p) => p.id);
const REAL = JSON.parse(readFileSync(new URL('../../relatorios/painel-v2/dados.json', import.meta.url), 'utf8'));

test('sem filtro, o recorte e a lista inteira', () => {
  const ps = [paper('a'), paper('b')];
  assert.equal(aplicaLentes(ps, []), ps);
});

test('filtros do mesmo menu se alternam; menus diferentes se somam', () => {
  const ps = [
    paper('a', { sol: 'forte', esf: 2 }), paper('b', { sol: 'firme', esf: 2 }),
    paper('c', { sol: 'forte', esf: 4 }), paper('d', { sol: 'fragil', esf: 2 }),
  ];
  assert.deepEqual(ids(aplicaLentes(ps, [{ k: 'sol', v: 'forte' }])), ['a', 'c']);
  assert.deepEqual(ids(aplicaLentes(ps, [{ k: 'sol', v: 'forte' }, { k: 'sol', v: 'firme' }])), ['a', 'b', 'c']);
  assert.deepEqual(ids(aplicaLentes(ps, [{ k: 'sol', v: 'forte' }, { k: 'sol', v: 'firme' }, { k: 'esf', v: 2 }])), ['a', 'b']);
});

test('filtro de arena e de familia olham listas do paper', () => {
  const ps = [
    paper('a', { ar: ['robotica_acao', 'video'], ents: [['Qwen2.5-VL', 'modelo']] }),
    paper('b', { ar: ['video'], ents: [['Llama 3', 'modelo']] }),
  ];
  assert.deepEqual(ids(aplicaLentes(ps, [{ k: 'ar', v: 'video' }])), ['a', 'b']);
  assert.deepEqual(ids(aplicaLentes(ps, [{ k: 'ar', v: 'robotica_acao' }])), ['a']);
  assert.deepEqual(ids(aplicaLentes(ps, [{ k: 'fam', v: 'Qwen' }])), ['a']);
});

test('filtro de chave desconhecida nao esvazia o recorte', () => {
  const ps = [paper('a')];
  assert.deepEqual(ids(aplicaLentes(ps, [{ k: 'xyz', v: 1 }])), ['a']);
});

test('o endereco so liga filtros conhecidos', () => {
  assert.deepEqual(lenteValida('sol', 'forte'), { k: 'sol', v: 'forte' });
  assert.deepEqual(lenteValida('esf', '2'), { k: 'esf', v: 2 });
  assert.deepEqual(lenteValida('ar', 'robotica_acao'), { k: 'ar', v: 'robotica_acao' });
  for (const [k, v] of [['sol', 'otima'], ['esf', '9'], ['esf', 'x'], ['ar', '<script>'], ['fam', ''], ['nada', 'x']]) assert.equal(lenteValida(k, v), null, `${k}:${v}`);
  assert.equal(rotuloLente({ k: 'esf', v: 2 }), 'Adoção: Integrar');
});

test('em toda ordem, paper sem o dado vai para o fim', () => {
  const ps = [
    paper('sem', { u: 99, sol: 'sem_leitura', radar: { solidez: null, ganho: null, facilidade: null, abertura: null, amplitude: null } }),
    paper('baixo', { u: 5, sol: 'fragil', res: [{ rext: 1 }], radar: { solidez: 10, facilidade: 10, abertura: 10, amplitude: 10 } }),
    paper('alto', { u: 7, sol: 'forte', res: [{ rext: 9 }], radar: { solidez: 90, facilidade: 90, abertura: 90, amplitude: 90 } }),
  ];
  for (const [ordem] of ORDENS.filter(([k]) => !['votos', 'recentes'].includes(k))) {
    assert.deepEqual(ids(ordenar(ps, ordem)), ['alto', 'baixo', 'sem'], ordem);
    assert.equal(comDado(ps, ordem), 2, ordem);
  }
  assert.deepEqual(ids(ordenar(ps, 'votos')), ['sem', 'alto', 'baixo']);
});

test('ordem empatada se resolve pelos votos e nao muda a lista original', () => {
  const ps = [paper('a', { u: 1 }), paper('b', { u: 9 }), paper('c', { u: 5 })];
  assert.deepEqual(ids(ordenar(ps, 'facilidade')), ['b', 'c', 'a']);
  assert.deepEqual(ids(ps), ['a', 'b', 'c']);
});

test('o ganho do paper e a mediana contra o rival externo', () => {
  assert.equal(ganhoDe(paper('a', { res: [{ rext: 1 }, { rext: 5 }, { rext: null }, { rext: 3 }] })), 3);
  assert.equal(ganhoDe(paper('b', { res: [{ rext: null }] })), null);
  assert.equal(median([4, null, 2]), 3);
  assert.equal(median([]), null);
});

test('a busca ignora acento e caixa e exige todos os termos', () => {
  const ps = [paper('a', { t: 'Geração de Vídeo em Tempo Real', org: 'USP' }), paper('b', { t: 'Agent Harness', ents: [['Qwen', 'modelo']] })];
  assert.deepEqual(ids(buscar(ps, 'video GERACAO')), ['a']);
  assert.deepEqual(ids(buscar(ps, 'qwen')), ['b']);
  assert.deepEqual(ids(buscar(ps, 'video qwen')), []);
  assert.equal(buscar(ps, '   '), ps);
});

test('a busca marca o termo no texto, sem trocar o texto', () => {
  const pedacos = realcar('Geração de Vídeo: geracao rápida', 'GERACAO video');
  assert.equal(pedacos.map((x) => x[0]).join(''), 'Geração de Vídeo: geracao rápida');
  assert.deepEqual(pedacos.filter((x) => x[1]).map((x) => x[0]), ['Geração', 'Vídeo', 'geracao']);
  assert.deepEqual(realcar('Sem termo', '  '), [['Sem termo', false]]);
  assert.deepEqual(realcar('Nada casa aqui', 'xyz'), [['Nada casa aqui', false]]);
});

test('a busca nomeia o campo quando o termo nao esta na linha', () => {
  const p = paper('a', { t: 'Agent Harness', org: 'USP', cam: 'agente_harness', ar: ['robotica_acao'], ents: [['Qwen2.5-VL', 'modelo']] });
  assert.equal(ondeAchou(p, 'agent'), '', 'termo no titulo');
  assert.equal(ondeAchou(p, 'metodo harness'), '', 'tipo e camada ja aparecem na linha');
  assert.equal(ondeAchou(p, 'usp'), 'Organização: USP');
  assert.equal(ondeAchou(p, 'qwen robotica'), 'Cita: Qwen2.5-VL · Arena: Robótica');
  assert.equal(ondeAchou(p, ''), '');
});

test('o periodo so oferece a opcao que muda o recorte', () => {
  const dias = ['2026-11-01', '2026-11-09', '2026-11-10'];
  const dados = { dias, papers: [paper('a', { d: '2026-11-10' }), paper('b', { d: '2026-11-09' }), paper('c', { d: '2026-11-01' })] };
  assert.deepEqual(periodos(dados), [['1', 'Último dia', 1], ['7', '7 dias', 2], ['tudo', 'Tudo', 3]]);
  assert.deepEqual(ids(noPeriodo(dados.papers, dias, '7')), ['a', 'b']);
  assert.equal(noPeriodo(dados.papers, dias, 'tudo'), dados.papers);
  assert.deepEqual(periodos({ dias: [], papers: [] }), [['tudo', 'Tudo', 0]]);
  assert.deepEqual(periodos(null), [['tudo', 'Tudo', 0]]);
});

test('no radar, eixo nao lido nao vira zero', () => {
  const v = radarValores([80, null, 80, 80, 80, 80]);
  assert.ok(v[1] > 0 && v[1] < 80, `vertice de passagem: ${v[1]}`);
  assert.deepEqual(radarValores([null, null, null, null, null, null]), [0, 0, 0, 0, 0, 0]);
  assert.deepEqual(radarValores([10, 20, 30, 40, 50, 60]), [10, 20, 30, 40, 50, 60]);
});

test('o enxame e deterministico, nao sobrepoe pontos e cabe na faixa', () => {
  const pts = [0, 2, 4, 5, 40, 41, 90].map((x) => ({ x, y: 0 })).concat([{ x: 3, y: 1 }]);
  const a = enxame(pts, 80), b = enxame(pts, 80);
  assert.deepEqual(a, b);
  assert.equal(a[7], 0, 'ponto sozinho na linha fica no eixo');
  assert.equal(a[6], 0, 'ponto longe dos outros fica no eixo');
  const d = 2 * 6.5 + 2;
  for (let i = 0; i < 7; i++) for (let j = i + 1; j < 7; j++) {
    assert.ok(Math.hypot(pts[i].x - pts[j].x, a[i] - a[j]) >= d - 0.02, `pontos ${i} e ${j} se tocam`);
  }
  // sem espaco, encolhe para dentro da faixa em vez de vazar para a linha vizinha
  const apertado = enxame(Array.from({ length: 30 }, () => ({ x: 0, y: 0 })), 40);
  for (const dy of apertado) assert.ok(Math.abs(dy) <= 40 / 2 - 6.5 - 1 + 1e-9);
});

test('nome de ponto nao encobre ponto nem outro nome e respeita a zona', () => {
  const area = [0, 0, 300, 200], zona = [0, 0, 200, 100], linhas = [[198, 0, 4, 200], [0, 98, 300, 4]];
  const itens = [
    { x: 40, y: 60, r: 8, w: 60, dentro: true, obrigatorio: true },      // na zona
    { x: 170, y: 55, r: 8, w: 90, dentro: true, obrigatorio: true },     // na zona, perto da linha de custo igual
    { x: 215, y: 30, r: 6, w: 50, dentro: false },                       // fora, logo depois da linha
    { x: 212, y: 44, r: 6, w: 120, dentro: false },                      // fora, sem lugar limpo para um nome longo
    { x: 120, y: 160, r: 6, w: 80, dentro: false },                      // fora, embaixo
  ];
  const cx = rotular(itens, { area, zona, linhas });
  assert.deepEqual(rotular(itens, { area, zona, linhas }), cx, 'mesma entrada, mesmo desenho');
  assert.ok(cx[0] && cx[1], 'quem responde a pergunta tem nome');
  assert.equal(cx[3], null, 'sem lugar limpo, o nome nao entra');
  const bolas = itens.map((o) => [o.x - o.r, o.y - o.r, 2 * o.r, 2 * o.r]);
  cx.forEach((c, i) => {
    if (!c) return;
    assert.ok(c[0] >= area[0] && c[0] + c[2] <= area[0] + area[2] && c[1] >= area[1] && c[1] + c[3] <= area[1] + area[3], `nome ${i} dentro da area`);
    bolas.forEach((b, j) => { if (j !== i) assert.ok(!toca(c, b), `nome ${i} encobre o ponto ${j}`); });
    cx.forEach((d, j) => { if (d && j > i) assert.ok(!toca(c, d), `nomes ${i} e ${j} se sobrepoem`); });
    linhas.forEach((l) => assert.ok(!toca(c, l), `nome ${i} cruza linha de referencia`));
    if (itens[i].dentro) assert.ok(c[0] >= zona[0] && c[0] + c[2] <= zona[0] + zona[2] && c[1] + c[3] <= zona[1] + zona[3], `nome ${i} fica na zona`);
    else assert.ok(!toca(c, zona), `nome ${i}, de fora, entra na zona`);
  });
  // apertado, o obrigatorio ainda ganha nome (no lugar menos ruim); o opcional, nao
  const junto = [{ x: 50, y: 50, r: 8, w: 280, dentro: true, obrigatorio: true }, { x: 60, y: 60, r: 6, w: 280, dentro: false }];
  const ap = rotular(junto, { area, zona, linhas });
  assert.ok(ap[0]); assert.equal(ap[1], null);
});

test('o eixo so corta o que foge muito', () => {
  // -12,6 fica a menos de um passo de -10: entra. +66 foge do conjunto: fica de fora, para ser desenhado na borda.
  const [d0, d1, passo] = dominio([-12.6, 3.4, 4.7, 7.8, 10.2], { inclui: [-10, 10] });
  assert.equal(passo, 5); assert.equal(d0, -15); assert.ok(d1 >= 10.2);
  const [, e1] = dominio([66.2, 21.4, 12.7, 10.2, 7.8, 4.7, 4.2, 3.4, 1.2, 0.6, 0.6, 0.3, -1.1, -9.2, -12.6]);
  assert.ok(e1 < 66.2 && e1 >= 21.4);
  assert.deepEqual(dominio([]), [0, 5, 5]);
});

test('a marca de prova enche conforme o nivel e nao lida e anel tracejado', () => {
  const t = { surface: '#fff', solNada: '#999', solForte: '#001', solFirme: '#002', solBasico: '#003', solFragil: '#004' };
  const volta = (sol) => { const [, fatia] = pontoProva(t, { sol }, 0, 0, 6); return fatia ? (fatia.shape.endAngle - fatia.shape.startAngle) / (2 * Math.PI) : null; };
  assert.equal(pontoProva(t, { sol: 'forte' }, 0, 0, 6).length, 1, 'forte e um disco inteiro');
  assert.deepEqual(['firme', 'basico', 'fragil'].map(volta), [0.75, 0.5, 0.25]);
  const [anel] = pontoProva(t, { sol: 'sem_leitura' }, 0, 0, 6);
  assert.ok(anel.style.lineDash && anel.style.fill === t.surface, 'nao lida: anel tracejado, sem fatia');
  assert.equal(pontoProva(t, { sol: 'sem_leitura' }, 0, 0, 6).length, 1);
  // ponto pequeno demais para a fatia: volta ao disco de cor
  assert.equal(pontoProva(t, { sol: 'basico' }, 0, 0, 3, { cheio: false }).length, 1);
});

test('textos de apoio: intervalo, plural, sinal e nome curto', () => {
  assert.equal(intervalo('2026-11-02', '2026-11-13'), '2 a 13 de nov.');
  assert.equal(intervalo('2026-10-28', '2026-11-13'), '28 de out. a 13 de nov.');
  assert.equal(intervalo('2026-11-13', '2026-11-13'), '13 de nov.');
  assert.equal(plural(1, 'paper', 'papers'), '1 paper');
  assert.equal(plural(2, 'paper', 'papers'), '2 papers');
  assert.equal(sgn(3.44), '+3,4');
  assert.equal(sgn(-12.6), '−12,6');
  assert.equal(sgn(null), '–');
  assert.equal(curto('CoworkOS: Scaling Agent Coworkers'), 'CoworkOS');
  assert.ok(curto('Um titulo bem comprido sem dois pontos nenhum', 20).endsWith('…'));
});

test('texto de fora e escapado e so link http(s) passa', () => {
  assert.equal(esc('<img onerror="x">'), '&lt;img onerror=&quot;x&quot;&gt;');
  assert.equal(urlSegura('javascript:alert(1)'), null);
  assert.equal(urlSegura(' https://arxiv.org/abs/1 '), 'https://arxiv.org/abs/1');
});

test('nos dados publicados, toda ordem e uma permutacao e todo filtro existente traz papers', () => {
  const ps = REAL.papers;
  assert.ok(ps.length > 0);
  for (const [ordem] of ORDENS) {
    const o = ordenar(ps, ordem), n = comDado(ps, ordem);
    assert.equal(new Set(ids(o)).size, ps.length, ordem);
    assert.ok(n <= ps.length);
  }
  for (const s of SOLIDEZ) assert.equal(aplicaLentes(ps, [{ k: 'sol', v: s }]).length, ps.filter((p) => p.sol === s).length, s);
  for (const a of new Set(ps.flatMap((p) => p.ar))) assert.ok(aplicaLentes(ps, [{ k: 'ar', v: a }]).length > 0, a);
  const c = cobertura(ps, REAL.faltam);
  assert.equal(c.inteira + c.parcial, ps.length);
  assert.equal(c.total, ps.length + REAL.faltam.length);
});

test('fato que falta diz por que falta, sem traco', () => {
  const semRes = paper('a', { sol: 'sem_leitura', esf: 0, radar: { ganho: null, solidez: null, abertura: null, facilidade: null, amplitude: null } });
  const semRival = paper('b', { res: [{ b: 'X', rext: null }], radar: { ganho: null } });
  assert.equal(SEM_FATO.ganho(semRes), 'não achado');
  assert.equal(SEM_FATO.ganho(semRival), 'sem rival externo');
  assert.equal(SEM_FATO.facilidade(semRes), ESFORCO[0]);
  for (const [k] of EIXOS) {
    const txt = FATO[k](semRes) ?? SEM_FATO[k](semRes);
    assert.ok(typeof txt === 'string' && !/^[–—-]?$/.test(txt.trim()) || k === 'atencao', `${k}: "${txt}"`);
  }
  // nos dados publicados, todo paper tem um texto para cada eixo
  for (const p of REAL.papers) for (const [k] of EIXOS) {
    const txt = FATO[k](p) ?? SEM_FATO[k](p);
    assert.ok(txt && !/^[–—-]$/.test(txt), `${p.id} ${k}`);
  }
});

test('no radar, quem passa do teto da amplitude ganha corte e a abertura lida em parte ganha faixa', () => {
  const res = (n) => Array.from({ length: n }, (_, i) => ({ b: `B${i}`, rext: 1 }));
  const teto = paper('a', { res: res(TETO_AMPLITUDE), radar: { amplitude: 100 } }), mais = paper('b', { res: res(20), radar: { amplitude: 100 } });
  assert.equal(nBench(teto), TETO_AMPLITUDE);
  assert.equal(passaDoEixo('amplitude', teto), false);
  assert.equal(passaDoEixo('amplitude', mais), true);
  assert.equal(passaDoEixo('ganho', mais), false);
  const parte = paper('c', { ab: { codigo: 'liberado', pesos: 'nao_lido', dados: 'nao_lido', demo: 'nao_lido' }, radar: { abertura: 40 }, abTeto: 100 });
  const tudo = paper('d', { ab: { codigo: 'liberado', pesos: 'ausente', dados: 'ausente', demo: 'ausente' }, radar: { abertura: 40 }, abTeto: 40 });
  const nada = paper('e', { ab: { codigo: 'nao_lido', pesos: 'nao_lido', dados: 'nao_lido', demo: 'nao_lido' }, radar: { abertura: null }, abTeto: null });
  assert.equal(naoLidosDe(parte), 3);
  assert.equal(tetoDoEixo('abertura', parte), 100);
  assert.equal(tetoDoEixo('abertura', tudo), null, 'tudo lido: a faixa e um ponto');
  assert.equal(tetoDoEixo('abertura', nada), null, 'eixo todo nao lido nao tem vertice nem faixa');
  assert.equal(tetoDoEixo('amplitude', parte), null);
  // nos dados publicados, a faixa nunca fica abaixo do vertice e nunca passa de 100
  for (const p of REAL.papers) { const h = tetoDoEixo('abertura', p); assert.ok(h == null || (h > p.radar.abertura && h <= 100), p.id); }
});

test('as marcas do radar: escala nos aneis, faixa no eixo e corte fora do anel', () => {
  const t = { muted: '#666', surface: '#fff', fNum: 'mono' }, r = 100, cx = 200, cy = 200;
  const itens = [{ valores: [50, 40, null, 100, 20, 30], cor: '#a00', simbolo: 'circle', faixas: [null, 100, null, null, null, null], cortes: [false, false, false, true, false, false] }];
  const els = marcasRadar(t, { cx, cy, r, itens });
  const textos = els.filter((e) => e.type === 'text').map((e) => e.style.text);
  assert.deepEqual(textos, ['50', '100']);
  // a escala fica na aresta entre o primeiro e o ultimo eixo: nunca em cima de um raio, onde caem os vertices
  for (const e of els.filter((x) => x.type === 'text')) assert.ok(Math.abs(e.x - cx) > 10, 'rotulo fora do raio do topo');
  // a faixa e um intervalo, nao um dado: fio fino e tique de fecho atravessado, os dois na cor apagada, sem anel nem cor do paper
  const [faixa, fecho] = els.filter((e) => e.type === 'line');
  assert.ok(faixa && !faixa.style.lineDash && faixa.style.lineWidth <= 1 && faixa.style.stroke === t.muted, 'fio fino na cor apagada');
  assert.ok(fecho && fecho.style.stroke === t.muted, 'o fecho tambem e apagado');
  assert.equal(els.filter((e) => e.type === 'circle').length, 0, 'nenhum anel: um anel se lia como valor medido');
  // a faixa sai do vertice (40) e vai ate o anel de 100 do segundo eixo; o fecho atravessa o eixo no 100
  assert.ok(Math.abs(Math.hypot(faixa.shape.x1 - cx, faixa.shape.y1 - cy) - 0.4 * r) < 0.01);
  assert.ok(Math.abs(Math.hypot(faixa.shape.x2 - cx, faixa.shape.y2 - cy) - r) < 0.01);
  const mx = (fecho.shape.x1 + fecho.shape.x2) / 2, my = (fecho.shape.y1 + fecho.shape.y2) / 2;
  assert.ok(Math.abs(mx - faixa.shape.x2) < 0.01 && Math.abs(my - faixa.shape.y2) < 0.01, 'o fecho fica no fim da faixa');
  const cortes = els.filter((e) => e.type === 'polyline');
  assert.equal(cortes.length, 2);
  for (const c of cortes) assert.ok(Math.hypot(c.shape.points[1][0] - cx, c.shape.points[1][1] - cy) > r, 'a marca de corte fica fora do anel');
  // sem aviso, so a escala
  assert.equal(marcasRadar(t, { cx, cy, r, itens: [{ valores: [1, 2, 3, 4, 5, 6], cor: '#000', simbolo: 'rect' }] }).length, 2);
});

test('a fila entra na busca pelo titulo e pelo id', () => {
  const fila = [{ id: '2611.05376', t: 'From Autonomous Agents to Cognitive Symbionts', u: 105, d: '2026-11-06' }, { id: '2611.12806', t: 'Learning Heterogeneous Tactile Representation', u: 102, d: '2026-11-10' }];
  assert.equal(buscarFila(fila, '').length, 2);
  assert.deepEqual(ids(buscarFila(fila, 'TÁCTILE learning')), ['2611.12806']);
  assert.deepEqual(ids(buscarFila(fila, '2611.05376')), ['2611.05376']);
  assert.equal(buscarFila(fila, 'robot').length, 0);
  assert.equal(buscarFila(REAL.faltam, '').length, REAL.faltam.length);
});

test('o nome curto e um so: o titulo ate os dois-pontos, cortado em palavra inteira', () => {
  assert.equal(nome({ t: 'SLA: Scaling Spatial-Language-Action Model' }), 'SLA');
  assert.equal(nome({ t: "Don't Just Trust Your Memory: Evidence-Linked Memory" }), "Don't Just Trust Your Memory");
  assert.equal(nome({ t: 'Advances in Agentic Computer Graphics' }), 'Advances in Agentic Computer…');
  assert.equal(nomeMenor({ t: 'Advances in Agentic Computer Graphics' }), 'Advances in…');
  // o corte nao termina em palavra de ligacao, desde que sobrem duas palavras
  assert.equal(nome({ t: 'SO-Arena Benchmarking the Capability Spectrum and Reliability of System One Models' }), 'SO-Arena Benchmarking…');
  for (const p of REAL.papers) { assert.ok(nome(p).length <= 29, p.t); assert.ok(nomeMenor(p).length <= nome(p).length); }
});

test('a abertura tem as mesmas palavras em toda tela e nao esconde a parte nao lida', () => {
  const NL = { codigo: 'nao_lido', pesos: 'nao_lido', dados: 'nao_lido', demo: 'nao_lido' };
  const codigo = paper('a', { ab: { ...NL, codigo: 'liberado' }, radar: { abertura: 100 } });
  const dois = paper('b', { ab: { codigo: 'liberado', pesos: 'liberado', dados: 'ausente', demo: 'ausente' }, radar: { abertura: 70 } });
  const pagina = paper('c', { ab: { ...NL, codigo: 'so_pagina' }, radar: { abertura: 15 } });
  const nada = paper('d', { ab: { codigo: 'ausente', pesos: 'ausente', dados: 'ausente', demo: 'ausente' }, radar: { abertura: 0 } });
  const semLer = paper('e', { ab: NL, radar: { abertura: null } });
  // o fato, sob o rotulo "Abertura", e a frase, onde nao ha rotulo: a segunda so acrescenta o verbo
  assert.equal(FATO.abertura(codigo), 'código'); assert.equal(aberturaFrase(codigo), 'liberou código');
  assert.equal(FATO.abertura(dois), 'código e pesos'); assert.equal(aberturaFrase(dois), 'liberou código e pesos');
  assert.equal(aberturaFrase(pagina), 'só a página'); assert.equal(aberturaFrase(nada), 'nada liberado');
  assert.equal(aberturaFrase(semLer), 'abertura não achada');
  // "nada" ou "só a página" com parte nao verificada nao e ausencia: o resto vem junto, e o paper aberto diz quais
  assert.equal(faltaLer(codigo), 'resto não verificado'); assert.equal(faltaLer(pagina), 'resto não verificado');
  assert.equal(faltaLerNomes(codigo), 'pesos, dados e demo não verificados'); assert.equal(faltaLerNomes(dois), '');
  assert.equal(faltaLer(dois), ''); assert.equal(faltaLer(nada), '');
  assert.equal(faltaLer(paper('f', { ab: { codigo: 'liberado', pesos: 'liberado', dados: 'liberado', demo: 'nao_lido' }, radar: { abertura: 100 } })), 'resto não verificado');
  assert.equal(faltaLerNomes(paper('f2', { ab: { codigo: 'liberado', pesos: 'liberado', dados: 'liberado', demo: 'nao_lido' }, radar: { abertura: 100 } })), 'demo não verificada');
  assert.equal(faltaLer(paper('g', { ab: { codigo: 'liberado', pesos: 'nao_lido', dados: 'liberado', demo: 'liberado' }, radar: { abertura: 90 } })), 'resto não verificado');
  assert.equal(faltaLerNomes(paper('g2', { ab: { codigo: 'liberado', pesos: 'nao_lido', dados: 'liberado', demo: 'liberado' }, radar: { abertura: 90 } })), 'pesos não verificados');
  assert.equal(faltaLer(semLer), '', 'eixo todo nao achado ja diz "abertura não achada"');
  // nos dados publicados, todo paper tem frase, e nenhuma diz "nada" sozinha
  for (const p of REAL.papers) { assert.ok(aberturaFrase(p).length > 3, p.id); assert.notEqual(aberturaFrase(p), 'nada'); }
});

test('os limites dos autores tem um nome so, com o tipo por extenso', () => {
  // todo tipo que a leitura publica tem nome em portugues; grave e um subconjunto com nome
  for (const p of REAL.papers) for (const r of p.ress) assert.ok(LIMITE_TIPO[r[0]], `tipo sem nome: ${r[0]}`);
  for (const k of LIMITE_GRAVE) assert.ok(LIMITE_TIPO[k], k);
});
