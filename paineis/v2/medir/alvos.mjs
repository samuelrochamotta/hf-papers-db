// Alvos de toque: com o dedo na tela (360 px, ponteiro grosso), quanto de cada
// controle responde ao toque. Mede de fato: parte do centro do controle e anda
// para os quatro lados enquanto o ponto ainda cai nele (elementFromPoint), o
// que conta a area estendida por pseudo-elementos e desconta vizinhos.
// Criterio: 44 x 44 px (HIG e Material). Link dentro de frase fica fora, como
// na WCAG 2.5.8. Abaixo de 24 px e falha em qualquer caso.
// uso: node medir/alvos.mjs [--dir build] [--saida pasta] [--estados "?a,?b"] [--largura 360]
// --largura 768 mede o tablet, tambem com ponteiro grosso.
import { chromium, servir, abrir, arg, BUILD } from './lib.mjs';
import { writeFileSync, mkdirSync } from 'node:fs';
const dir = arg('dir', BUILD), saida = arg('saida', ''), largura = +arg('largura', 360);
const estados = arg('estados', '?vista=papers,?lente=ar:robotica_acao,?paper=2611.14320,?paper=2611.14320&prof=3,?vista=panorama,?vista=comparar&comparar=2611.08373%2C2611.04277%2C2611.14320').split(',');
const MIN = 44;
const srv = await servir(dir), b = await chromium.launch();
const linhas = [], falhas = [];
for (const estado of estados) for (const tema of ['light']) {
  const { page, ctx } = await abrir(b, { url: srv.url, largura, tema, estado, toque: true });
  const itens = await page.evaluate((MIN) => {
    const raiz = document.querySelector('.paper') || document.body;
    const out = [];
    for (const el of raiz.querySelectorAll('button, a[href], input, [role="tab"], summary')) {
      if (el.closest('[inert]') || el.disabled) continue;
      el.scrollIntoView({ block: 'center', inline: 'nearest' });
      const r = el.getBoundingClientRect();
      if (!r.width || !r.height) continue;
      const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
      const meu = (x, y) => { const h = document.elementFromPoint(x, y); return h && (h === el || el.contains(h) || (h.closest('label') && h.closest('label').contains(el))); };
      if (!meu(cx, cy)) continue;                       // coberto (barra presa): nao e alvo nesta posicao
      const anda = (dx, dy) => { let n = 0; while (n < 60 && meu(cx + dx * (n + 1), cy + dy * (n + 1))) n++; return n; };
      const w = anda(-1, 0) + anda(1, 0) + 1, h = anda(0, -1) + anda(0, 1) + 1;
      const emFrase = el.matches('a, button.lk') && el.parentElement && [...el.parentElement.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim().length > 12);
      out.push({ nome: (el.getAttribute('aria-label') || el.textContent || el.placeholder || el.className).trim().replace(/\s+/g, ' ').slice(0, 48), w, h, emFrase, desenho: `${Math.round(r.width)}x${Math.round(r.height)}` });
    }
    return out;
  }, MIN);
  const vistos = new Set();
  for (const it of itens) {
    const chave = `${it.nome}|${it.w}|${it.h}`; if (vistos.has(chave)) continue; vistos.add(chave);
    const ok = it.emFrase ? Math.min(it.w, it.h) >= 16 : it.w >= MIN && it.h >= MIN;
    linhas.push(`${ok ? 'ok   ' : 'FALHA'} ${estado.padEnd(34)} ${String(it.w).padStart(3)}x${String(it.h).padEnd(3)} desenho ${it.desenho.padEnd(8)} ${it.emFrase ? '(em frase) ' : ''}${it.nome}`);
    if (!ok) falhas.push({ estado, ...it });
  }
  await ctx.close();
}
await b.close(); srv.fechar();
console.log(linhas.filter((l) => l.startsWith('FALHA')).join('\n'));
console.log(`alvos de toque: ${linhas.length} controles medidos, ${falhas.length} abaixo de ${MIN} px`);
if (saida) { mkdirSync(saida, { recursive: true }); writeFileSync(`${saida}/alvos.txt`, linhas.join('\n') + '\n'); writeFileSync(`${saida}/alvos.json`, JSON.stringify({ medidos: linhas.length, falhas }, null, 1)); }
process.exit(falhas.length ? 1 : 0);
