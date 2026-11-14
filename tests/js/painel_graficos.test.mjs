/* Os graficos do Panorama (Apache ECharts) e o estado na URL.
 *
 * O ECharts aqui e de mentira (ver `dom_painel.mjs`): o teste nao olha
 * pixel, olha o contrato - que grafico existe, o que a opcao dele diz, e que
 * o clique nele recorta o painel como o clique numa pilula recortaria. E que
 * o recorte vai para o fragmento da URL e volta dele.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { montarPainel } from './dom_painel.mjs';

function paper(id, { d = '2026-09-01', v = 'aprovado', nt = 'proposta', a = 'Alfa', sa = 'Benchmark', vt = ['Medir'], extra = {} } = {}) {
  const base = { id, t: 'Paper ' + id, d, v, rf: v === 'fora' ? 'geracao_de_midia' : null, a, sa, vt, oa: 0, pp: 0, u: 10, c: 1, gs: 0,
    org: 'acme', na: 1, nv: 0, url: 'https://x/' + id, f: 0 };
  if (v === 'aprovado') Object.assign(base, { j: 'motivo', h: 0, nt, ao: 0 });
  return { ...base, ...extra };
}

const DADOS = {
  gerado: '2026-09-03T08:00:00', modeloA: 'm', modeloB: 'm', janela: 90, pendentes: 0, diasHall: 90, diasRefresh: 90,
  areas: [{ a: 'Alfa', def: '' }, { a: 'Beta', def: '' }],
  subdef: { Benchmark: '', 'Difusão': '' },
  vertentes: [{ v: 'Medir', def: '' }, { v: 'Treinar', def: '' }],
  naturezas: [{ k: 'proposta', r: 'Proposta', def: '' }, { k: 'achado_empirico', r: 'Achado empírico', def: '' },
    { k: 'teoria', r: 'Teoria', def: '' }, { k: 'panorama', r: 'Panorama', def: '' }],
  papers: [
    paper('a1', { extra: { vg: ['2026-08-28', 2, '2026-09-03', 30], vm: [0, 50, 1, 80, 14, 100] } }),
    paper('a2', { d: '2026-09-02', nt: 'achado_empirico', vt: ['Treinar'], extra: { vg: ['2026-08-30', 5, '2026-09-02', 9] } }),
    paper('f1', { v: 'fora', a: 'Beta', sa: 'Difusão' }),
    paper('f2', { v: 'fora', a: 'Beta', sa: 'Difusão', d: '2026-09-02', extra: { rf: 'fora_de_escopo' } }),
  ],
  fichas: [], hall: [],
};

const painel = (opcoes = {}) => montarPainel(structuredClone(DADOS), { echarts: true, ...opcoes });

test('o Panorama monta um grafico por secao com dado, cada um com o resumo em texto como descricao acessivel', () => {
  const p = painel({ hash: '#aba=panorama' });
  assert.deepEqual(Object.keys(p.graficos).sort(),
    ['areas-dist', 'ganho', 'matriz', 'regras', 'taxa', 'volume'].sort());
  for (const g of Object.values(p.graficos)) {
    assert.ok(g.opcao.aria.enabled);
    assert.ok(g.opcao.aria.label.description.length > 20, g.nome);
  }
  // o mesmo resumo aparece escrito na pagina, antes do grafico
  assert.match(p.html, /class="resumo-grafico">4 papers em 2 dias com publicação/);
  assert.match(p.html, /ver os números em tabela/);
});

test('o clique numa barra do lote diario recorta pelo dia, e os outros dias so esmaecem', () => {
  const p = painel({ hash: '#aba=panorama' });
  p.clicaGrafico('volume', { dataIndex: 1 });
  assert.match(p.recorte, /^2 de 4 · 02\/09$/);
  const fora = p.graficos.volume.opcao.series[0].data;
  assert.equal(fora[0].value, 1);               // 01/09 continua contado...
  assert.equal(fora[0].itemStyle.opacity, 0.28); // ...e esmaecido
  assert.equal(fora[1].itemStyle, undefined);
  p.clicaGrafico('volume', { dataIndex: 1 });
  assert.match(p.recorte, /sem recorte/);
});

test('o clique na barra de regra e na celula da matriz recortam como as pilulas', () => {
  const p = painel({ hash: '#aba=panorama' });
  p.clicaGrafico('regras', { componentType: 'series', dataIndex: 0 });
  assert.match(p.recorte, /regra: /);
  p.clicaGrafico('regras', { componentType: 'series', dataIndex: 0 });
  p.clicaGrafico('matriz', { value: [0, 0, 1] });   // coluna 0, linha 0 = Proposta x vertente mais frequente
  assert.ok(p.acesa('Proposta'));
  assert.match(p.recorte, /dominante: /);
});

test('o ganho de votos e a maturacao leem o que veio pre-agregado', () => {
  const p = painel({ hash: '#aba=panorama' });
  const ganho = p.graficos.ganho.opcao;
  assert.equal(JSON.stringify(ganho.series[1].data.map((d) => d.value)), '[28,4]');
  // a maturacao precisa de 5 papers por idade: com 1 so, sai o aviso, sem grafico
  assert.equal(p.graficos.maturacao, undefined);
  assert.match(p.html, /Amostra insuficiente/);
});

test('o recorte vai para a URL e volta dela', () => {
  const p = painel();
  p.clicaPilula('Achado empírico');
  p.aba('Panorama');
  assert.equal(p.hash, '#aba=panorama&natureza=achado_empirico');
  const q = painel({ hash: p.hash });
  assert.ok(q.acesa('Achado empírico'));
  assert.match(q.html, /Natureza × vertente/);
});

test('link para um paper abre o card no dia dele', () => {
  const p = painel({ hash: '#paper=a1' });
  assert.equal(p.diaAtual, '2026-09-01');
  assert.match(p.html, /POR QUE ESTA CLASSIFICAÇÃO/);
});

test('sem as fichas carregadas, o card aberto avisa em vez de dizer que nao ha ficha', () => {
  const dados = structuredClone(DADOS);
  delete dados.fichas;
  dados.papers[0].f = 1;
  const p = montarPainel(dados, { hash: '#paper=a1' });
  assert.match(p.html, /Carregando a ficha…/);
  assert.doesNotMatch(p.html, /sem ficha gerada/);
});
