// Pontua as sessoes de uso simulado: acerto (palavras do gabarito na resposta),
// passos, tempo estimado e acerto no primeiro clique.
// Tempo: modelo KLM (Card, Moran e Newell): decidir 1,35 s; apontar 1,1 s;
// clicar 0,2 s; tecla 0,28 s; rolar 0,6 s. E estimativa, nao cronometro: serve
// para comparar duas versoes com a mesma regua.
//   node medir/pontuar.mjs --saida medir/saida/rodada-0 --primeiro medir/primeiro-v0.json
import { readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { arg } from './lib.mjs';

const KLM = { clicar: 1.35 + 1.1 + 0.2, passar: 1.35 + 1.1, rolar: 1.35 + 0.6, tecla: 1.35 + 0.28 };
const saida = resolve(arg('saida', 'medir/saida/atual'));
const T = JSON.parse(readFileSync(resolve('medir/tarefas.json'), 'utf8'));
const prim = JSON.parse(readFileSync(resolve(arg('primeiro', 'medir/primeiro.json')), 'utf8'));
const linhas = [];
for (const f of readdirSync(saida).filter((x) => /^uso-.*\.jsonl$/.test(x))) {
  const ev = readFileSync(join(saida, f), 'utf8').trim().split('\n').filter(Boolean).map((l) => JSON.parse(l));
  const porT = {};
  const resps = {};
  for (const e of ev) { if (!e.tarefa) continue; if (e.tipo === 'responder') { resps[e.tarefa] = e; continue; } if (e.tipo === 'iniciar') porT[e.tarefa] = []; (porT[e.tarefa] ||= []).push(e); }
  for (const [id, es] of Object.entries(porT)) {
    const t = T[id]; if (!t) continue;
    const resp = resps[id];
    const ate = es;
    const acoes = ate.filter((e) => KLM[e.tipo]);
    const texto = resp?.resposta || '';
    const desistiu = /^desisto/i.test(texto) || !resp;
    let certo = !desistiu && t.acerto.every((r) => new RegExp(r, 'i').test(texto));
    if (certo && t.fim) certo = new RegExp(t.fim).test(resp.url || '');
    const c1 = acoes.find((e) => e.tipo === 'clicar');
    const alvo = c1 ? `${c1.alvo?.regiao || ''} | ${c1.alvo?.nome || ''} | ${c1.alvo?.canvas ? 'canvas' : ''}` : '';
    const p1 = c1 ? new RegExp(prim[id] || '$^', 'i').test(alvo) : certo;
    linhas.push({ tarefa: id, prio: t.prio, largura: es[0].largura, certo, desistiu, passos: acoes.length,
      cliques: acoes.filter((e) => e.tipo === 'clicar').length, rolagens: acoes.filter((e) => e.tipo === 'rolar').length,
      tempo: +acoes.reduce((a, e) => a + KLM[e.tipo], 0).toFixed(1), primeiro: p1, alvo1: alvo.slice(0, 70), resposta: texto.slice(0, 160) });
  }
}
linhas.sort((a, b) => a.largura - b.largura || +a.tarefa.slice(1) - +b.tarefa.slice(1));
const resumo = {};
for (const larg of [...new Set(linhas.map((l) => l.largura))]) {
  const ls = linhas.filter((l) => l.largura === larg);
  const med = (xs) => { const a = [...xs].sort((x, y) => x - y); return a.length ? (a.length % 2 ? a[a.length >> 1] : (a[a.length / 2 - 1] + a[a.length / 2]) / 2) : null; };
  resumo[larg] = { tarefas: ls.length, acerto: ls.filter((l) => l.certo).length, primeiroClique: ls.filter((l) => l.primeiro).length,
    passosTotal: ls.reduce((a, l) => a + l.passos, 0), passosMediana: med(ls.map((l) => l.passos)), tempoTotal: +ls.reduce((a, l) => a + l.tempo, 0).toFixed(0), tempoMediana: med(ls.map((l) => l.tempo)) };
}
writeFileSync(join(saida, 'uso.json'), JSON.stringify({ resumo, linhas }, null, 1));
console.table(linhas.map(({ resposta, alvo1, desistiu, ...l }) => l));
console.table(resumo);
