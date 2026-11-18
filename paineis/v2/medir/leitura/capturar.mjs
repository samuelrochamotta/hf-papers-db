// Teste de leitura: gera as sete imagens de cada conjunto. Cada conjunto e
// uma combinacao de variantes do prototipo (X, Y, Z) ou o painel de antes (O).
// Leitores que so recebem as imagens e medir/leitura/perguntas.md respondem
// 21 perguntas; medir/leitura/pontuar.py confere as respostas.
//   node medir/leitura/capturar.mjs --proto <build do prototipo> --base <build de antes> --saida <pasta>
// As variantes X, Y e Z existem ate o commit do prototipo com experimentos;
// depois dele o painel guarda so a forma escolhida.
import { chromium, servir, abrir, arg, BUILD } from '../lib.mjs';
import fs from 'node:fs';
import { resolve } from 'node:path';
const PROTO = resolve(arg('proto', BUILD)), BASE = resolve(arg('base', BUILD)), SAIDA = resolve(arg('saida', 'medir/saida/leitura'));
const CMP = 'comparar=2611.08373,2611.04277,2611.06043';
const SETS = {
  X: { dir: PROTO, v: 'indice=tabela&dens=m&g=a&radar=sobre' },
  Y: { dir: PROTO, v: 'indice=tabela&dens=c&g=b&radar=lado' },
  Z: { dir: PROTO, v: 'indice=linhas&g=a&radar=pontos' },
  O: { dir: BASE, v: '', base: true },
};
const b = await chromium.launch();
const linhas = {};
for (const [nome, s] of Object.entries(SETS)) {
  const srv = await servir(s.dir); const out = `${SAIDA}/${nome}`; fs.mkdirSync(out, { recursive: true });
  const q = (extra) => '?' + [s.v, extra].filter(Boolean).join('&');
  const quadro = (page, titulo) => page.locator('section, article, div.card').filter({ has: page.getByRole('heading', { name: titulo, exact: true }) }).last();
  // 1 indice e 2 filtro: o que cabe na primeira tela
  for (const [arq, extra] of [['1-indice', ''], ['2-filtro', 'lente=ar:robotica_acao']]) {
    const { page, ctx } = await abrir(b, { url: srv.url + q(extra), largura: 1280 });
    await page.screenshot({ path: `${out}/${arq}.png` });
    if (arq === '1-indice') linhas[nome] = await page.evaluate(() => {
      const els = [...document.querySelectorAll('.lista .linha, .tiles .tile, #papers [role="listitem"], #papers .it, #papers li')];
      return els.filter((e) => { const r = e.getBoundingClientRect(); return r.top >= 0 && r.bottom <= innerHeight && r.height > 0; }).length;
    });
    await ctx.close();
  }
  // 3 a 5: um grafico por imagem
  {
    const { page, ctx } = await abrir(b, { url: srv.url + q(s.base ? '' : 'vista=panorama'), largura: 1280, altura: 1400 });
    for (const [arq, titulo] of [['3-prova', 'Onde há votos sem prova?'], ['4-ganho', 'Quanto ganham do melhor rival?'], ['5-adocao', 'O que dá para adotar já?']]) {
      const el = quadro(page, titulo); await el.scrollIntoViewIfNeeded(); await page.waitForTimeout(500);
      await el.screenshot({ path: `${out}/${arq}.png` });
    }
    await ctx.close();
  }
  // 6 e 7: comparacao de tres papers, no computador e no celular
  for (const [arq, largura] of [['6-comparar', 1280], ['7-comparar-celular', 360]]) {
    const { page, ctx } = await abrir(b, { url: srv.url + q((s.base ? '' : 'vista=comparar&') + CMP), largura, altura: largura === 360 ? 1400 : 900 });
    if (s.base) { const el = page.locator('section#comparar'); await el.scrollIntoViewIfNeeded(); await page.waitForTimeout(600); await el.screenshot({ path: `${out}/${arq}.png` }); }
    else { await page.addStyleTag({ content: 'nav.abas{display:none!important}' }); await page.screenshot({ path: `${out}/${arq}.png`, fullPage: true }); }
    await ctx.close();
  }
  srv.fechar();
}
await b.close();
fs.writeFileSync(`${SAIDA}/linhas-por-tela.json`, JSON.stringify(linhas));
console.log('linhas inteiras na primeira tela (1280x800):', linhas);
