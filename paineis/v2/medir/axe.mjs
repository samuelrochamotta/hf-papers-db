// axe-core em todos os estados e temas (360 e 1280 px), com todas as regras
// WCAG 2.x A/AA e boas praticas. Sai com erro se houver violacao.
import { readFileSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { join, resolve } from 'node:path';
import { chromium, servir, abrir, TEMAS, ESTADOS, BUILD, arg, pasta } from './lib.mjs';

const fonte = readFileSync(createRequire(import.meta.url).resolve('axe-core/axe.min.js'), 'utf8');
const dir = resolve(arg('dir', BUILD));
const saida = pasta(resolve(arg('saida', 'medir/saida/atual')));
const s = await servir(dir);
const b = await chromium.launch();
const linhas = []; const viol = {}; let total = 0, incompletos = 0;
const extras = (arg('estados', '') || '').split(',').filter(Boolean);
for (const largura of [360, 1280]) for (const tema of TEMAS) for (const estado of [...Object.keys(ESTADOS), ...extras]) {
  const { page, ctx } = await abrir(b, { url: s.url, largura, tema, estado });
  await page.evaluate(fonte);
  const r = await page.evaluate(() => axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'] } }));
  const nos = r.violations.reduce((a, v) => a + v.nodes.length, 0);
  total += nos; incompletos += r.incomplete.length;
  linhas.push({ estado: `${largura}-${tema}-${estado}`, regras: r.violations.length, nos, passa: r.passes.length, revisar: r.incomplete.map((i) => i.id).join(' ') });
  for (const v of r.violations) {
    const k = (viol[v.id] ||= { impacto: v.impact, ajuda: v.help, onde: new Set(), exemplos: [] });
    k.onde.add(`${largura}-${tema}-${estado}`);
    for (const n of v.nodes.slice(0, 3)) if (k.exemplos.length < 4) k.exemplos.push({ alvo: n.target.join(' '), msg: (n.any[0] || n.all[0] || n.none[0] || {}).message });
  }
  await ctx.close();
}
const resumo = Object.fromEntries(Object.entries(viol).map(([id, v]) => [id, { ...v, onde: [...v.onde] }]));
writeFileSync(join(saida, 'axe.json'), JSON.stringify({ total, linhas, violacoes: resumo }, null, 1));
console.table(linhas);
for (const [id, v] of Object.entries(resumo)) console.log(`\n${id} [${v.impacto}] ${v.ajuda}\n  em ${v.onde.length} estados\n` + v.exemplos.map((e) => `  ${e.alvo}: ${e.msg}`).join('\n'));
console.log(`\naxe: ${total} nos em violacao, ${Object.keys(resumo).length} regras`);
await b.close(); s.fechar();
process.exitCode = total ? 1 : 0;
