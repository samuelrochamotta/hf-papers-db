// Pontua o experimento E4 (marca de prova): cada item certo vale 1; "nao_sei" conta a parte.
// uso: node medir/marca/pontuar.mjs <pasta com as respostas> [condicoes separadas por virgula]
import fs from 'node:fs';
const dir = process.argv[2];
const A = { Integrar: { Forte: 1, Firme: 3, 'Básica': 1, 'Frágil': 2, 'Não lida': 2 }, Reimplementar: { Forte: 1, Firme: 2, 'Básica': 1, 'Frágil': 0, 'Não lida': 3 }, 'Só informa': { Forte: 0, Firme: 2, 'Básica': 1, 'Frágil': 0, 'Não lida': 3 } };
const G = { DreamX: 'Forte', SplatAnything: 'Firme', 'Sage-Taiyi': 'Forte', "Don't Just Trust Your": 'Firme', 'P2-MOPD': 'Firme', 'Think Less Locally': 'Básica', 'Confucius4-R2T2': 'Firme', MoviEdit: 'Forte', SLA: 'Forte', 'Wave Forcing': 'Firme', 'Few-Step Streaming Video': 'Forte', CoworkOS: 'Frágil', 'From Pixels to Actions': 'Firme', 'Harness-S': 'Firme', 'Route Anything': 'Básica' };
const linhas = [];
for (const marca of ['cor', 'cheio']) for (const cond of (process.argv[3] || 'normal,escuro,deuteranopia,celular').split(',')) {
  const f = `${dir}/${marca}-${cond}.json`;
  if (!fs.existsSync(f)) { linhas.push({ marca, cond, falta: true }); continue; }
  const r = JSON.parse(fs.readFileSync(f, 'utf8'));
  let ca = 0, na = 0, cg = 0, ng = 0; const erros = [];
  for (const [l, niv] of Object.entries(A)) for (const [k, v] of Object.entries(niv)) { const x = r.adocao?.[l]?.[k]; if (x === 'nao_sei') na++; else if (+x === v) ca++; else erros.push(`${l}/${k}: ${x} (certo ${v})`); }
  for (const [p, v] of Object.entries(G)) { const x = r.ganho?.[p]; if (x === 'nao_sei') ng++; else if (x === v) cg++; else erros.push(`${p}: ${x} (certo ${v})`); }
  linhas.push({ marca, cond, adocao: `${ca}/15`, ganho: `${cg}/15`, certos: ca + cg, naoSei: na + ng, erros: erros.length, det: erros.slice(0, 6).join(' | '), dif: (r.dificuldade || '').slice(0, 160) });
}
console.table(linhas.map(({ det, dif, ...x }) => x));
for (const l of linhas) if (l.det || l.dif) console.log(`${l.marca}-${l.cond}: ${l.det}\n   "${l.dif}"`);
for (const m of ['cor', 'cheio']) { const ls = linhas.filter((l) => l.marca === m && !l.falta); console.log(m, 'certos', ls.reduce((s, l) => s + l.certos, 0), 'de', ls.length * 30, '| nao sei', ls.reduce((s, l) => s + l.naoSei, 0), '| erros', ls.reduce((s, l) => s + l.erros, 0)); }
