// Estimulos do experimento E4 (marca de prova): os mesmos dois graficos, nas
// duas variantes da marca, em quatro condicoes de leitura.
// uso: node medir/marca/estimulos.mjs <build> <saida> [escala]
// Precisa de um build que ainda tenha as duas variantes (?marca=cor|cheio): o commit d3e21a3.
import { chromium, servir, abrir } from '../lib.mjs';
import fs from 'node:fs';
const [dir, saida] = process.argv.slice(2);
const DEUT = '0.367322 0.860646 -0.227968 0 0  0.280085 0.672501 0.047413 0 0  -0.011820 0.042940 0.968881 0 0  0 0 0 1 0';
const COND = { normal: [1280, 'light', null], escuro: [1280, 'dark', null], deuteranopia: [1280, 'light', DEUT], celular: [360, 'light', null] };
const srv = await servir(dir); const b = await chromium.launch();
for (const marca of ['cor', 'cheio']) for (const [cond, [largura, tema, matriz]] of Object.entries(COND)) {
  const pasta = `${saida}/${marca}-${cond}`; fs.mkdirSync(pasta, { recursive: true });
  const { page, ctx, erros } = await abrir(b, { url: srv.url, largura, tema, estado: `?vista=panorama&marca=${marca}`, escala: +(process.argv[4] || 2) });
  await page.waitForTimeout(700);
  // some com as faixas presas: elas cobririam o grafico na captura do elemento
  await page.addStyleTag({ content: '.topo,.recorte,.abas{position:static!important} nav.abas{display:none!important}' });
  if (matriz) await page.evaluate((m) => {
    const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    s.setAttribute('style', 'position:absolute;width:0;height:0');
    s.innerHTML = `<filter id="cvd" color-interpolation-filters="linearRGB"><feColorMatrix type="matrix" values="${m}"/></filter>`;
    document.body.append(s); document.documentElement.style.filter = 'url(#cvd)';
  }, matriz);
  await page.waitForTimeout(300);
  for (const q of ['adocao', 'ganho']) { const el = page.locator(`[data-regiao=${q}]`); await el.scrollIntoViewIfNeeded(); await page.waitForTimeout(250); await el.screenshot({ path: `${pasta}/${q}.png` }); }
  if (erros.length) console.log(marca, cond, 'ERROS', erros.slice(0, 3));
  await ctx.close();
}
await b.close(); srv.fechar();
console.log('ok');
