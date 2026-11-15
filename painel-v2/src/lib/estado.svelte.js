// Estado compartilhado entre cartoes, indice de papers e painel do paper.
export const estado = $state({
  dados: null,
  erro: null,
  periodo: 'tudo',   // '7' | '14' | 'tudo' (dias de HF Daily, contados do mais recente)
  lente: null,       // {k, v}
  sel: null,         // id do paper aberto no painel
  prof: 1,           // profundidade do painel: 1 resumo, 2 trechos, 3 ficha
  comparar: [],      // ate 3 ids no radar
  hover: null,       // id sob o ponteiro, em qualquer grafico
  ordem: 'votos',    // ordem do indice: votos | ganho | solidez
  tema: {},          // cores lidas dos tokens CSS
  modoTema: null,    // null segue o sistema; 'light' | 'dark' escolhido
});

export const MAX_COMPARAR = 3;

// Duracao de transicao que respeita prefers-reduced-motion (o CSS so cobre
// animacoes CSS; as transicoes do Svelte rodam em JS).
export const mov = (ms) => (typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : ms);

export function alternaComparar(id) {
  const i = estado.comparar.indexOf(id);
  if (i >= 0) estado.comparar.splice(i, 1);
  else {
    if (estado.comparar.length >= MAX_COMPARAR) estado.comparar.shift();
    estado.comparar.push(id);
  }
}

export function abrir(id, prof = 1) { estado.sel = id; estado.prof = prof; }
export function fechar() { estado.sel = null; }
export function lente(k, v) {
  estado.lente = estado.lente && estado.lente.k === k && estado.lente.v === v ? null : { k, v };
}

// Tema escolhido pela pessoa: fica no navegador, e o painel funciona sem isso.
// Escolher o mesmo tema do sistema volta a seguir o sistema.
// So a escolha feita no botao passa por essa regra; o tema salvo e aplicado
// como esta, mesmo que hoje coincida com o do sistema.
export function aplicarTema(m, { escolha = true } = {}) {
  if (escolha && m && matchMedia(`(prefers-color-scheme: ${m})`).matches) m = null;
  estado.modoTema = m;
  if (m) document.documentElement.dataset.theme = m; else delete document.documentElement.dataset.theme;
  try { m ? localStorage.setItem('painel-tema', m) : localStorage.removeItem('painel-tema'); } catch {}
}
export function temaSalvo() {
  try { const m = localStorage.getItem('painel-tema'); if (m === 'light' || m === 'dark') aplicarTema(m, { escolha: false }); } catch {}
}
