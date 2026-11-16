// Le os tokens de cor do CSS para os graficos e avisa quando o tema muda
// (preferencia do sistema, data-theme ou data-id na raiz).
const NOMES = ['bg', 'surface', 'sunk', 'hover', 'raise', 'ink', 'ink2', 'muted', 'line', 'line-strong', 'accent', 'on-accent', 'focus',
  'alert', 'alert-soft', 'sol-forte', 'sol-firme', 'sol-basico', 'sol-fragil', 'sol-nada',
  'res-ganha', 'res-ruido', 'res-perde', 'res-semrival', 'cmp-1', 'cmp-2', 'cmp-3', 'f-ui', 'f-num', 'f-display'];

export function lerTema() {
  const cs = getComputedStyle(document.documentElement);
  const t = {};
  for (const n of NOMES) t[n.replace(/-(\w)/g, (_, c) => c.toUpperCase())] = cs.getPropertyValue(`--${n}`).trim();
  t.escuro = cs.colorScheme === 'dark';
  return t;
}

export function observarTema(cb) {
  const mq = matchMedia('(prefers-color-scheme: dark)');
  const f = () => cb(lerTema());
  mq.addEventListener('change', f);
  const mo = new MutationObserver(f);
  mo.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme', 'data-id'] });
  f();
  // as fontes chegam depois: os graficos medem texto, entao redesenham
  document.fonts?.ready.then(f);
  return () => { mq.removeEventListener('change', f); mo.disconnect(); };
}

export const corSolidez = (t, s) => ({ forte: t.solForte, firme: t.solFirme, basico: t.solBasico, fragil: t.solFragil, sem_leitura: 'transparent' }[s]);
export const corCmp = (t, i) => [t.cmp1, t.cmp2, t.cmp3][i];

// Ponto de um paper: uma codificacao so (cor = solidez). Sem leitura
// suficiente vira anel tracejado: ausencia de dado nao e um nivel da rampa.
export function estiloPonto(t, p) {
  if (p.sol === 'sem_leitura') return { color: t.surface, borderColor: t.solNada, borderWidth: 1.5, borderType: [3, 2] };
  return { color: corSolidez(t, p.sol), borderColor: t.surface, borderWidth: 1 };
}
// o mesmo ponto para quem desenha a propria forma (serie custom)
export const marca = (t, p) => (p.sol === 'sem_leitura'
  ? { fill: t.surface, stroke: t.solNada, lineWidth: 1.5, lineDash: [3, 2] }
  : { fill: corSolidez(t, p.sol), stroke: t.surface, lineWidth: 1 });
// A marca de prova de quem desenha a propria forma, como lista de elementos.
// Na variante "cheio", alem da cor, o disco enche conforme a prova: forte
// inteiro, firme 3/4, basica 1/2, fragil 1/4. Sem leitura continua anel
// tracejado. `extra` (realce, cursor, nome) vai no primeiro elemento.
const FRACAO = { forte: 1, firme: 0.75, basico: 0.5, fragil: 0.25 };
export function pontoProva(t, p, cx, cy, r, { cheio = false, extra = {}, borda = null } = {}) {
  const f = FRACAO[p.sol], m = marca(t, p);
  if (!cheio || f == null || f === 1) return [{ type: 'circle', shape: { cx, cy, r }, style: borda ? { ...m, stroke: borda } : m, ...extra }];
  const cor = corSolidez(t, p.sol);
  return [
    { type: 'circle', shape: { cx, cy, r: r - 0.75 }, style: { fill: t.surface, stroke: borda || cor, lineWidth: 1.5 }, ...extra },
    { type: 'sector', silent: true, shape: { cx, cy, r0: 0, r: r - 0.75, startAngle: -Math.PI / 2, endAngle: -Math.PI / 2 + 2 * Math.PI * f }, style: { fill: cor } },
  ];
}
// Enxame: os pontos de uma mesma linha ficam no centro da faixa enquanto ha
// lugar; quem tocaria um vizinho sobe ou desce o minimo necessario. Se a
// linha lota, os desvios encolhem para caber na faixa. Recebe [{x, y}] em
// pixels e devolve o desvio vertical de cada ponto. Sem sorteio: a mesma
// entrada da sempre o mesmo desenho.
export function enxame(pts, faixa, raio = 6.5, folga = 2) {
  const d = 2 * raio + folga, dy = pts.map(() => 0), linhas = new Map();
  pts.forEach((p, i) => { if (!linhas.has(p.y)) linhas.set(p.y, []); linhas.get(p.y).push(i); });
  for (const idx of linhas.values()) {
    idx.sort((a, b) => pts[a].x - pts[b].x || a - b);
    const postos = [];
    for (const i of idx) {
      const viz = postos.filter((j) => pts[i].x - pts[j].x < d);
      const livre = (c) => viz.every((j) => Math.hypot(pts[i].x - pts[j].x, c - dy[j]) >= d - 0.01);
      const cands = [0];
      for (const j of viz) { const h = Math.sqrt(Math.max(0, d * d - (pts[i].x - pts[j].x) ** 2)); cands.push(dy[j] + h, dy[j] - h); }
      dy[i] = cands.sort((a, b) => Math.abs(a) - Math.abs(b) || a - b).find(livre) ?? 0;
      postos.push(i);
    }
    const max = Math.max(...idx.map((i) => Math.abs(dy[i]))), lim = Math.max(0, faixa / 2 - raio - 1);
    if (max > lim) for (const i of idx) dy[i] *= lim / max;
  }
  return dy;
}

