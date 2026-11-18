// Sessao de uso simulado: um navegador que so devolve capturas. Um subagente
// recebe a tarefa em texto, pede uma acao por vez (clicar, rolar, tecla) e ve
// apenas a nova captura. Cada acao fica no registro com o que foi atingido,
// para medir passos, tempo estimado e acerto no primeiro clique.
//   node medir/sessao.mjs --dir <build> --porta 4901 --largura 1280 --registro medir/saida/x/uso-a.jsonl
// e, do outro lado:  node medir/agir.mjs 4901 iniciar T1 | clicar 400 300 | rolar 600 | tecla Escape | digitar "texto" | passar 400 300 | responder T1 "texto"
import { createServer } from 'node:http';
import { appendFileSync, writeFileSync, existsSync } from 'node:fs';
import { resolve, join, dirname } from 'node:path';
import { chromium, servir, abrir, BUILD, ALTURA, arg, pasta } from './lib.mjs';

const dir = resolve(arg('dir', BUILD));
const porta = +arg('porta', 4901);
const largura = +arg('largura', 1280);
const registro = resolve(arg('registro', 'medir/saida/atual/uso.jsonl'));
const inicio = arg('inicio', '');
const caps = pasta(join(dirname(registro), 'uso-capturas-' + porta));
if (!existsSync(registro)) writeFileSync(registro, '');
const s = await servir(dir);
const b = await chromium.launch();
let page = null, ctx = null, tarefa = null, n = 0, mouse = [largura / 2, (ALTURA[largura] || 800) / 2];

const ALVO = ([x, y]) => {
  const e = document.elementFromPoint(x, y); if (!e) return null;
  const a = e.closest('button, a, [role="button"], [role="tab"], [role="option"], select, input, summary, [tabindex]') || e;
  const nome = (a.getAttribute('aria-label') || a.textContent || a.getAttribute('title') || a.getAttribute('placeholder') || '').replace(/\s+/g, ' ').trim().slice(0, 100);
  const regiao = e.closest('[data-regiao], section[id], [role="dialog"], header, nav, aside, footer');
  return { tag: a.tagName.toLowerCase(), nome, canvas: e.tagName === 'CANVAS', regiao: regiao ? (regiao.dataset.regiao || regiao.id || regiao.getAttribute('aria-label') || regiao.tagName.toLowerCase()) : '' };
};
const grava = (o) => appendFileSync(registro, JSON.stringify({ t: Date.now(), porta, largura, tarefa, ...o }) + '\n'); // a resposta leva a tarefa que o comando nomeou
async function captura() {
  const f = join(caps, `${tarefa || 'x'}-${String(++n).padStart(3, '0')}.jpg`);
  await page.screenshot({ path: f, type: 'jpeg', quality: 70 });
  return f;
}

createServer(async (q, r) => {
  let corpo = ''; for await (const c of q) corpo += c;
  const a = JSON.parse(corpo || '{}'); let extra = '';
  try {
    if (a.tipo === 'iniciar') {
      if (ctx) await ctx.close();
      ({ page, ctx } = await abrir(b, { url: s.url, largura, estado: inicio, reduzido: true }));
      tarefa = a.tarefa; n = 0; mouse = [largura / 2, (ALTURA[largura] || 800) / 2];
      grava({ tipo: 'iniciar' });
    } else if (!page) { throw new Error('use "iniciar <tarefa>" primeiro'); }
    else if (a.tipo === 'clicar') {
      mouse = [+a.x, +a.y];
      const alvo = await page.evaluate(ALVO, mouse);
      await page.mouse.click(...mouse); await page.waitForTimeout(650);
      grava({ tipo: 'clicar', x: +a.x, y: +a.y, alvo, url: page.url() });
    } else if (a.tipo === 'passar') {
      mouse = [+a.x, +a.y]; await page.mouse.move(...mouse); await page.waitForTimeout(450);
      grava({ tipo: 'passar', x: +a.x, y: +a.y, alvo: await page.evaluate(ALVO, mouse) });
    } else if (a.tipo === 'rolar') {
      await page.mouse.move(...mouse); await page.mouse.wheel(0, +a.dy); await page.waitForTimeout(450);
      grava({ tipo: 'rolar', dy: +a.dy });
    } else if (a.tipo === 'tecla') {
      await page.keyboard.press(a.k); await page.waitForTimeout(450);
      grava({ tipo: 'tecla', k: a.k, url: page.url() });
    } else if (a.tipo === 'digitar') {
      await page.keyboard.type(String(a.texto || ''), { delay: 20 }); await page.waitForTimeout(500);
      grava({ tipo: 'digitar', texto: a.texto, url: page.url() });
    } else if (a.tipo === 'responder') {
      // a resposta vale para a tarefa aberta: ninguem responde de memoria uma tarefa que nao iniciou
      if (a.tarefa && a.tarefa !== tarefa) throw new Error(`a tarefa aberta e ${tarefa}; use "iniciar ${a.tarefa}" antes de responder`);
      grava({ tipo: 'responder', tarefa: a.tarefa || tarefa, resposta: a.resposta, url: page.url() });
      extra = 'resposta registrada. ';
    } else if (a.tipo === 'fim') { r.end('ok'); await b.close(); s.fechar(); process.exit(0); }
    else throw new Error('acao desconhecida: ' + a.tipo);
    const f = await captura();
    const pos = await page.evaluate(() => `rolagem ${Math.round(scrollY)} de ${Math.max(0, document.documentElement.scrollHeight - innerHeight)} px`);
    r.end(`${extra}captura: ${f} (${largura}x${ALTURA[largura] || 800}; ${pos})`);
  } catch (e) { r.statusCode = 500; r.end('erro: ' + e.message); }
}).listen(porta, '127.0.0.1', () => console.log(`sessao em ${porta}, ${largura}px, ${dir}`));
