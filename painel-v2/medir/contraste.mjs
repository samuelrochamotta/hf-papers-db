// Contraste dos pares de tokens que o painel usa de fato: texto sobre cada
// fundo (WCAG 1.4.3, minimo 4,5:1) e borda de controle, foco e marca de
// grafico sobre a superficie (WCAG 1.4.11, minimo 3:1). O axe mede o que esta
// na tela; esta tabela garante os pares que uma tela qualquer pode combinar.
//   node medir/contraste.mjs --dir <build> [--id periodico|oficina]
import { writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { chromium, servir, abrir, TEMAS, BUILD, arg, pasta } from './lib.mjs';

const FUNDOS = ['bg', 'surface', 'sunk', 'hover', 'raise'];
const TEXTO = [
  ...['ink', 'ink2', 'muted'].flatMap((t) => FUNDOS.map((f) => [t, f])),
  ['on-accent', 'accent'], ['alert', 'bg'], ['alert', 'surface'], ['alert', 'alert-soft'], ['ink', 'alert-soft'], ['ink2', 'alert-soft'],
];
const GRAFICO = [
  ...['line-strong', 'focus', 'accent'].flatMap((t) => ['bg', 'surface'].map((f) => [t, f])),
  ...['sol-forte', 'sol-firme', 'sol-basico', 'sol-fragil', 'sol-nada', 'res-ganha', 'res-ruido', 'res-perde', 'cmp-1', 'cmp-2', 'cmp-3'].map((t) => [t, 'surface']),
];
const lin = (c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
const lum = (c) => 0.2126 * lin(c[0] / 255) + 0.7152 * lin(c[1] / 255) + 0.0722 * lin(c[2] / 255);
const razao = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };

const dir = resolve(arg('dir', BUILD));
const saida = pasta(resolve(arg('saida', 'medir/saida/atual')));
const s = await servir(dir), b = await chromium.launch();
const linhas = []; let falhas = 0;
for (const tema of TEMAS) {
  const { page, ctx } = await abrir(b, { url: s.url, tema });
  const nomes = [...new Set([...TEXTO, ...GRAFICO].flat())];
  const tok = await page.evaluate((ns) => {
    const cs = getComputedStyle(document.documentElement);
    const c = document.createElement('canvas'); c.width = c.height = 1; const g = c.getContext('2d', { willReadFrequently: true });
    const o = {};
    for (const n of ns) { g.clearRect(0, 0, 1, 1); g.fillStyle = cs.getPropertyValue(`--${n}`).trim(); g.fillRect(0, 0, 1, 1); o[n] = [...g.getImageData(0, 0, 1, 1).data].slice(0, 3); }
    return o;
  }, nomes);
  for (const [pares, minimo, tipo] of [[TEXTO, 4.5, 'texto'], [GRAFICO, 3, 'grafico']]) for (const [a, f] of pares) {
    const r = razao(tok[a], tok[f]), ok = r >= minimo;
    if (!ok) falhas++;
    linhas.push({ tema, tipo, par: `${a} / ${f}`, razao: +r.toFixed(2), minimo, ok });
  }
  await ctx.close();
}
writeFileSync(join(saida, 'contraste.json'), JSON.stringify(linhas, null, 1));
const pior = (tipo) => linhas.filter((l) => l.tipo === tipo).sort((x, y) => x.razao - y.razao)[0];
console.table(linhas.filter((l) => !l.ok));
console.log(`contraste: ${linhas.length} pares, ${falhas} abaixo do minimo; pior texto ${pior('texto').par} ${pior('texto').razao} (${pior('texto').tema}); pior grafico ${pior('grafico').par} ${pior('grafico').razao} (${pior('grafico').tema})`);
await b.close(); s.fechar();
process.exitCode = falhas ? 1 : 0;
