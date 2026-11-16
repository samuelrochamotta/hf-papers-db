// Estado compartilhado entre cartoes, indice de papers e painel do paper.
export const estado = $state({
  dados: null,
  erro: null,
  periodo: 'tudo',   // '7' | '14' | 'tudo' (dias de HF Daily, contados do mais recente)
  lentes: [],        // [{k, v}] por faceta: arena, prova, adocao, familia
  sel: null,         // id do paper aberto no painel
  prof: 1,           // profundidade do painel: 1 resumo, 2 trechos, 3 ficha
  comparar: [],      // ate 3 ids no radar
  hover: null,       // id sob o ponteiro, em qualquer grafico
  ordem: 'votos',    // ordem do indice (dados.js ORDENS)
  busca: '',         // texto da busca no indice
  vista: 'papers',   // vista aberta: 'papers' | 'panorama' | 'comparar'
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
// Lentes. Ligar de novo a mesma lente desliga. As lentes se somam (decisao 9
// do redesenho, que substitui a D8 do prototipo v3): valores do mesmo menu se
// alternam (Firme ou Forte) e menus diferentes se exigem juntos (Robotica e Firme).
export const lentesDe = (k) => estado.lentes.filter((l) => l.k === k).map((l) => l.v);
export const temLente = (k, v) => estado.lentes.some((l) => l.k === k && l.v === v);
export function lente(k, v) {
  if (temLente(k, v)) estado.lentes = estado.lentes.filter((l) => !(l.k === k && l.v === v));
  else estado.lentes = [...estado.lentes, { k, v }];
}
export function semLente(k) { estado.lentes = k ? estado.lentes.filter((l) => l.k !== k) : []; }

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
