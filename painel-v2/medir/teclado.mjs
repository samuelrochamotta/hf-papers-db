// Percurso so com teclado. Duas medidas:
// 1) varredura: Tab do inicio ao fim, anotando cada parada (nome acessivel,
//    foco visivel, parada escondida atras da barra fixa, armadilha);
// 2) percursos: para cada tarefa, uma lista de [nome acessivel, tecla]; conta
//    quantas teclas a tarefa custa e confere o resultado esperado.
//   node medir/teclado.mjs --percursos medir/percursos-v0.json
import { readFileSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { chromium, servir, abrir, BUILD, arg, pasta } from './lib.mjs';

const dir = resolve(arg('dir', BUILD));
const saida = pasta(resolve(arg('saida', 'medir/saida/atual')));
const percursos = JSON.parse(readFileSync(resolve(arg('percursos', 'medir/percursos.json')), 'utf8'));
const s = await servir(dir);
const b = await chromium.launch();

// descreve o elemento em foco
const FOCO = () => {
  const e = document.activeElement;
  if (!e || e === document.body) return null;
  const r = e.getBoundingClientRect(), cs = getComputedStyle(e);
  const rot = (id) => id.split(/\s+/).map((i) => document.getElementById(i)?.textContent || '').join(' ');
  const nome = (e.getAttribute('aria-label') || (e.getAttribute('aria-labelledby') && rot(e.getAttribute('aria-labelledby'))) || e.textContent || e.getAttribute('title') || e.getAttribute('placeholder') || '').replace(/\s+/g, ' ').trim().slice(0, 90);
  const anel = (cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0) || cs.boxShadow !== 'none';
  const cx = Math.min(innerWidth - 1, Math.max(0, r.left + r.width / 2)), cy = r.top + r.height / 2;
  const topo = cy >= 0 && cy < innerHeight ? document.elementFromPoint(cx, cy) : null;
  return {
    tag: e.tagName.toLowerCase(), papel: e.getAttribute('role') || '', nome, anel,
    estado: e.getAttribute('aria-pressed') ?? e.getAttribute('aria-selected') ?? e.getAttribute('aria-expanded') ?? e.getAttribute('aria-current') ?? '',
    visivel: r.width > 0 && r.height > 0 && cy >= 0 && cy < innerHeight,
    coberto: !!topo && !(e === topo || e.contains(topo) || topo.contains(e)),
    tam: [Math.round(r.width), Math.round(r.height)],
    chave: `${e.tagName}|${nome}|${Math.round(r.left + scrollX)}|${Math.round(r.top + scrollY)}`,
  };
};

async function varrer(largura) {
  const { page, ctx } = await abrir(b, { url: s.url, largura });
  const paradas = []; const vistos = new Set();
  for (let i = 0; i < 600; i++) {
    await page.keyboard.press('Tab');
    const f = await page.evaluate(FOCO);
    if (!f) break;
    if (vistos.has(f.chave)) break;
    vistos.add(f.chave); paradas.push(f);
  }
  await ctx.close();
  return {
    largura, paradas: paradas.length,
    semNome: paradas.filter((p) => !p.nome).length,
    semAnel: paradas.filter((p) => !p.anel).map((p) => p.nome || p.tag).slice(0, 8),
    cobertas: paradas.filter((p) => p.coberto).map((p) => p.nome || p.tag).slice(0, 8),
    foraDaTela: paradas.filter((p) => !p.visivel).map((p) => p.nome || p.tag).slice(0, 8),
    lista: paradas.map((p) => `${p.tag}${p.papel ? `[${p.papel}]` : ''} ${p.nome}`),
  };
}

async function percorrer(nome, passos, largura = 1280) {
  const { page, ctx } = await abrir(b, { url: s.url + (passos.inicio || ''), largura });
  let teclas = 0; const trilha = [];
  for (const [alvo, tecla] of passos.passos) {
    if (alvo) {
      const re = new RegExp(alvo, 'i'); let achou = false;
      for (let i = 0; i < 400; i++) {
        const f = await page.evaluate(FOCO);
        if (f && re.test(f.nome) && i > 0 || (f && re.test(f.nome) && passos.semTab)) { achou = true; break; }
        await page.keyboard.press(passos.voltar ? 'Shift+Tab' : 'Tab'); teclas++;
        const g = await page.evaluate(FOCO);
        if (g && re.test(g.nome)) { achou = true; break; }
      }
      if (!achou) { await ctx.close(); return { nome, ok: false, teclas, erro: `sem foco em /${alvo}/`, trilha }; }
    }
    if (tecla) { for (const t of [].concat(tecla)) { await page.keyboard.press(t); teclas++; } await page.waitForTimeout(350); }
    trilha.push((await page.evaluate(FOCO))?.nome?.slice(0, 40) || '(body)');
  }
  let ok = true, visto = '';
  if (passos.espera) {
    visto = await page.evaluate(() => document.body.innerText.replace(/\s+/g, ' '));
    const fn = (await page.evaluate(FOCO))?.nome || '';
    ok = [visto, page.url(), fn].some((x) => new RegExp(passos.espera, 'i').test(x));
  }
  if (passos.focoFinal) { const f = await page.evaluate(FOCO); ok = ok && !!f && new RegExp(passos.focoFinal, 'i').test(f.nome); }
  await ctx.close();
  return { nome, ok, teclas, trilha: trilha.slice(-3) };
}

const varreduras = [await varrer(1280), await varrer(360)];
const feitos = [];
for (const [nome, p] of Object.entries(percursos)) feitos.push(await percorrer(nome, p));
writeFileSync(join(saida, 'teclado.json'), JSON.stringify({ varreduras, percursos: feitos }, null, 1));
console.table(varreduras.map(({ lista, ...v }) => ({ ...v, semAnel: v.semAnel.length, cobertas: v.cobertas.length, foraDaTela: v.foraDaTela.length })));
console.table(feitos.map(({ trilha, ...f }) => f));
const falhas = feitos.filter((f) => !f.ok).length;
console.log(`teclado: ${feitos.length - falhas}/${feitos.length} percursos completos, ${feitos.reduce((a, f) => a + f.teclas, 0)} teclas no total`);
await b.close(); s.fechar();
process.exitCode = falhas ? 1 : 0;
