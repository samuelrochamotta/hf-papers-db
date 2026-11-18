// Daltonismo: (1) contas na paleta dos graficos, lida dos tokens CSS da pagina:
// para protanopia, deuteranopia e tritanopia (Machado et al. 2009, severidade
// 1), a menor diferenca de cor (CIEDE2000) entre duas categorias da mesma
// paleta e o contraste de cada cor contra a superficie; (2) capturas com a
// emulacao do Chrome, para olhar.
//   node medir/daltonismo.mjs --paletas medir/paletas-v0.json
import { readFileSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { chromium, servir, abrir, TEMAS, BUILD, arg, pasta } from './lib.mjs';

const MINIMO_DE = +arg('minimo', 10);   // abaixo disso duas categorias se confundem
const MINIMO_CONTRASTE = 3;             // WCAG 1.4.11, objeto grafico contra o fundo
const M = {
  normal: [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
  protanopia: [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]],
  deuteranopia: [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]],
  tritanopia: [[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602], [0.004733, 0.691367, 0.303900]],
};
const lin = (c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
const corte = (x) => Math.min(1, Math.max(0, x));
const rgb = (s) => { const m = s.match(/[\d.]+/g).map(Number); return s.startsWith('#') ? [1, 3, 5].map((i) => parseInt(s.slice(i, i + 2), 16) / 255) : m.slice(0, 3).map((v) => v / 255); };
const simula = (c, m) => { const l = c.map(lin); return m.map((r) => corte(r[0] * l[0] + r[1] * l[1] + r[2] * l[2])); };
const lum = (l) => 0.2126 * l[0] + 0.7152 * l[1] + 0.0722 * l[2];
const contraste = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
function lab(l) {
  const X = (0.4124564 * l[0] + 0.3575761 * l[1] + 0.1804375 * l[2]) / 0.95047, Y = 0.2126729 * l[0] + 0.7151522 * l[1] + 0.072175 * l[2], Z = (0.0193339 * l[0] + 0.119192 * l[1] + 0.9503041 * l[2]) / 1.08883;
  const f = (t) => (t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116);
  return [116 * f(Y) - 16, 500 * (f(X) - f(Y)), 200 * (f(Y) - f(Z))];
}
function de2000([L1, a1, b1], [L2, a2, b2]) {
  const rad = Math.PI / 180, C1 = Math.hypot(a1, b1), C2 = Math.hypot(a2, b2), Cm = (C1 + C2) / 2;
  const G = 0.5 * (1 - Math.sqrt(Cm ** 7 / (Cm ** 7 + 25 ** 7)));
  const ap1 = a1 * (1 + G), ap2 = a2 * (1 + G), Cp1 = Math.hypot(ap1, b1), Cp2 = Math.hypot(ap2, b2);
  const h = (b, a) => { const v = Math.atan2(b, a) / rad; return v < 0 ? v + 360 : v; };
  const hp1 = Cp1 ? h(b1, ap1) : 0, hp2 = Cp2 ? h(b2, ap2) : 0;
  const dL = L2 - L1, dC = Cp2 - Cp1;
  let dh = hp2 - hp1; if (Cp1 * Cp2 === 0) dh = 0; else if (dh > 180) dh -= 360; else if (dh < -180) dh += 360;
  const dH = 2 * Math.sqrt(Cp1 * Cp2) * Math.sin((dh * rad) / 2);
  const Lm = (L1 + L2) / 2, Cpm = (Cp1 + Cp2) / 2;
  let hm = hp1 + hp2; if (Cp1 * Cp2 !== 0) hm = Math.abs(hp1 - hp2) <= 180 ? hm / 2 : (hm + (hm < 360 ? 360 : -360)) / 2;
  const T = 1 - 0.17 * Math.cos((hm - 30) * rad) + 0.24 * Math.cos(2 * hm * rad) + 0.32 * Math.cos((3 * hm + 6) * rad) - 0.2 * Math.cos((4 * hm - 63) * rad);
  const Sl = 1 + (0.015 * (Lm - 50) ** 2) / Math.sqrt(20 + (Lm - 50) ** 2), Sc = 1 + 0.045 * Cpm, Sh = 1 + 0.015 * Cpm * T;
  const Rt = -2 * Math.sqrt(Cpm ** 7 / (Cpm ** 7 + 25 ** 7)) * Math.sin(60 * Math.exp(-(((hm - 275) / 25) ** 2)) * rad);
  return Math.sqrt((dL / Sl) ** 2 + (dC / Sc) ** 2 + (dH / Sh) ** 2 + Rt * (dC / Sc) * (dH / Sh));
}

const dir = resolve(arg('dir', BUILD));
const saida = pasta(resolve(arg('saida', 'medir/saida/atual'), 'daltonismo'));
const conf = JSON.parse(readFileSync(resolve(arg('paletas', 'medir/paletas.json')), 'utf8'));
const s = await servir(dir);
const b = await chromium.launch();
const linhas = []; let falhas = 0;
for (const tema of TEMAS) {
  const { page, ctx } = await abrir(b, { url: s.url, tema });
  const nomes = [conf.superficie, ...Object.values(conf.paletas).flat()];
  const tok = await page.evaluate((ns) => {
    // resolve o token para rgb pintando um canvas (cobre oklch, color-mix)
    const cs = getComputedStyle(document.documentElement);
    const c = document.createElement('canvas'); c.width = c.height = 1; const g = c.getContext('2d', { willReadFrequently: true });
    const o = {};
    for (const n of ns) { g.clearRect(0, 0, 1, 1); g.fillStyle = cs.getPropertyValue(`--${n}`).trim(); g.fillRect(0, 0, 1, 1); const d = g.getImageData(0, 0, 1, 1).data; o[n] = `rgb(${d[0]}, ${d[1]}, ${d[2]})`; }
    return o;
  }, nomes);
  if (process.env.DEPURA) console.log(tok);
  for (const [visao, m] of Object.entries(M)) {
    const fundo = simula(rgb(tok[conf.superficie]), m);
    for (const [nome, cores] of Object.entries(conf.paletas)) {
      const sim = cores.map((c) => simula(rgb(tok[c]), m));
      let menor = Infinity, par = '';
      for (let i = 0; i < sim.length; i++) for (let j = i + 1; j < sim.length; j++) {
        const d = de2000(lab(sim[i]), lab(sim[j])); if (d < menor) { menor = d; par = `${cores[i]} × ${cores[j]}`; }
      }
      const cts = sim.map((c, i) => [cores[i], contraste(c, fundo)]);
      const pior = cts.sort((x, y) => x[1] - y[1])[0];
      const ok = menor >= MINIMO_DE;
      if (!ok) falhas++;
      linhas.push({ tema, visao, paleta: nome, 'menor ΔE': +menor.toFixed(1), par, 'pior contraste': `${pior[0]} ${pior[1].toFixed(2)}`, ok });
    }
  }
  if (tema === 'light') {
    const cdp = await ctx.newCDPSession(page);
    for (const visao of ['protanopia', 'deuteranopia', 'tritanopia', 'achromatopsia']) {
      await cdp.send('Emulation.setEmulatedVisionDeficiency', { type: visao });
      await page.screenshot({ path: join(saida, `${visao}.jpg`), type: 'jpeg', quality: 60, fullPage: true });
    }
  }
  await ctx.close();
}
writeFileSync(join(saida, 'daltonismo.json'), JSON.stringify(linhas, null, 1));
console.table(linhas);
console.log(`daltonismo: ${falhas} combinacoes com ΔE abaixo de ${MINIMO_DE}`);
await b.close(); s.fechar();
process.exitCode = falhas ? 1 : 0;
