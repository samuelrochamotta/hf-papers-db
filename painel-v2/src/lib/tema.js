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
export const realce = (t) => ({ scale: 1.3, itemStyle: { borderColor: t.ink, borderWidth: 2, shadowBlur: 0 } });

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
  if (d0 === d1) d1 = d0 + passo;
  return [d0, d1, passo];
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
