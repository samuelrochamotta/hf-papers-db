// Estado compartilhado entre cartoes, faixa de assinaturas e painel do paper.
export const estado = $state({
  dados: null,
  erro: null,
  periodo: 'tudo',   // '7' | '14' | 'tudo' (dias de HF Daily, contados do mais recente)
  lente: null,       // {k, v}
  sel: null,         // id do paper aberto no painel
  prof: 1,           // profundidade do painel: 1 cartao, 2 trechos, 3 ficha
  comparar: [],      // ate 3 ids no radar
  hover: null,       // id sob o ponteiro, em qualquer grafico
  tema: {},          // cores lidas dos tokens CSS
});

export const MAX_COMPARAR = 3;

export function alternaComparar(id) {
  const i = estado.comparar.indexOf(id);
  if (i >= 0) estado.comparar.splice(i, 1);
  else {
    if (estado.comparar.length >= MAX_COMPARAR) estado.comparar.shift();
    estado.comparar.push(id);
  }
}

export function abrir(id) { estado.sel = id; estado.prof = 1; }
export function fechar() { estado.sel = null; }
export function lente(k, v) {
  estado.lente = estado.lente && estado.lente.k === k && estado.lente.v === v ? null : { k, v };
}
