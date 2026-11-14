// Le os tokens de cor do CSS para os graficos e avisa quando o tema muda
// (preferencia do sistema ou data-theme na raiz).
const NOMES = ['bg', 'surface', 'sunk', 'raise', 'ink', 'ink2', 'muted', 'line', 'accent', 'accent-soft',
  'win', 'noise', 'lose', 'warn', 's-forte', 's-firme', 's-basico', 's-fragil', 's-nada',
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
  return { color: corSolidez(t, p.sol), borderColor: p.sol === 'fragil' ? t.sBasico : 'transparent', borderWidth: p.sol === 'fragil' ? 1 : 0 };
}

export function base(t) {
  return {
    backgroundColor: 'transparent',
    textStyle: { fontFamily: t.body, color: t.ink2 },
    animationDuration: 700,
    animationDurationUpdate: 650,
    animationEasing: 'cubicOut',
    animationEasingUpdate: 'cubicInOut',
    tooltip: {
      backgroundColor: t.raise, borderColor: t.line, borderWidth: 1, padding: [8, 10],
      textStyle: { color: t.ink, fontFamily: t.body, fontSize: 12.5 },
      extraCssText: 'border-radius:12px;box-shadow:0 10px 30px rgba(0,0,0,.18);max-width:280px;white-space:normal;',
      confine: true,
    },
  };
}
