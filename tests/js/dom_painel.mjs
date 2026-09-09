/* DOM minimo para exercitar `scripts/painel_app.js` fora do navegador.
 *
 * O app e uma IIFE que nao exporta nada: o unico jeito de olhar para o estado
 * dele e pelo HTML que ele escreve em `#painel` e pelos handlers de clique que
 * ele registra. E isso que este modulo oferece - renderiza, deixa clicar por
 * rotulo e le de volta as linhas de um menu aberto. Nao e um DOM: e a menor
 * superficie que `render()` toca (getElementById, innerHTML, querySelectorAll,
 * addEventListener) mais o `getBoundingClientRect` que o tooltip chama.
 *
 * Os seletores abaixo casam com o HTML que `montaMenu` e os chips escrevem.
 * Se um deles quebrar depois de uma mudanca de estilo, e aqui que se conserta:
 * o teste continua falando de rotulo e contagem, nao de CSS.
 */
import fs from 'node:fs';
import path from 'node:path';
import url from 'node:url';
import vm from 'node:vm';

const RAIZ = path.resolve(path.dirname(url.fileURLToPath(import.meta.url)), '../..');
const APP = path.join(RAIZ, 'scripts/painel_app.js');
const FONTE = fs.readFileSync(APP, 'utf-8');

const CAIXA_MENU = 'max-height: 288px; overflow-y: auto;';
const CORTINA = /data-c="(\d+)" style="position: fixed; inset: 0; z-index: 80;"/;

export function montarPainel(DADOS) {
  let html = '';
  const handlers = { c: new Map(), e: new Map(), l: new Map(), i: new Map() };

  const painel = {
    id: 'painel',
    set innerHTML(v) { html = v; },
    get innerHTML() { return html; },
    querySelectorAll(seletor) {
      const tipo = seletor.slice(6, 7); // '[data-c]' -> 'c'
      const ids = [...html.matchAll(new RegExp('data-' + tipo + '="(\\d+)"', 'g'))].map((m) => +m[1]);
      return [...new Set(ids)].map((n) => ({
        getAttribute: () => String(n),
        addEventListener: (_tipo, fn) => handlers[tipo].set(n, fn),
      }));
    },
  };
  const tip = {
    style: {},
    set innerHTML(_v) {},
    getBoundingClientRect: () => ({ width: 0, height: 0 }),
  };

  const ctx = vm.createContext({
    DADOS,
    console,
    window: { innerWidth: 1600, innerHeight: 900 },
    document: {
      activeElement: null,
      getElementById: (id) => (id === 'painel' ? painel : id === 'tip' ? tip : null),
    },
  });
  vm.runInContext(FONTE, ctx, { filename: APP });

  function clica(n) {
    const fn = handlers.c.get(n);
    if (!fn) throw new Error('sem handler de clique para ' + n);
    fn();
  }
  function achaUm(re, oque) {
    const m = html.match(re);
    if (!m) throw new Error('nao encontrado no HTML: ' + oque);
    return +m[1];
  }
  function fechaMenu() {
    if (CORTINA.test(html)) clica(achaUm(CORTINA, 'cortina'));
  }

  const api = {
    get html() { return html; },
    clica,

    /* O texto do resumo "Recorte", util para ver o filtro em vigor. */
    get recorte() {
      const m = html.match(/font-size: 12px; color: #6d7178;">([^<]*)<\/span>/);
      return m ? m[1] : '';
    },

    /* Clica no chip de veredito (`estrito`, `amplo`, `fora`). */
    clicaVeredito(v) {
      fechaMenu();
      clica(achaUm(
        new RegExp('data-c="(\\d+)"[^>]*>\\s*<span style="display: inline-block; width: 7px[^"]*"><\\/span>' + v + '<'),
        'chip do veredito ' + v,
      ));
    },

    /* Contagem exibida no chip de veredito. */
    contaVeredito(v) {
      const m = html.match(new RegExp('>' + v + '<span style="margin-left: 7px[^"]*">(\\d+)<'));
      if (!m) throw new Error('chip de veredito ausente: ' + v);
      return +m[1];
    },

    /* Abre o menu do filtro e devolve as linhas dele: [{label, n}].
       Fecha antes o que estiver aberto - o clique no chip e um toggle. */
    menu(rotulo) {
      fechaMenu();
      clica(achaUm(
        new RegExp('data-c="(\\d+)" style="display: inline-flex[^"]*">\\s*<span style="font-size: 10px[^"]*">' + rotulo + '<\\/span>'),
        'chip do menu ' + rotulo,
      ));
      return linhasMenu(html);
    },

    /* Mapa label -> contagem do menu, sem a linha "todos/todas". */
    contagens(rotulo) {
      const mapa = {};
      for (const l of api.menu(rotulo)) if (l.n !== null) mapa[l.label] = l.n;
      return mapa;
    },

    /* Marca (ou desmarca) um item pelo rotulo dentro de um menu. */
    clicaItem(rotulo, label) {
      const linha = api.menu(rotulo).filter((l) => l.label === label)[0];
      if (!linha) throw new Error('linha ausente no menu ' + rotulo + ': ' + label);
      clica(linha.clique);
    },
  };
  return api;
}

function corpoMenu(html) {
  const caixa = html.indexOf(CAIXA_MENU);
  if (caixa < 0) throw new Error('nenhum menu aberto');
  return html.slice(caixa, html.indexOf('</div></div>', caixa));
}

function linhasMenu(html) {
  const re = /<div class="row" data-c="(\d+)"[^>]*>\s*<span style="[^"]*">.*?<\/span><span style="[^"]*">(.*?)<\/span><span style="font-family: 'IBM Plex Mono'[^"]*">(.*?)<\/span>/g;
  return [...corpoMenu(html).matchAll(re)].map((m) => ({
    clique: +m[1],
    label: desescapa(m[2]),
    n: m[3] === '' ? null : +m[3],
  }));
}

function desescapa(s) {
  return s.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"');
}
