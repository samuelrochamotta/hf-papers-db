// Matriz de capturas: 4 larguras x 2 temas x (base, lente, paper aberto).
//   node medir/capturas.mjs --dir ../relatorios/painel-v2 --saida medir/saida/rodada-0
// --estados acrescenta estados pelo endereco, no formato nome@endereco:
//   --estados "panorama@?vista=panorama,comparar@?vista=comparar&comparar=a%2Cb"
import { writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { chromium, servir, abrir, LARGURAS, TEMAS, ESTADOS, BUILD, arg, pasta } from './lib.mjs';

const dir = resolve(arg('dir', BUILD));
const saida = pasta(resolve(arg('saida', 'medir/saida/atual'), 'matriz'));
const s = await servir(dir);
const b = await chromium.launch();
const feitas = [];
const estados = [...Object.keys(ESTADOS).map((k) => [k, k]), ...(arg('estados', '') || '').split(',').filter(Boolean).map((e) => e.split('@'))];
for (const largura of LARGURAS) for (const tema of TEMAS) for (const [rot, estado] of estados) {
  const { page, ctx, erros } = await abrir(b, { url: s.url, largura, tema, estado });
  const nome = `${largura}-${tema}-${rot}`;
  // paper aberto: o que importa e a janela (gaveta ou folha), nao a pagina inteira
  await page.screenshot({ path: join(saida, `${nome}.jpg`), type: 'jpeg', quality: 72, fullPage: !estado.includes('paper') });
  const m = await page.evaluate(() => ({ alt: document.documentElement.scrollHeight, larg: document.documentElement.scrollWidth, vw: innerWidth }));
  feitas.push({ nome, ...m, estouro: m.larg > m.vw, erros });
  await ctx.close();
}
writeFileSync(join(saida, 'matriz.json'), JSON.stringify(feitas, null, 1));
console.table(feitas.map(({ nome, alt, estouro, erros }) => ({ nome, alt, estouro, erros: erros.length })));
await b.close(); s.fechar();
