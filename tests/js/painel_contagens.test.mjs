/* O recorte do painel no regime do ADR 004.
 *
 * Tres contratos que o navegador cumpre sozinho e que nenhum teste de Python
 * enxerga:
 *
 * 1. As contagens da barra de filtro descrevem o RECORTE, nao a janela - cada
 *    seletor se conta com a SUA dimensao solta, senao marcar a primeira area
 *    zeraria as demais e a segunda ficaria inalcancavel.
 * 2. O perfil e um preset de degraus: ele marca as pilulas de degrau, que
 *    continuam editaveis, e degrau/natureza/marca so recortam aprovados.
 * 3. A aba Aprovados pagina por DIA e ordena pela escada, depois pelo voto; a
 *    busca alcanca o texto da ficha.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { montarPainel } from './dom_painel.mjs';

const VERTENTES = ['Medir', 'Treinar'];
const SUBAREAS = { 'Benchmark': '', 'Pré-treino': '', 'Difusão': '' };

function paper(id, { d = '2026-09-01', v = 'aprovado', pr = 'implementar', nt = 'proposta', a, sa, vt, org = null, u = 10, extra = {} }) {
  const base = {
    id, t: 'Paper ' + id, d, v, rf: v === 'fora' ? 'geracao_de_midia' : null,
    a, sa, vt, oa: 0, pp: 0, u, c: 1, gs: 0, org,
    na: 1, nv: 0, url: 'https://x/' + id, f: 0,
  };
  if (v === 'aprovado') Object.assign(base, { j: 'motivo', h: 0, pr, nt, ao: 0 });
  return { ...base, ...extra };
}

/* Alfa: 3 em `implementar`/`nenhum`, 1 em `treino`, 2 fora.
   Beta: 4 fora, nenhum aprovado. */
const PAPERS = [
  paper('a1', { pr: 'nenhum', a: 'Alfa', sa: 'Benchmark', vt: ['Medir'], org: 'globo', u: 5 }),
  paper('a2', { pr: 'implementar', a: 'Alfa', sa: 'Benchmark', vt: ['Medir'], org: 'globo', u: 50 }),
  paper('a3', { pr: 'implementar', nt: 'achado_empirico', a: 'Alfa', sa: 'Pré-treino', vt: ['Treinar', 'Medir'], org: null, u: 7,
    extra: { pc: 'usar a mesma temperatura no rollout e na avaliacao' } }),
  paper('a4', { pr: 'treino', a: 'Alfa', sa: 'Benchmark', vt: ['Medir'], org: 'acme', u: 99, extra: { ao: 1, gh: 'https://github.com/x/y' } }),
  paper('a5', { v: 'fora', a: 'Alfa', sa: 'Pré-treino', vt: ['Treinar'], org: 'acme' }),
  paper('a6', { v: 'fora', a: 'Alfa', sa: 'Pré-treino', vt: ['Treinar'], org: 'acme', d: '2026-09-02' }),
  paper('b1', { v: 'fora', a: 'Beta', sa: 'Difusão', vt: ['Treinar'], org: 'acme' }),
  paper('b2', { v: 'fora', a: 'Beta', sa: 'Difusão', vt: ['Treinar'], org: 'acme' }),
  paper('b3', { v: 'fora', a: 'Beta', sa: 'Difusão', vt: ['Treinar'], org: null }),
  paper('b4', { v: 'fora', a: 'Beta', sa: 'Difusão', vt: ['Medir'], org: null, d: '2026-09-02' }),
];

const DEGRAUS = [
  { k: 'nenhum', r: 'Nenhum' }, { k: 'implementar', r: 'Implementar' },
  { k: 'acesso_interno', r: 'Acesso interno' }, { k: 'treino', r: 'Treino' },
  { k: 'sem_acao', r: 'Sem ação' },
];

const DADOS = {
  gerado: '2026-09-03T08:00:00', modeloA: 'm', modeloB: 'm',
  janela: 90, pendentes: 0, diasHall: 90, diasRefresh: 90,
  areas: [{ a: 'Alfa', def: '' }, { a: 'Beta', def: '' }],
  subdef: SUBAREAS,
  vertentes: VERTENTES.map((v) => ({ v, def: '' })),
  degraus: DEGRAUS.map((d) => ({ ...d, def: '' })),
  naturezas: [
    { k: 'proposta', r: 'Proposta', def: '' }, { k: 'achado_empirico', r: 'Achado empírico', def: '' },
    { k: 'teoria', r: 'Teoria', def: '' }, { k: 'panorama', r: 'Panorama', def: '' },
  ],
  perfis: [
    { p: 'produto', r: 'Produto', d: ['implementar', 'nenhum'] },
    { p: 'pesquisa_treino', r: 'Treino/pesquisa', d: ['acesso_interno', 'sem_acao', 'treino'] },
  ],
  papers: PAPERS,
  fichas: [{ p: 'a2', ach: 'mede o cache de prefixo', pn: '', pm: '', imp: 'Você reaproveita o prefixo. Depois mede.', ex: 'e', res: 'r' }],
  serie: {}, hall: [],
};

