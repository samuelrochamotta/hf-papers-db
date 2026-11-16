// Casos extremos (painel-v2/casos/*.json, gerados de dados reais por
// scripts/perfil_dados.py): nada pode quebrar. Em cada caso e largura confere
// erro de console, rolagem horizontal, elemento que sai da tela, texto cortado
// sem reticencias e texto sobreposto; depois abre o primeiro paper e repete.
import { readdirSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { chromium, servir, abrir, BUILD, CASOS, arg, pasta } from './lib.mjs';

const dir = resolve(arg('dir', BUILD));
const saida = pasta(resolve(arg('saida', 'medir/saida/atual'), 'extremos'));
const s = await servir(dir);
const b = await chromium.launch();
const casos = readdirSync(CASOS).filter((f) => f.endsWith('.json')).map((f) => f.replace('.json', ''));

const CONFERE = () => {
  const vw = innerWidth, fora = [], cortado = [], minusculo = [], vaza = [];
  const visivel = (e) => { const c = getComputedStyle(e); return c.visibility !== 'hidden' && c.display !== 'none' && +c.opacity > 0; };
  const rolavel = (e) => { for (let p = e.parentElement; p; p = p.parentElement) { const o = getComputedStyle(p).overflowX; if (o === 'auto' || o === 'scroll' || o === 'hidden' || o === 'clip') return true; } return false; };
  for (const e of document.querySelectorAll('body *')) {
    if (!visivel(e) || e.closest('[aria-hidden="true"]')) continue;
    const r = e.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    const id = (e.className && typeof e.className === 'string' ? '.' + e.className.split(' ')[0] : e.tagName.toLowerCase()) + ' ' + (e.textContent || '').trim().slice(0, 30);
    if ((r.right > vw + 1 || r.left < -1) && !rolavel(e)) fora.push(id);
    const c = getComputedStyle(e);
    const temTexto = [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
    if (temTexto && e.scrollWidth > e.clientWidth + 1 && (c.overflowX === 'hidden' || c.overflowX === 'clip') && c.textOverflow !== 'ellipsis' && !c.webkitLineClamp) cortado.push(id);
    if (temTexto && parseFloat(c.fontSize) < 11) minusculo.push(id);
    // texto que vaza da propria caixa (palavra inquebravel, por exemplo)
    if (temTexto && c.display !== 'inline' && e.scrollWidth > e.clientWidth + 1 && c.overflowX === 'visible') vaza.push(id);
  }
  return { estouro: document.documentElement.scrollWidth > vw + 1, fora: [...new Set(fora)].slice(0, 6), cortado: [...new Set([...cortado, ...vaza.map((v) => 'vaza ' + v)])].slice(0, 6), minusculo: [...new Set(minusculo)].length };
};

const linhas = []; let falhas = 0;
for (const caso of casos) for (const largura of [360, 1280]) {
  const { page, ctx, erros } = await abrir(b, { url: s.url, largura, caso });
  const r = await page.evaluate(CONFERE);
  await page.screenshot({ path: join(saida, `${caso}-${largura}.jpg`), type: 'jpeg', quality: 60, fullPage: true });
  // abre o primeiro paper que existir (qualquer botao ou link que leve a ?paper=)
  let rp = null;
  const antes = page.url();
  const alvo = page.locator('[data-paper], [role="listitem"] button, .it').first();
  if (await alvo.count()) {
    await alvo.click({ timeout: 2000 }).catch(() => {});
    await page.waitForTimeout(500);
    if (page.url() !== antes) {
      rp = await page.evaluate(CONFERE);
      await page.screenshot({ path: join(saida, `${caso}-${largura}-paper.jpg`), type: 'jpeg', quality: 60 });
    }
  }
  const ruim = erros.length || r.estouro || r.fora.length || r.cortado.length || (rp && (rp.estouro || rp.fora.length || rp.cortado.length));
  if (ruim) falhas++;
  linhas.push({ caso, largura, erros: erros.length, estouro: r.estouro, fora: r.fora.length, cortado: r.cortado.length, paper: rp ? (rp.estouro || rp.fora.length || rp.cortado.length ? 'quebra' : 'ok') : 'nao abriu', det: [...erros.slice(0, 1), ...r.fora, ...r.cortado, ...(rp ? [...rp.fora, ...rp.cortado] : [])].slice(0, 4).join(' | ') });
  await ctx.close();
}
writeFileSync(join(saida, 'extremos.json'), JSON.stringify(linhas, null, 1));
console.table(linhas);
console.log(`extremos: ${falhas} de ${linhas.length} combinacoes com quebra`);
await b.close(); s.fechar();
process.exitCode = falhas ? 1 : 0;
