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
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  aplicaLentes, lenteValida, rotuloLente, ordenar, comDado, ORDENS, buscar, periodos, noPeriodo,
  radarValores, median, ganhoDe, intervalo, plural, sgn, curto, cobertura, esc, urlSegura, SOLIDEZ, realcar, ondeAchou,
} from '../../painel-v2/src/lib/dados.js';
import { enxame, rotular, toca, dominio } from '../../painel-v2/src/lib/tema.js';

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
  assert.equal(c.inteira + c.parcial + c.insuf, ps.length);
  assert.equal(c.total, ps.length + REAL.faltam.length);
});