const painel = (opcoes) => montarPainel(structuredClone(DADOS), opcoes);
function emTudo(p) { p.clicaPilula('Tudo'); return p; }

// ══════════════ contagens do recorte ══════════════

test('sem recorte, o menu conta a janela inteira', () => {
  assert.deepEqual(emTudo(painel()).contagens('ÁREA'), { Alfa: 6, Beta: 4 });
});

test('o perfil Produto e o inicial e nao apaga os descartados', () => {
  // degrau so recorta aprovado: a4 (treino) sai, os seis `fora` ficam
  const p = painel();
  assert.ok(p.acesa('Produto'));
  assert.deepEqual(p.contagens('ÁREA'), { Alfa: 5, Beta: 4 });
});

test('a linha que zerou fica no menu, e cai para o fim', () => {
  const p = emTudo(painel());
  p.aba('Panorama');       // o filtro de veredito so existe la
  p.clicaPilula('aprovado');
  assert.deepEqual(p.menu('ÁREA').map((l) => l.label), ['todas', 'Alfa', 'Beta']);
  assert.deepEqual(p.contagens('ÁREA'), { Alfa: 4, Beta: 0 });
});

test('o menu nao se apaga: a dimensao se conta com ela mesma solta', () => {
  const p = emTudo(painel());
  p.clicaItem('ÁREA', 'Alfa');
  assert.deepEqual(p.contagens('ÁREA'), { Alfa: 6, Beta: 4 });
  assert.deepEqual(p.contagens('SUB-ÁREA'), { 'Pré-treino': 3, Benchmark: 3, Difusão: 0 });
});

test('organizacao e a excecao: a que zera sai do menu', () => {
  const p = emTudo(painel());
  assert.deepEqual(p.contagens('ORGANIZAÇÃO'), { acme: 5, globo: 2, 'sem organização': 3 });
  p.aba('Panorama');
  p.clicaPilula('aprovado');
  // acme so tem a4 aprovado; sem organizacao so tem a3
  assert.deepEqual(p.contagens('ORGANIZAÇÃO'), { globo: 2, acme: 1, 'sem organização': 1 });
});

test('o menu de dia conta o recorte e mantem o dia que zerou', () => {
  const p = emTudo(painel());
  assert.deepEqual(p.contagens('DIA'), { '01/09': 8, '02/09': 2 });
  p.aba('Panorama');
  p.clicaPilula('aprovado');
  assert.deepEqual(p.contagens('DIA'), { '01/09': 4, '02/09': 0 });
});

// ══════════════ perfil e degraus ══════════════

test('o perfil marca as pilulas de degrau, que continuam editaveis', () => {
  const p = painel();
  assert.ok(p.acesa('Nenhum') && p.acesa('Implementar'));
  assert.ok(!p.acesa('Treino'));
  p.clicaPilula('Treino/pesquisa');
  assert.ok(p.acesa('Treino') && p.acesa('Acesso interno') && p.acesa('Sem ação'));
  assert.ok(!p.acesa('Implementar'));
  // editar uma pilula tira o perfil de cena: o recorte e "personalizado"
  p.clicaPilula('Implementar');
  assert.ok(!p.acesa('Treino/pesquisa'));
  assert.match(p.html, /personalizado/);
});

test('cada pilula de degrau conta so aprovados, com o degrau solto', () => {
  const p = painel();
  assert.equal(p.contaPilula('Nenhum'), 1);
  assert.equal(p.contaPilula('Implementar'), 2);
  assert.equal(p.contaPilula('Treino'), 1);
  assert.equal(p.contaPilula('Acesso interno'), 0);
  // o perfil conta o que traria: Produto 3, Treino/pesquisa 1, Tudo 4
  assert.equal(p.contaPilula('Produto'), 3);
  assert.equal(p.contaPilula('Treino/pesquisa'), 1);
  assert.equal(p.contaPilula('Tudo'), 4);
});

