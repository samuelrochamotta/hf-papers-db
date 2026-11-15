// Le os tokens de cor do CSS para os graficos e avisa quando o tema muda
// (preferencia do sistema ou data-theme na raiz).
const NOMES = ['bg', 'surface', 'sunk', 'raise', 'ink', 'ink2', 'muted', 'faint', 'line', 'line-strong', 'accent', 'accent-ink', 'accent-soft',
  'warn-soft',
  'win', 'noise', 'norival', 'lose', 'warn', 's-forte', 's-firme', 's-basico', 's-fragil', 's-nada',
  'compare-1', 'compare-2', 'compare-3', 'shade', 'body', 'mono', 'display'];

export function lerTema() {
  const cs = getComputedStyle(document.documentElement);
  const t = {};
  for (const n of NOMES) t[n.replace(/-(\w)/g, (_, c) => c.toUpperCase())] = cs.getPropertyValue(`--${n}`).trim();
  t.escuro = cs.colorScheme === 'dark' || matchMedia('(prefers-color-scheme: dark)').matches
    && document.documentElement.dataset.theme !== 'light';
  if (document.documentElement.dataset.theme === 'dark') t.escuro = true;
  return t;
}

export function observarTema(cb) {
  const mq = matchMedia('(prefers-color-scheme: dark)');
  const f = () => cb(lerTema());
  mq.addEventListener('change', f);
  const mo = new MutationObserver(f);
  mo.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  f();
  return () => { mq.removeEventListener('change', f); mo.disconnect(); };
}

export const corSolidez = (t, s) => ({
  forte: t.sForte, firme: t.sFirme, basico: t.sBasico, fragil: t.sFragil, sem_leitura: 'transparent',
}[s]);

// Estilo do ponto de um paper: uma codificacao so (cor = solidez). Sem leitura
// suficiente vira anel tracejado, para nao parecer "fragil".
export function estiloPonto(t, p) {
  if (p.sol === 'sem_leitura') return { color: 'transparent', borderColor: t.sNada, borderWidth: 1.5, borderType: [3, 2] };
  // fragil e claro demais para 3:1 sobre o fundo: ganha borda da rampa
  if (p.sol === 'fragil') return { color: t.sFragil, borderColor: t.escuro ? t.sBasico : t.sFirme, borderWidth: 1.2 };
  return { color: corSolidez(t, p.sol), borderColor: t.surface, borderWidth: 1 };
}

export function base(t) {
  const reduz = typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;
  return {
    backgroundColor: 'transparent',
    textStyle: { fontFamily: t.body, color: t.ink2 },
    animation: !reduz,
    animationDuration: 600,
    animationDurationUpdate: 500,
    animationEasing: 'cubicOut',
    animationEasingUpdate: 'cubicInOut',
    tooltip: {
      backgroundColor: t.raise, borderColor: t.line, borderWidth: 1, padding: [10, 12],
      textStyle: { color: t.ink, fontFamily: t.body, fontSize: 12.5, lineHeight: 18 },
      extraCssText: `border-radius:10px;box-shadow:0 12px 32px rgba(0,0,0,${t.escuro ? '.5' : '.14'});max-width:300px;white-space:normal;`,
      confine: true, transitionDuration: 0.15,
    },
  };
}

// Eixos com a mesma voz em todos os graficos: rotulo de dado em mono e
// discreto, rotulo de categoria em sans, grade fina e tracejada.
export const rotNum = (t) => ({ color: t.muted, fontFamily: t.mono, fontSize: 10.5 });
export const rotCat = (t, forte = true) => ({ color: forte ? t.ink : t.ink2, fontFamily: t.body, fontSize: 12, fontWeight: forte ? 500 : 400 });
export const grade = (t) => ({ lineStyle: { color: t.line, type: [3, 3] } });
export const realce = (t) => ({ scale: 1.35, itemStyle: { borderColor: t.ink, borderWidth: 2, shadowBlur: 0 } });

// Cabecalho de tooltip padrao: titulo do paper + linhas.
export const dica = (titulo, ...linhas) =>
  `<div style="font-weight:600;margin-bottom:4px;line-height:1.3">${titulo}</div>` +
  linhas.filter(Boolean).map((l) => `<div style="opacity:.78">${l}</div>`).join('');
