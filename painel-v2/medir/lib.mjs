// Ferramentas de medicao do painel v2: servidor estatico, pagina do Playwright
// e os estados que toda rodada mede. O Playwright vem do ambiente (global).
import { createRequire } from 'node:module';
import { createServer } from 'node:http';
import { readFileSync, existsSync, statSync, mkdirSync } from 'node:fs';
import { join, extname, resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const req = createRequire(import.meta.url);
export const { chromium } = req('playwright');
export const AQUI = dirname(fileURLToPath(import.meta.url));
export const RAIZ = resolve(AQUI, '..');
export const BUILD = resolve(RAIZ, '../relatorios/painel-v2');
export const CASOS = resolve(RAIZ, 'casos');

export const LARGURAS = [360, 768, 1280, 1600];
export const ALTURA = { 360: 740, 768: 1024, 1280: 800, 1600: 900 };
export const TEMAS = ['light', 'dark'];
// Estados pelo endereco: valem para o marco zero e para o redesenho.
export const ESTADOS = {
  base: '',
  lente: '?lente=ar:robotica_acao',
  paper: '?paper=2611.14320',
};

const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.woff2': 'font/woff2', '.png': 'image/png', '.jpg': 'image/jpeg' };

export function servir(dir = BUILD, porta = 0) {
  const srv = createServer((q, r) => {
    let p = decodeURIComponent(new URL(q.url, 'http://x').pathname);
    if (p.endsWith('/')) p += 'index.html';
    const f = join(dir, p);
    if (!f.startsWith(dir) || !existsSync(f) || statSync(f).isDirectory()) { r.writeHead(404); return r.end('404'); }
    r.writeHead(200, { 'content-type': MIME[extname(f)] || 'application/octet-stream', 'cache-control': 'no-store' });
    r.end(readFileSync(f));
  });
  return new Promise((ok) => srv.listen(porta, '127.0.0.1', () => ok({ url: `http://127.0.0.1:${srv.address().port}/`, fechar: () => srv.close() })));
}

// Abre o painel num estado. `caso` troca o dados.json por um caso extremo.
export async function abrir(browser, { url, largura = 1280, altura, tema = 'light', estado = '', caso = null, reduzido = true, escala = 1 }) {
  const ctx = await browser.newContext({
    viewport: { width: largura, height: altura || ALTURA[largura] || 800 },
    colorScheme: tema, reducedMotion: reduzido ? 'reduce' : 'no-preference', deviceScaleFactor: escala,
    hasTouch: largura < 700, locale: 'pt-BR',
  });
  const page = await ctx.newPage();
  const erros = [];
  page.on('pageerror', (e) => erros.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') erros.push(m.text()); });
  if (caso) {
    const corpo = readFileSync(join(CASOS, `${caso}.json`), 'utf8');
    await page.route('**/dados.json', (r) => r.fulfill({ contentType: 'application/json', body: corpo }));
  }
  await page.goto(url + (ESTADOS[estado] ?? estado), { waitUntil: 'networkidle' });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(900);
  return { page, ctx, erros };
}

export const arg = (nome, padrao) => {
  const i = process.argv.indexOf(`--${nome}`);
  return i > 0 ? process.argv[i + 1] : padrao;
};
export const pasta = (p) => { mkdirSync(p, { recursive: true }); return p; };