const reduz = () => typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;
export function base(t) {
  return {
    backgroundColor: 'transparent',
    textStyle: { fontFamily: t.fUi, color: t.ink2 },
    animation: !reduz(), animationDuration: 320, animationDurationUpdate: 320,
    animationEasing: 'cubicOut', animationEasingUpdate: 'cubicInOut',
    tooltip: {
      backgroundColor: t.raise, borderColor: t.line, borderWidth: 1, padding: [8, 12],
      textStyle: { color: t.ink, fontFamily: t.fUi, fontSize: 12, lineHeight: 16 },
      extraCssText: `border-radius:8px;box-shadow:0 8px 24px rgba(0,0,0,${t.escuro ? '.5' : '.12'});max-width:280px;white-space:normal;`,
      confine: true, transitionDuration: 0.12,
    },
  };
}

// Eixos com a mesma voz em todos os graficos. Nada abaixo de 12 px.
export const rotNum = (t) => ({ color: t.muted, fontFamily: t.fNum, fontSize: 12 });
export const rotCat = (t, forte = true) => ({ color: forte ? t.ink : t.muted, fontFamily: t.fUi, fontSize: 12, fontWeight: forte ? 500 : 400 });
export const grade = (t) => ({ lineStyle: { color: t.line } });

export const dica = (titulo, ...linhas) =>
  `<div style="font-weight:600;margin-bottom:2px">${titulo}</div>` + linhas.filter(Boolean).map((l) => `<div style="opacity:.8">${l}</div>`).join('');

// Dominio de eixo honesto: cobre a massa dos dados (cerca de Tukey) em passos
// redondos. O que fica alem dele e desenhado na borda com marca de corte e o
// valor escrito ao lado: o eixo nunca corta em silencio.
export function dominio(vals, { inclui = [0] } = {}) {
  const a = vals.filter((v) => v != null && Number.isFinite(v)).sort((x, y) => x - y);
  const q = (f) => { const i = (a.length - 1) * f, b = Math.floor(i); return a[b] + (a[Math.min(a.length - 1, b + 1)] - a[b]) * (i - b); };
  let lo = Math.min(...inclui), hi = Math.max(...inclui);
  if (a.length) {
    const iqr = Math.max(q(0.75) - q(0.25), 5);
    lo = Math.min(lo, Math.max(a[0], q(0.25) - 1.5 * iqr)); hi = Math.max(hi, Math.min(a[a.length - 1], q(0.75) + 1.5 * iqr));
  }
  // passo redondo que da de 3 a 7 intervalos: os rotulos do eixo caem nas marcas
  const passo = [5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000].find((s) => (hi - lo) / s <= 6) || 10000;
  let d0 = Math.floor(lo / passo) * passo, d1 = Math.ceil(hi / passo) * passo;
  // quem fica a menos de um passo da borda entra no eixo: o corte e so para o que foge muito
  if (a.length && a[0] < d0 && a[0] >= d0 - passo) d0 -= passo;
  if (a.length && a[a.length - 1] > d1 && a[a.length - 1] <= d1 + passo) d1 += passo;
  if (d0 === d1) d1 = d0 + passo;
  return [d0, d1, passo];
}

// largura de um texto em pixels, para reservar o lugar do nome antes de desenhar
let tela;
export const larguraTexto = (txt, fonte) => { tela ||= document.createElement('canvas').getContext('2d'); tela.font = fonte; return tela.measureText(txt).width; };

