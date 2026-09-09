/* As contagens da barra de filtro descrevem o RECORTE, nao a janela.
 *
 * Antes elas saiam todas de `DADOS.papers` inteiro: marcado `estrito`, o menu
 * de area seguia anunciando "Modelo & treino 524" quando o recorte tinha 7, e
 * duas das areas com mais papers da janela nao tinham estrito nenhum. Agora
 * cada seletor se conta no recorte com a SUA dimensao solta - e essa solta e
 * metade do contrato: sem ela, marcar a primeira area zeraria as demais
 * linhas do proprio menu e a segunda ficaria inalcancavel.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { montarPainel } from './dom_painel.mjs';

const VERTENTES = ['Medir', 'Treinar'];
const SUBAREAS = { 'Benchmark': '', 'Pré-treino': '', 'Difusão': '' };

function paper(id, { d = '2026-09-01', v, a, sa, vt, org = null }) {
  return {
    id, t: 'Paper ' + id, d, v, rf: v === 'fora' ? 'treino_ou_postreino' : null,
    art: false, a, sa, vt, oa: 0, pp: 0, u: 10, c: 1, gs: 0, org,
    na: 1, nv: 0, url: 'https://x/' + id, f: 0,
    ...(v === 'fora' ? {} : { j: 'motivo', h: 0, fr: 0, cr: ['benchmark'] }),
  };
}

/* Alfa: 3 estritos, 1 amplo, 2 fora.  Beta: 4 fora, nenhum aprovado.
   `beta` e o caso que motivou o ticket - a area grande da janela que some
   inteira quando o recorte vira estrito. */
const PAPERS = [
  paper('a1', { v: 'estrito', a: 'Alfa', sa: 'Benchmark', vt: ['Medir'], org: 'globo' }),
  paper('a2', { v: 'estrito', a: 'Alfa', sa: 'Benchmark', vt: ['Medir'], org: 'globo' }),
  paper('a3', { v: 'estrito', a: 'Alfa', sa: 'Pré-treino', vt: ['Treinar', 'Medir'], org: null }),
  paper('a4', { v: 'amplo', a: 'Alfa', sa: 'Benchmark', vt: ['Medir'], org: 'acme' }),
  paper('a5', { v: 'fora', a: 'Alfa', sa: 'Pré-treino', vt: ['Treinar'], org: 'acme' }),
  paper('a6', { v: 'fora', a: 'Alfa', sa: 'Pré-treino', vt: ['Treinar'], org: 'acme', d: '2026-09-02' }),
  paper('b1', { v: 'fora', a: 'Beta', sa: 'Difusão', vt: ['Treinar'], org: 'acme' }),
  paper('b2', { v: 'fora', a: 'Beta', sa: 'Difusão', vt: ['Treinar'], org: 'acme' }),
  paper('b3', { v: 'fora', a: 'Beta', sa: 'Difusão', vt: ['Treinar'], org: null }),
  paper('b4', { v: 'fora', a: 'Beta', sa: 'Difusão', vt: ['Medir'], org: null, d: '2026-09-02' }),
];

const DADOS = {
  gerado: '2026-09-03T08:00:00', modeloA: 'm', modeloB: 'm',
  janela: 90, pendentes: 0, diasHall: 90, diasRefresh: 90,
  areas: [{ a: 'Alfa', def: '' }, { a: 'Beta', def: '' }],
  subdef: SUBAREAS,
  vertentes: VERTENTES.map((v) => ({ v, def: '' })),
  papers: PAPERS, fichas: [], serie: {}, hall: [],
};

const painel = () => montarPainel(structuredClone(DADOS));

test('sem recorte, o menu conta a janela inteira', () => {
  assert.deepEqual(painel().contagens('ÁREA'), { Alfa: 6, Beta: 4 });
});

test('marcado estrito, area/sub-area/vertente contam so os estritos', () => {
  const p = painel();
  p.clicaVeredito('estrito');
  assert.deepEqual(p.contagens('ÁREA'), { Alfa: 3, Beta: 0 });
  assert.deepEqual(p.contagens('SUB-ÁREA'), { Benchmark: 2, 'Pré-treino': 1, Difusão: 0 });
  // por DOMINANTE: a3 tem ['Treinar','Medir'] e conta em Treinar
  assert.deepEqual(p.contagens('VERTENTE'), { Medir: 2, Treinar: 1 });
});

test('a linha que zerou fica no menu, e cai para o fim', () => {
  const p = painel();
  p.clicaVeredito('estrito');
  assert.deepEqual(p.menu('ÁREA').map((l) => l.label), ['todas', 'Alfa', 'Beta']);
  assert.deepEqual(
    p.menu('SUB-ÁREA').map((l) => l.label),
    ['todas', 'Benchmark', 'Pré-treino', 'Difusão'],
  );
});

test('o menu nao se apaga: a dimensao se conta com ela mesma solta', () => {
  // Sem isso, marcar Alfa zeraria Beta no proprio menu de area e nao haveria
  // como marcar a segunda - o motivo de `filtrados` aceitar `exceto`.
  const p = painel();
  p.clicaItem('ÁREA', 'Alfa');
  assert.deepEqual(p.contagens('ÁREA'), { Alfa: 6, Beta: 4 });
  // as outras dimensoes, essas sim, ja respondem ao recorte por Alfa
  assert.deepEqual(p.contagens('SUB-ÁREA'), { 'Pré-treino': 3, Benchmark: 3, Difusão: 0 });
});

test('os chips de veredito respondem ao recorte de tema', () => {
  const p = painel();
  p.clicaItem('ÁREA', 'Beta');
  assert.equal(p.contaVeredito('fora'), 4);
  assert.equal(p.contaVeredito('estrito'), 0);
  assert.equal(p.contaVeredito('amplo'), 0);
});

test('o chip de veredito se conta com o veredito solto', () => {
  // senao `estrito` marcado leria "estrito 3, amplo 0, fora 0" e o painel
  // perderia o tamanho dos outros dois baldes justamente ao compara-los
  const p = painel();
  p.clicaVeredito('estrito');
  assert.equal(p.contaVeredito('estrito'), 3);
  assert.equal(p.contaVeredito('amplo'), 1);
  assert.equal(p.contaVeredito('fora'), 6);
});

test('organizacao e a excecao: a que zera sai do menu', () => {
  const p = painel();
  assert.deepEqual(p.contagens('ORGANIZAÇÃO'), { acme: 5, globo: 2, 'sem organização': 3 });
  p.clicaVeredito('estrito');
  // acme so tem amplo e fora; sem organizacao so tem a3
  assert.deepEqual(p.contagens('ORGANIZAÇÃO'), { globo: 2, 'sem organização': 1 });
});

test('a organizacao MARCADA nao some do menu, mesmo zerada', () => {
  const p = painel();
  p.clicaItem('ORGANIZAÇÃO', 'acme');
  p.clicaVeredito('estrito');
  assert.deepEqual(p.contagens('ORGANIZAÇÃO'), { acme: 0, globo: 2, 'sem organização': 1 });
});

test('o menu de dia conta o recorte e mantem o dia que zerou', () => {
  const p = painel();
  assert.deepEqual(p.contagens('DIA'), { '01/09': 8, '02/09': 2 });
  p.clicaVeredito('estrito');
  assert.deepEqual(p.contagens('DIA'), { '01/09': 3, '02/09': 0 });
});