test('o perfil escolhido sobrevive no storage', () => {
  const guardado = {};
  const storage = { getItem: (k) => guardado[k] ?? null, setItem: (k, v) => { guardado[k] = v; } };
  painel({ storage }).clicaPilula('Treino/pesquisa');
  assert.equal(guardado['hfpapers.perfil'], 'pesquisa_treino');
  const reaberto = painel({ storage });
  assert.ok(reaberto.acesa('Treino/pesquisa'));
  assert.deepEqual(reaberto.cards, ['a4']);
});

test('natureza e marca recortam os aprovados', () => {
  const p = emTudo(painel());
  p.clicaPilula('Achado empírico');
  assert.deepEqual(p.cards, ['a3']);
  p.clicaPilula('Achado empírico');
  p.clicaPilula('artefato aberto');
  assert.deepEqual(p.cards, ['a4']);
  // a marca se conta com as marcas soltas: diz o que ela traria sozinha
  assert.equal(p.contaPilula('contradiz prática'), 1);
});

// ══════════════ aba Aprovados ══════════════

test('dentro do dia a ordem e a escada, depois o voto', () => {
  // a4 (treino, 99 votos) vem depois de a1 (nenhum, 5 votos): o degrau manda
  const p = emTudo(painel());
  assert.deepEqual(p.cards, ['a1', 'a2', 'a3', 'a4']);
});

test('a aba Aprovados pagina por dia, do mais recente ao mais antigo', () => {
  const dados = structuredClone(DADOS);
  dados.papers.push(paper('c1', { d: '2026-09-02', pr: 'nenhum', a: 'Alfa', sa: 'Benchmark', vt: ['Medir'] }));
  const p = montarPainel(dados);
  assert.equal(p.diaAtual, '2026-09-02');
  assert.deepEqual(p.cards, ['c1']);
  p.navegaDia('← dia anterior');
  assert.equal(p.diaAtual, '2026-09-01');
  assert.deepEqual(p.cards, ['a1', 'a2', 'a3']);   // so o dia visivel e desenhado
  p.navegaDia('dia seguinte →');
  assert.equal(p.diaAtual, '2026-09-02');
});

test('a busca alcanca o texto da ficha', () => {
  const p = emTudo(painel());
  p.busca('cache de prefixo');
  assert.deepEqual(p.cards, ['a2']);
  p.busca('globo');
  assert.deepEqual(p.cards, ['a1', 'a2']);
  p.busca('');
  assert.equal(p.cards.length, 4);
});

test('o card recolhido traz a primeira frase do que muda para voce e as marcas', () => {
  const p = emTudo(painel());
  assert.match(p.html, /Você reaproveita o prefixo\./);
  assert.doesNotMatch(p.html, /Depois mede\./);
  assert.match(p.html, /≠ prática/);
  assert.match(p.html, /href="https:\/\/github.com\/x\/y"[^>]*>artefato ↗/);
});

test('aprovado nao classificado aparece com pilula propria, fora dos perfis', () => {
  const dados = structuredClone(DADOS);
  // o contrato de gerar_painel.py: `pr` com o marcador, `nt` nulo
  const legado = paper('z1', { pr: '__sem-degrau__', nt: null, a: 'Alfa', sa: 'Benchmark', vt: ['Medir'] });
  dados.papers.push(legado);
  const p = montarPainel(dados);
  assert.ok(!p.cards.includes('z1'));               // Produto nao o inclui
  assert.equal(p.contaPilula('não classificado'), 1);
  p.clicaPilula('Tudo');
  assert.ok(p.cards.includes('z1'));
  assert.match(p.html, /ainda são do regime anterior/);
});

test('o registro historico segue os degraus do perfil', () => {
  const dados = structuredClone(DADOS);
  const entrada = (id, pr, u) => ({ id, t: 'H ' + id, d: '2026-06-01', v: 'aprovado', pr, nt: 'proposta', u, f: 0, j: 'm', h: 0, url: 'u' });
  dados.hall = [{
    per: '2026-T2', rot: '2º trimestre de 2026', ini: '2026-04-01', fim: '2026-06-30',
    n: 3, na: 3, nd: 0, nx: 0, cons: 0, nad: { implementar: 2, treino: 1 },
    ap: [entrada('h1', 'implementar', 5), entrada('h2', 'treino', 90), entrada('h3', 'implementar', 30)],
    de: [],
  }];
  const p = montarPainel(dados);
  p.aba('Registro histórico');
  assert.deepEqual(p.cards, ['h3', 'h1']);
  assert.match(p.html, /2 de 2 aprovados/);
  p.clicaPilula('Tudo');
  assert.deepEqual(p.cards, ['h2', 'h3', 'h1']);
});