// Nomes de pontos sem sobreposicao. Recebe os pontos em pixels, na ordem de
// prioridade ({x, y, r, w, h, dentro, obrigatorio}), e devolve a caixa
// [x, y, w, h] do nome de cada um, ou null quando nao ha lugar limpo. Lugar
// limpo: dentro da area, sem encobrir ponto nem outro nome, sem cruzar linha
// de referencia e do mesmo lado da zona que o ponto. Ponto obrigatorio ganha
// nome sempre, no lugar menos ruim. Sem sorteio: a mesma entrada da o mesmo
// desenho.
export const toca = (a, b) => a[0] < b[0] + b[2] && b[0] < a[0] + a[2] && a[1] < b[1] + b[3] && b[1] < a[1] + a[3];
export function rotular(itens, { area, zona = null, linhas = [], ocupado = [], folga = 5 } = {}) {
  const bolas = itens.map((o) => [o.x - o.r, o.y - o.r, 2 * o.r, 2 * o.r]);
  const postos = [...ocupado], saida = itens.map(() => null);
  const cabe = (c) => c[0] >= area[0] && c[1] >= area[1] && c[0] + c[2] <= area[0] + area[2] && c[1] + c[3] <= area[1] + area[3];
  const contem = (z, c) => c[0] >= z[0] && c[1] >= z[1] && c[0] + c[2] <= z[0] + z[2] && c[1] + c[3] <= z[1] + z[3];
  itens.forEach((o, i) => {
    if (!o.w) return;
    const h = o.h ?? 14, g = o.r + folga, { x, y, r, w } = o;
    const cands = [
      [x + g, y - h / 2], [x - g - w, y - h / 2],
      [x - r, y - g - h], [x + r - w, y - g - h], [x - r, y + g], [x + r - w, y + g],
      [x - w / 2, y - g - h], [x - w / 2, y + g],
    ].map(([cx, cy], ordem) => {
      let c = [cx, cy, w, h], custo = ordem;
      if (!cabe(c)) {
        // nome obrigatorio que nao cabe e empurrado para dentro da area, em vez de sumir
        if (!o.obrigatorio) return null;
        c = [Math.max(area[0], Math.min(area[0] + area[2] - w, cx)), Math.max(area[1], Math.min(area[1] + area[3] - h, cy)), w, h];
        custo += 500 + (toca(c, bolas[i]) ? 1000 : 0);
      }
      custo += 1000 * (bolas.filter((b, j) => j !== i && toca(c, b)).length + postos.filter((b) => toca(c, b)).length);
      if (zona && (o.dentro ? !contem(zona, c) : toca(c, zona))) custo += 100;
      custo += 100 * linhas.filter((l) => toca(c, l)).length;
      return { c, custo };
    }).filter(Boolean).sort((a, b) => a.custo - b.custo);
    const m = cands[0];
    if (!m || (m.custo >= 100 && !o.obrigatorio)) return;
    saida[i] = m.c; postos.push(m.c);
  });
  return saida;
}
// numero inteiro curto para eixo: 1.200 vira 1,2 mil
export const curtoNum = (v) => (v >= 1e6 ? `${(v / 1e6).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} mi` : v >= 1e4 ? `${(v / 1e3).toLocaleString('pt-BR', { maximumFractionDigits: 0 })} mil` : v.toLocaleString('pt-BR'));
export const pct = (v) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toLocaleString('pt-BR')}%`;
// marca de corte: duas cunhas na borda do eixo
export const corte = (x, y, dir, cor) => [0, 5].map((d) => ({ type: 'polyline', silent: true,
  shape: { points: [[x - dir * (4 + d), y - 4], [x - dir * d, y], [x - dir * (4 + d), y + 4]] }, style: { stroke: cor, lineWidth: 1.5, fill: 'none' } }));
// limites redondos para eixo logaritmico de contagem (votos)
const REDONDOS = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000];
export function limitesLog(vals) {
  const us = vals.map((v) => Math.max(1, +v || 1));
  const lo = Math.min(...us, 1e12), hi = Math.max(...us, 1);
  const a = [...REDONDOS].reverse().find((r) => r <= lo * 0.9) || 1;
  let b = REDONDOS.find((r) => r >= hi * 1.1) || hi * 2;
  if (b <= a) b = REDONDOS.find((r) => r > a) || a * 10;
  return [a, b];
}
