/* Painel Daily Papers - porte do design canvas para HTML/JS puro.
 *
 * O desenho nasceu como artboard `.dc.html` da Claude Design (Artifact
 * "Painel Daily Papers"). Aquele arquivo so roda dentro do runtime do canvas;
 * este e o mesmo layout e a mesma logica de recorte reescritos em JS de
 * navegador, para o painel abrir em qualquer lugar.
 *
 * Desde o ADR 004 (20/10/2026) o painel nao separa mais estrito e amplo. Cada
 * aprovado e localizado pela natureza da afirmacao (`nt`), pela area e
 * sub-area e pela vertente. O pre-requisito (`pr`) continua no banco e nos
 * Parquet, mas saiu do painel em 21/10/2026: como coluna e como perfil de
 * leitura ele confundia mais do que separava. Os descartados seguem pelo
 * veredito e pela regra.
 *
 * Duas diferencas deliberadas em relacao ao original:
 *
 * 1. O tooltip nao passa pelo estado. No canvas cada hover era um setState e
 *    um re-render; com centenas de pontos de dispersao isso pisca no
 *    navegador. Aqui o tooltip e um no fixo que so muda de posicao e texto.
 *
 * 2. A linha de filtro que esta com o menu aberto sobe para z-index 90. No
 *    canvas as linhas ficam em 4/3/2/1 e a cortina de fechar em 80 - o que
 *    deixaria o proprio menu embaixo da cortina num navegador de verdade.
 */
(function () {
  'use strict';

  /* ACCENT e so link e destaque (ticket 04). Aprovado tem cor propria, VERDE,
     e ela vale em todo lugar onde a medida e "quanto passou". */
  var ACCENT = '#d9a441';
  var VERDE = '#4ec07a';

  var root = document.getElementById('painel');
  var elTip = document.getElementById('tip');

  /* ── vocabulario do ADR 004 ──────────────────────────────────────────────
     As naturezas vem do banco (`dim_natureza`), na ordem dele. O marcador de
     nao classificado e o de `gerar_painel.py` - linha migrada do regime
     estrito/amplo que ainda nao passou pela reclassificacao total. */
  var NAO_CLASSIFICADO = '__sem-natureza__';
  var DEF_NAO_CLASSIFICADO = 'Aprovado no regime anterior (estrito/amplo), ainda sem natureza: some com a reclassificação total.';
  var NATUREZAS = (DADOS.naturezas || []).map(function (n) { return n.k; });
  var ROTULO_NATUREZA = {}, DEF_NATUREZA = {};
  (DADOS.naturezas || []).forEach(function (n) { ROTULO_NATUREZA[n.k] = n.r; DEF_NATUREZA[n.k] = n.def || ''; });

  /* Cor CATEGORICA nas quatro naturezas - nao ha ordem entre elas. O nao
     classificado e cinza-azulado escuro; os descartados mantem o cinza de
     sempre. */
  var COR_NATUREZA = {
    proposta: '#4fb3c8', achado_empirico: '#8a6fe0', teoria: '#d55181', panorama: '#b39a72'
  };
  COR_NATUREZA[NAO_CLASSIFICADO] = '#4d5a68';
  var COR_FORA = '#6b7480';
  function natureza(p) { return p.nt || NAO_CLASSIFICADO; }
  function corNatureza(k) { return COR_NATUREZA[k] || '#8b8f96'; }
  function corPaper(p) { return p.v === 'fora' ? COR_FORA : corNatureza(natureza(p)); }
  function rotuloNatureza(k) { return k && k !== NAO_CLASSIFICADO ? (ROTULO_NATUREZA[k] || String(k)) : 'não classificado'; }

  var state = {
    aba: 'aprovados',
    diasSel: [], vereditos: [], areas: [], subareas: [], vertentes: [], orgs: [],
    // Natureza e marcas so recortam os aprovados: um descartado nao tem
    // nenhuma das duas, e continua respondendo so ao veredito e a regra.
    naturezas: [], marcas: [],
    // recorte que so o grafico produz: o clique no Pareto de descartes
    regrasFora: [],
    // `busca` e o que esta no campo; `buscaQ` e o que esta valendo no
    // recorte. Os dois se separam pelo debounce: buscar no texto da ficha de
    // centenas de papers a cada tecla travaria a digitacao.
    busca: '', buscaQ: '', aberta: null,
    // dia exibido na aba Aprovados (paginacao por dia); null = o mais recente
    diaPag: null,
    menu: null, buscaMenu: '',
    perSel: null, abertaH: null,
    vistaArea: 'dist', ghVeredito: '',
    justExp: {}
  };

  /* Handlers vivem num array reconstruido a cada render; o HTML so carrega o
     indice. Evita serializar funcao em atributo. */
  var H = [];
  function h(fn) { H.push(fn); return H.length - 1; }
  function ev(tipo, fn) { return ' data-' + tipo + '="' + h(fn) + '"'; }

  function esc(v) {
    if (v === null || v === undefined) return '';
    return String(v)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  /* Corta no ultimo espaco antes do limite e sinaliza o corte. Sem as
     reticencias o leitor nao distingue um titulo truncado de um titulo curto -
     "Beyond Data Scaling: Representatio" parece um erro de digitacao. */
  function rotuloCurto(texto, limite) {
    var t = String(texto || '');
    if (t.length <= limite) return t;
    var corte = t.slice(0, limite);
    var porPalavra = corte.replace(/\s+\S*$/, '');
    /* Quando nao sobra palavra inteira - titulo de uma palavra so, ou titulo
       que comeca com espaco - o corte por palavra devolve vazio e o rotulo
       viraria so "…". Nesse caso vale o corte cru, que ao menos informa. */
    return (porPalavra.trim() ? porPalavra : corte.trim()) + '…';
  }

  /* O par que localiza o paper na arquitetura: a peca do sistema em que ele
     mexe e a sub-area dela. Os dois juntos, porque a sub-area sozinha nao diz
     de quem e filha e a area sozinha e a informacao que o painel ja dava. */
  function parArea(p) {
    if (!p.a) return '\u2014';
    return p.sa ? p.a + ' \u203a ' + p.sa : p.a;
  }

  /* A vertente que manda no paper. `p.vt` vem ordenado por `ordem`, entao e a
     primeira; a chave do vazio existe porque um paper sem vertente nenhuma
     precisa continuar contavel - some-lo faria a soma das barras nao bater com
     o total do recorte. */
  var VERTENTE_NULA = '__sem-vertente__';
  function dominante(p) { return (p.vt && p.vt[0]) || VERTENTE_NULA; }
  /* Celula VERTENTE das listas: a dominante, e as outras no tooltip. */
  function celulaVertente(p) {
    var d = dominante(p);
    var outras = (p.vt || []).slice(1);
    return '<span' + (outras.length ? ev('e', mostraTip(d, 'também: ' + outras.join(', '), 'vertentes')) + ev('l', escondeTip()) : '') +
      ' style="font-size: 11.5px; color: ' + (d === VERTENTE_NULA ? '#5f636a' : '#a8a49b') + '; line-height: 1.5;">' +
      esc(d === VERTENTE_NULA ? '—' : d) + (outras.length ? '<span style="color: #5f636a;"> +' + outras.length + '</span>' : '') + '</span>';
  }

  function setState(patch) {
    for (var k in patch) if (Object.prototype.hasOwnProperty.call(patch, k)) state[k] = patch[k];
    render();
  }

  /* Paleta exclusiva de composição. Cor + textura identificam as categorias;
     os dez estilos preservam a capacidade anterior sem reutilizar vereditos. */
  var RAMPA = ['#E8E0D4', '#CFC0AD', '#B3A18D', '#95816F', '#786454'];
  var MAX_FATIAS = RAMPA.length * 2;
  function hachura(tom) {
    return 'repeating-linear-gradient(135deg, transparent 0px, transparent 3px, rgba(24,20,17,0.6) 3px, rgba(24,20,17,0.6) 5px), ' + tom;
  }
  var FUNDO_OUTRAS = 'repeating-linear-gradient(0deg, transparent 0px, transparent 3px, #95816F 3px, #95816F 4px), #211e1b';
  function tons(n) {
    n = Math.min(n, MAX_FATIAS);
    var estilos = [];
    for (var i = 0; i < n; i++) {
      var indice = n <= RAMPA.length && n > 1
        ? Math.round(i * (RAMPA.length - 1) / (n - 1)) : i % RAMPA.length;
      estilos.push(i < RAMPA.length ? RAMPA[indice] : hachura(RAMPA[indice]));
    }
    return estilos;
  }
  function contornoFatia(k) {
    return k === '__outras__' || k === VERTENTE_NULA
      ? 'box-shadow: inset 0 0 0 1px #95816F;' : '';
  }

  /* Chave do motivo de descarte. `regra_fora` e obrigatoria em todo `fora`
     desde o ticket 02; o nulo continua contavel para o dia em que voltar. */
  var REGRA_NULA = '__sem-regra__';
  function chaveRegra(p) { return p.rf || REGRA_NULA; }

  /* Rotulos das regras de descarte. As tres primeiras sao as vigentes
     (`schemas.REGRAS_FORA`, na ordem de teste); as tres seguintes sairam no
     ADR 004 e so aparecem em linhas anteriores a reclassificacao total - por
     isso o "(regra antiga)": sem ele o Pareto pareceria dizer que o pipeline
     ainda descarta treino. */
  var ROTULOS_REGRA = {
    geracao_de_midia: 'geração de mídia',
    percepcao_robotica_embodied: 'percepção, robótica, embodied',
    fora_de_escopo: 'fora de escopo',
    treino_ou_postreino: 'treino ou pós-treino (regra antiga)',
    relatorio_tecnico_de_modelo: 'relatório técnico de modelo (regra antiga)',
    portabilidade_reprovada: 'portabilidade reprovada (regra antiga)'
  };
  ROTULOS_REGRA[REGRA_NULA] = 'regra não registrada';
  function rotulo(k) {
    return Object.prototype.hasOwnProperty.call(ROTULOS_REGRA, k) ? ROTULOS_REGRA[k] : String(k);
  }

  /* As tres marcas de um aprovado. `ao` e o artefato aberto do ADR 004
     (evidencia externa + "liberado"); `pc` e `fo` existem quando o texto
     correspondente foi escrito. Marcar duas e pedir as duas (AND). */
  var MARCAS = [
    { k: 'ao', r: 'artefato aberto', def: 'Repositório, pesos ou dataset liberados — evidência no HF ou no abstract, confirmada como liberada.' },
    { k: 'pc', r: 'contradiz prática', def: 'O achado contradiz algo que o leitor plausivelmente faz hoje; a prática vem nomeada na ficha.' },
    { k: 'fo', r: 'somente princípio', def: 'O princípio é portável, mas o paper não diz como implementar.' }
  ];
  function temMarca(p, k) { return !!p[k]; }

  var fichaPorId = {};
  (DADOS.fichas || []).forEach(function (f) { fichaPorId[f.p] = f; });

  /* Indice da busca, montado uma vez no carregamento: titulo, organizacao, id,
     justificativa, os dois textos da classificacao e os campos da ficha, tudo
     em minusculas. A busca vira um `indexOf` por paper. */
  var INDICE = {};
  DADOS.papers.forEach(function (p) {
    var f = fichaPorId[p.id] || {};
    INDICE[p.id] = [p.t, p.org, p.id, p.j, p.pc, p.fo, f.ach, f.imp, f.ex, f.res]
      .filter(Boolean).join(' \n ').toLowerCase();
  });

  /* `exceto` deixa uma ou mais dimensoes de fora: e o que mantem as outras
     opcoes de um seletor visiveis depois que ele ja filtrou (senao marcar a 2a
     area pelo grafico ficaria impossivel - a 1a teria apagado as demais
     barras). Aceita string ou array: a matriz natureza x vertente precisa
     soltar as duas dimensoes dela de uma vez.

     Natureza e marcas so recortam APROVADOS. Um descartado passa por elas
     sempre: ele nao tem nenhuma das duas, e o recorte dele e o veredito e a
     regra. Sem isso marcar uma natureza zeraria os descartados do Panorama, e
     o lote diario deixaria de mostrar o que foi cortado. */
  function filtrados(exceto) {
    var s = state;
    var q = (s.buscaQ || '').trim().toLowerCase();
    var solta = typeof exceto === 'string' ? [exceto] : (exceto || []);
    function livre(dim) { return solta.indexOf(dim) >= 0; }
    return DADOS.papers.filter(function (p) {
      if (!livre('diasSel') && s.diasSel.length && s.diasSel.indexOf(p.d) < 0) return false;
      if (!livre('vereditos') && s.vereditos.length && s.vereditos.indexOf(p.v) < 0) return false;
      // dentro de cada dimensao a selecao e OR; entre dimensoes, AND
      if (!livre('areas') && s.areas.length && s.areas.indexOf(p.a) < 0) return false;
      if (!livre('subareas') && s.subareas.length && s.subareas.indexOf(p.sa) < 0) return false;
      // Vertente DOMINANTE, nao "tem a vertente": `p.vt` chega ordenado por
      // `ponte_paper_vertente.ordem` e a primeira e a que manda.
      if (!livre('vertentes') && s.vertentes.length &&
        s.vertentes.indexOf(dominante(p)) < 0) return false;
      // marcar uma regra e marcar um recorte de descartados
      if (!livre('regrasFora') && s.regrasFora.length && (p.v !== 'fora' || s.regrasFora.indexOf(chaveRegra(p)) < 0)) return false;
      if (p.v === 'aprovado') {
        if (!livre('naturezas') && s.naturezas.length && s.naturezas.indexOf(natureza(p)) < 0) return false;
        if (!livre('marcas') && s.marcas.length &&
          !s.marcas.every(function (k) { return temMarca(p, k); })) return false;
      }
      if (!livre('orgs') && s.orgs.length) {
        var chave = p.org || '__sem-org__';
        if (s.orgs.indexOf(chave) < 0) return false;
      }
      if (q && INDICE[p.id].indexOf(q) < 0) return false;
      return true;
    });
  }

  /* liga/desliga um valor numa dimensao de selecao multipla */
  function alternaLista(campo, valor) {
    var l = state[campo].slice();
    var i = l.indexOf(valor);
    if (i < 0) l.push(valor); else l.splice(i, 1);
    // `aberta` some porque o card que estava aberto pode nem sobreviver ao
    // novo recorte; `justExp` some pelo mesmo motivo
    var novo = { aberta: null, justExp: {} };
    novo[campo] = l;
    setState(novo);
  }

  /* Debounce da busca: o campo guarda o texto na hora (sem re-render, que
     trocaria o input no meio da digitacao) e o recorte so muda depois de uma
     pausa. Sem `setTimeout` (ambiente minimo de teste) aplica direto. */
  var ESPERA_BUSCA = 220;
  var timerBusca = null;
  function digitaBusca(valor) {
    state.busca = valor;
    if (typeof setTimeout !== 'function') {
      setState({ buscaQ: valor, aberta: null, justExp: {}, diaPag: null });
      return;
    }
    if (timerBusca !== null && typeof clearTimeout === 'function') clearTimeout(timerBusca);
    timerBusca = setTimeout(function () {
      timerBusca = null;
      setState({ buscaQ: state.busca, aberta: null, justExp: {}, diaPag: null });
    }, ESPERA_BUSCA);
  }


  /* Tooltip de N linhas. A primeira e o rotulo (tip1), a ultima e o numero
     (tip2, mono) e o que estiver no meio e prosa (tipd) - e por onde entram as
     definicoes da taxonomia, que sao frase e nao medida. Chamado com dois
     argumentos o resultado e exatamente o de antes, que e como a maior parte
     do painel ainda o chama. Linha falsy some, para o chamador nao precisar
     montar a lista condicionalmente. */
  function mostraTip() {
    var linhas = [], i;
    for (i = 0; i < arguments.length; i++) if (arguments[i]) linhas.push(arguments[i]);
    var corpo = linhas.map(function (l, k) {
      var classe = k === 0 ? 'tip1' : (k === linhas.length - 1 ? 'tip2' : 'tipd');
      return '<div class="' + classe + '">' + esc(l) + '</div>';
    }).join('');
    return function (e) {
      elTip.innerHTML = corpo;
      elTip.style.display = 'block';
      elTip.style.left = '0px';
      elTip.style.top = '0px';
      var box = elTip.getBoundingClientRect();
      elTip.style.left = Math.max(8, Math.min(e.clientX + 16, window.innerWidth - box.width - 8)) + 'px';
      elTip.style.top = Math.max(8, Math.min(e.clientY + 16, window.innerHeight - box.height - 8)) + 'px';
    };
  }
  function escondeTip() { return function () { elTip.style.display = 'none'; }; }

  /* Quartil por interpolacao linear, usado tambem para a mediana (q = 0,5).
     Havia uma `mediana` propria, que arredondava para inteiro porque so media
     votos; ela saiu quando a curva de maturacao passou a medir PORCENTAGEM do
     voto final - arredondar ali perderia o cruzamento dos 90% por menos de um
     ponto. */
  function quartil(xs, q) {
    if (!xs.length) return 0;
    var o = xs.slice().sort(function (a, b) { return a - b; });
    var pos = (o.length - 1) * q;
    var lo = Math.floor(pos), hi = Math.ceil(pos);
    if (lo === hi) return o[lo];
    return o[lo] + (o[hi] - o[lo]) * (pos - lo);
  }
  /* Passo "redondo" (1, 2, 5, 10 · 10^k) para um eixo de dias: fixar o passo
     quebraria quando um recorte deixasse a janela com poucos dias. */
  function passoEixo(intervalo, alvo) {
    var bruto = intervalo / Math.max(1, alvo);
    var mag = Math.pow(10, Math.floor(Math.log(bruto) / Math.LN10));
    var n = bruto / mag;
    return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * mag;
  }
  function diaCurto(iso) {
    if (!iso) return '—';
    var p = iso.split('-');
    return p[2] + '/' + p[1];
  }
  /* Dias desde a epoca, para subtrair duas datas ISO sem aritmetica de Date -
     que em fuso local erra por um dia perto do horario de verao. */
  function diaNum(iso) {
    if (!iso) return null;
    var p = iso.split('-');
    return Math.round(Date.UTC(+p[0], +p[1] - 1, +p[2]) / 86400000);
  }
  function pct(n, total) { return total ? Math.round((n / total) * 100) : 0; }
  function escalaLog(v, max) {
    if (max <= 0) return 0;
    return (Math.log(1 + v) / Math.log(1 + max)) * 100;
  }
  /* Ticks de um eixo log1p: os valores redondos que ainda cabem, mais o
     maximo. Derivados do maximo, nunca fixos - com um recorte que baixe o teto,
     escalaLog(160, 50) da 129% e o rotulo sai do container. A folga de 7% e o
     que impede 400 e 510 de virarem um borrao: na escala log eles ficam a
     quatro pixels um do outro, e quem tem de sobreviver e o maximo. */
  function ticksLog(max) {
    if (max <= 0) return [0];
    var out = [0];
    [5, 20, 60, 160, 400, 1000, 2500].concat([max]).forEach(function (v) {
      if (v <= 0 || v > max) return;
      var ultimo = out[out.length - 1];
      if (v === max) {
        while (out.length > 1 && escalaLog(v, max) - escalaLog(out[out.length - 1], max) < 7) out.pop();
        if (v !== out[out.length - 1]) out.push(v);
        return;
      }
      if (escalaLog(v, max) - escalaLog(ultimo, max) >= 7) out.push(v);
    });
    return out;
  }

  /* ── plano cartesiano em SVG ───────────────────────────────────────────────
     Os cards sao fluidos, entao o viewBox e 0-100 nos dois eixos e o desenho
     estica junto (`preserveAspectRatio: none`). `vector-effect` e o que impede
     a espessura do traco de esticar com ele. Ponto e circulo continuam sendo
     div posicionada por porcentagem: dentro do viewBox esticado eles virariam
     elipse. `y` ja chega invertido (0 no topo), como o SVG espera. */
  function svgPlano(conteudo) {
    return '<svg viewBox="0 0 100 100" preserveAspectRatio="none" style="position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; pointer-events: none;">' + conteudo + '</svg>';
  }
  function poliLinha(pts, c, larg, tracos) {
    if (pts.length < 2) return '';
    return '<polyline points="' + pts.map(function (p) { return p[0] + ',' + p[1]; }).join(' ') +
      '" fill="none" stroke="' + c + '" stroke-width="' + larg + '" vector-effect="non-scaling-stroke"' +
      (tracos ? ' stroke-dasharray="' + tracos + '"' : '') +
      ' stroke-linejoin="round" stroke-linecap="round"></polyline>';
  }
  function poliArea(pts, c, opacidade) {
    if (pts.length < 3) return '';
    return '<polygon points="' + pts.map(function (p) { return p[0] + ',' + p[1]; }).join(' ') +
      '" fill="' + c + '" opacity="' + opacidade + '" stroke="none"></polygon>';
  }
  /* Quebra a serie nos buracos: com `n` abaixo do minimo a mediana daquela
     idade nao existe, e ligar os dois lados inventaria o ponto que falta. */
  function trechos(pontos) {
    var out = [], atual = [];
    pontos.forEach(function (p) {
      if (p === null) { if (atual.length) out.push(atual); atual = []; }
      else atual.push(p);
    });
    if (atual.length) out.push(atual);
    return out;
  }

  /* pilula de filtro: arredondada, com estados legiveis no escuro */
  function pill(on, corOn) {
    var base = 'display: inline-flex; align-items: center; gap: 0; font-size: 12.5px; line-height: 1; padding: 8px 15px; border-radius: 100px; white-space: nowrap;';
    if (!on) return base + ' background: #1b1f23; border: 1px solid #2b3138; color: #a8a49b;';
    if (corOn) return base + ' background: ' + corOn + '26; border: 1px solid ' + corOn + '; color: ' + corOn + '; font-weight: 500;';
    return base + ' background: #d9a441; border: 1px solid #d9a441; color: #14161a; font-weight: 600;';
  }

  /* Alternador de vista dentro de um card. Pilula menor e sem contador: ela
     nao filtra nada - troca o que o card desenha (Distribuicao|Sub-areas|
     Vertentes, dia|semana). */
  function chipVista(rotulo, on, fn) {
    return '<div class="' + (on ? 'chip chip-on' : 'chip') + '"' + ev('c', fn) +
      ' style="' + (on ? pillOnGlobal() : pill(false)) + ' font-size: 11.5px; padding: 6px 12px;">' + esc(rotulo) + '</div>';
  }

  var SVG_CHEVRON = '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 9l7 7 7-7"></path></svg>';
  var SVG_CHECK = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12.5l5.5 5.5L20 7"></path></svg>';

  /* Menu suspenso de selecao multipla (dia, area, organizacao).
     `campo` e a chave de estado; `itens` e [{valor, label, n}] ja ordenado. */
  function montaMenu(rotulo, campo, itens, opcoes) {
    var s = state;
    var aberto = s.menu === campo;
    var marcados = s[campo];
    var temBusca = itens.length > 12;
    var q = aberto && temBusca ? (s.buscaMenu || '').trim().toLowerCase() : '';
    var visiveis = q ? itens.filter(function (i) { return i.label.toLowerCase().indexOf(q) >= 0; }) : itens;
    var rotuloTodos = (opcoes && opcoes.todos) || 'todos';

    // caixa de selecao desenhada: o clique alterna e o menu FICA aberto,
    // senao marcar tres areas exigiria reabrir o menu tres vezes
    function caixa(marcado) {
      return 'display: inline-flex; align-items: center; justify-content: center; width: 15px; height: 15px; border-radius: 4px; ' +
        (marcado
          ? 'background: ' + ACCENT + '; border: 1px solid ' + ACCENT + '; color: #14161a;'
          : 'background: #16191c; border: 1px solid #3a4149; color: transparent;');
    }

    var linhas = [{
      label: rotuloTodos, n: '',
      style: 'display: grid; grid-template-columns: 15px minmax(0, 1fr) auto; gap: 10px; align-items: center; padding: 9px 13px; cursor: pointer; border-bottom: 1px solid #242a30;',
      check: caixa(marcados.length === 0),
      labelStyle: 'font-size: 12.5px; color: ' + (marcados.length === 0 ? '#f5f3ee' : '#8b8f96') + ';',
      click: function () {
        var novo = { aberta: null, justExp: {} };
        novo[campo] = [];
        setState(novo);
      }
    }].concat(visiveis.map(function (i) {
      var marcado = marcados.indexOf(i.valor) >= 0;
      return {
        label: i.label, n: i.n,
        style: 'display: grid; grid-template-columns: 15px minmax(0, 1fr) auto; gap: 10px; align-items: center; padding: 9px 13px; cursor: pointer;',
        check: caixa(marcado),
        labelStyle: 'font-size: 12.5px; color: ' + (marcado ? '#f5f3ee' : '#a8a49b') + '; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;',
        click: function () { alternaLista(campo, i.valor); }
      };
    }));

    var nomes = marcados.map(function (v) {
      var achado = itens.filter(function (i) { return i.valor === v; })[0];
      return achado ? achado.label : v;
    });
    var valorLabel = marcados.length === 0 ? rotuloTodos
      : (marcados.length === 1 ? nomes[0] : marcados.length + ' selecionados');
    var ativo = marcados.length > 0;

    var botao = 'display: inline-flex; align-items: center; gap: 9px; font-size: 12.5px; line-height: 1; padding: 9px 14px; border-radius: 100px; white-space: nowrap; max-width: 340px; ' +
      (ativo
        ? 'background: ' + ACCENT + '1f; border: 1px solid ' + ACCENT + '; color: #f5f3ee;'
        : 'background: #1b1f23; border: 1px solid #2b3138; color: #a8a49b;');
    var contadorStyle = marcados.length > 1
      ? 'display: inline-flex; align-items: center; justify-content: center; min-width: 18px; height: 18px; padding: 0 5px; border-radius: 100px; background: ' + ACCENT + '; color: #14161a; font-family: \'IBM Plex Mono\', monospace; font-size: 11px; font-weight: 500;'
      : 'display: none;';

    var html = '<div style="position: relative;">' +
      '<div class="chip"' + ev('c', function () { setState({ menu: aberto ? null : campo, buscaMenu: '' }); }) + ' style="' + botao + '">' +
        '<span style="font-size: 10px; font-weight: 600; letter-spacing: 0.13em; color: ' + (ativo ? ACCENT : '#6d7178') + ';">' + esc(rotulo) + '</span>' +
        '<span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 196px; color: ' + (ativo ? '#f5f3ee' : '#a8a49b') + ';">' + esc(valorLabel) + '</span>' +
        '<span style="' + contadorStyle + '">' + (marcados.length > 1 ? marcados.length : '') + '</span>' +
        '<span style="display: inline-flex; color: ' + (ativo ? ACCENT : '#6d7178') + '; transform: rotate(' + (aberto ? '180deg' : '0deg') + '); transition: transform 140ms ease;">' + SVG_CHEVRON + '</span>' +
      '</div>';

    if (aberto) {
      html += '<div style="position: absolute; top: calc(100% + 7px); left: 0; z-index: 81; width: 306px; background: #1b1f23; border: 1px solid #333a41; border-radius: 6px; box-shadow: 0 18px 42px rgba(0,0,0,0.55); overflow: hidden;">';
      if (temBusca) {
        html += '<div style="padding: 10px 11px; border-bottom: 1px solid #242a30;">' +
          '<input id="q-menu" class="busca" type="text" value="' + esc(s.buscaMenu || '') + '"' +
          ev('i', function (e) { setState({ buscaMenu: e.target.value }); }) +
          ' placeholder="filtrar lista" style="font-family: \'Instrument Sans\', sans-serif; font-size: 12.5px; padding: 7px 12px; width: 100%; border: 1px solid #2b3138; border-radius: 5px; background: #16191c; color: #ecebe6; outline: none;">' +
          '</div>';
      }
      html += '<div style="max-height: 288px; overflow-y: auto;">' +
        linhas.map(function (i) {
          return '<div class="row"' + ev('c', i.click) + ' style="' + i.style + '">' +
            '<span style="' + i.check + '">' + SVG_CHECK + '</span>' +
            '<span style="' + i.labelStyle + '">' + esc(i.label) + '</span>' +
            '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 11.5px; color: #6d7178;">' + esc(i.n) + '</span>' +
            '</div>';
        }).join('') +
        '</div>';
      if (visiveis.length === 0) {
        html += '<div style="padding: 20px 14px; text-align: center; font-size: 12.5px; color: #6d7178;">Nada encontrado.</div>';
      }
      html += '</div>';
    }
    return html + '</div>';
  }

  /* Os quatro campos da ficha exibidos, na ordem normativa, cada um com sua
     cor (slots dark do catalogo, validados contra o fundo do card). O Padrao
     Extraido continua no banco e nos Parquet, mas saiu do painel em
     21/10/2026: repetia o que o achado e "o que muda para voce" ja dizem. */
  function camposFicha(f) {
    var cores = {
      'ACHADO': '#199e70',
      'O QUE MUDA PARA VOCÊ': '#d55181',
      'EXEMPLO CONCRETO': '#9085e9',
      'RESSALVA': '#e66767'
    };
    var bruto = [
      { rotulo: 'ACHADO', texto: f.ach, nome: '', largo: true },
      { rotulo: 'O QUE MUDA PARA VOCÊ', texto: f.imp, nome: '', largo: false },
      { rotulo: 'EXEMPLO CONCRETO', texto: f.ex, nome: '', largo: false },
      { rotulo: 'RESSALVA', texto: f.res, nome: '', largo: true }
    ];
    return bruto.map(function (c) {
      var cr = cores[c.rotulo];
      return {
        rotulo: c.rotulo, texto: c.texto, nome: c.nome,
        wrap: c.largo ? 'grid-column: 1 / -1;' : '',
        regua: 'height: 2px; width: 34px; background: ' + cr + '; margin-bottom: 10px;',
        rotuloStyle: 'font-size: 10.5px; font-weight: 600; letter-spacing: 0.16em; color: ' + cr + '; margin-bottom: 8px;',
        nomeStyle: c.nome
          ? 'font-family: \'Instrument Sans\', system-ui, sans-serif; font-size: 17px; font-weight: 600; line-height: 1.32; letter-spacing: -0.01em; color: #f7f5f0; margin-bottom: 9px;'
          : 'display: none;'
      };
    });
  }

  /* Acima de 320 caracteres o texto e cortado com "mais". 320 fica acima do
     `maxLength: 300` do schema do Estagio B (src/hfpapers/llm/schemas.py) -
     isto e rede de seguranca para texto que escapou do limite, nao interacao
     de todo card: a maioria nunca precisa do botao. */
  var LIMITE_JUSTIFICATIVA = 320;

  /* Traduz o codigo de `justificativa_exibivel` (gerar_painel.py) para o aviso
     que substitui o texto - ou `null` quando ha texto de verdade para mostrar.
     Unica funcao a interpretar `h`: os tres consumidores do contrato (a lista
     da janela, os aprovados e os descartados do hall) chamam esta funcao em
     vez de testar `h` por si, porque um `if (p.h)` cru trata qualquer valor
     diferente de zero como falha do Estagio B - e o codigo 3 (justificativa
     vazia gravada pelo proprio pipeline) e um caso vivo em
     `estagios/classificacao.py`, nao hipotetico.
     So o codigo 0 devolve `null` (ha texto). Qualquer outro valor, `undefined`
     incluido, cai no aviso residual - a guarda e invertida de proposito: o
     painel publica sozinho as 08:30, e um `h` fora do contrato nao pode virar
     cabecalho com rotulo e corpo vazio. */
  function avisoDecisao(h) {
    if (h === 2) return 'O Estágio B não concluiu neste paper — o veredito é preliminar.';
    // codigo 3 e qualquer residual: a decisao pode ter sido so do Estagio A
    // (classificacao.py:206 grava "fora" sem o B chegar a rodar), entao o
    // aviso nao pode apontar o dedo para um estagio especifico.
    if (h !== 0) return 'O pipeline não registrou motivo para esta decisão.';
    return null;
  }

  /* Selo da natureza: a pilula com a cor categorica. Usado no card
     recolhido, no cabecalho da decisao e no hall - um desenho so. */
  function seloNatureza(k) {
    var c = corNatureza(k || NAO_CLASSIFICADO);
    return '<span' + ev('e', mostraTip(rotuloNatureza(k), k ? (DEF_NATUREZA[k] || '') : DEF_NAO_CLASSIFICADO, 'natureza')) + ev('l', escondeTip()) +
      ' style="display: inline-flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 600; letter-spacing: 0.02em; padding: 4px 9px; border-radius: 100px; white-space: nowrap; color: ' + c +
      '; background: ' + c + '1f; border: 1px solid ' + c + '59;">' + esc(rotuloNatureza(k)) + '</span>';
  }

  /* Cabecalho da decisao: por que esta classificacao, acima dos
     cinco campos da ficha (ou sozinho, quando nao ha ficha). Nao e um sexto
     campo - os cinco falam do paper, este fala da classificacao -, entao ele
     nao usa a regua colorida de `camposFicha`: uma barra lateral na cor da
     natureza e texto em italico o separam dos cinco. Embaixo dele vem os dois
     textos da classificacao, quando existem: a pratica que o achado contradiz
     e o que falta para implementar.
     `p` precisa de {v, pr, nt, j, h}; `chave` identifica o card para o estado
     do "mais" (aba viva e historica podem ter cards abertos ao mesmo tempo). */
  function cabecalhoDecisao(p, chave) {
    if (p.v !== 'aprovado') return '';
    var corV = corNatureza(natureza(p));

    var miolo;
    var aviso = avisoDecisao(p.h);
    if (aviso) {
      miolo = '<div style="font-size: 12.5px; font-style: italic; color: #6d7178;">' + aviso + '</div>';
    } else {
      var texto = p.j || '';
      var aberto = !!state.justExp[chave];
      var precisaCortar = texto.length > LIMITE_JUSTIFICATIVA;
      var exibido = (precisaCortar && !aberto) ? rotuloCurto(texto, LIMITE_JUSTIFICATIVA) : texto;
      var botaoMais = precisaCortar
        ? ' <span class="mais" style="font-size: 12px;"' +
          ev('c', function () {
            var m = {};
            for (var x in state.justExp) if (Object.prototype.hasOwnProperty.call(state.justExp, x)) m[x] = state.justExp[x];
            m[chave] = !aberto;
            setState({ justExp: m });
          }) + '>' + (aberto ? 'menos' : 'mais') + '</span>'
        : '';
      miolo = '<div style="font-family: Newsreader, Georgia, serif; font-size: 15px; font-style: italic; font-weight: 300; line-height: 1.62; color: #c9c5bb; text-wrap: pretty;">' + esc(exibido) + botaoMais + '</div>';
    }

    function texto2(rotuloT, valor) {
      if (!valor) return '';
      return '<div style="display: grid; grid-template-columns: 150px minmax(0, 1fr); gap: 14px; margin-top: 12px;">' +
        '<span style="font-size: 10.5px; font-weight: 600; letter-spacing: 0.14em; color: #8b8f96; padding-top: 2px;">' + rotuloT + '</span>' +
        '<span style="font-size: 13px; line-height: 1.55; color: #d5d1c8;">' + esc(valor) + '</span>' +
        '</div>';
    }

    return '<div style="border-left: 2px solid ' + corV + '; padding: 1px 0 1px 16px; margin-bottom: 22px;">' +
      '<div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 8px;">' +
        '<span style="font-size: 11px; font-weight: 600; letter-spacing: 0.14em; color: ' + corV + ';">POR QUE ESTA CLASSIFICAÇÃO</span>' +
        seloNatureza(p.nt) +
      '</div>' +
      miolo +
      texto2('CONTRADIZ A PRÁTICA', p.pc) +
      texto2('SOMENTE PRINCÍPIO', p.fo) +
      '</div>';
  }

  /* Links do paper no rodape da ficha: o HF sempre; o repositorio e a pagina
     do projeto quando existem. */
  function linksPaper(p) {
    var out = '<a href="' + esc(p.url) + '" target="_blank" rel="noopener" style="font-family: \'IBM Plex Mono\', monospace; font-size: 12px;">' + esc(p.id) + ' ↗</a>';
    if (p.gh) out += '<a href="' + esc(p.gh) + '" target="_blank" rel="noopener" style="font-size: 12px;">repositório ↗</a>';
    if (p.pg) out += '<a href="' + esc(p.pg) + '" target="_blank" rel="noopener" style="font-size: 12px;">página do projeto ↗</a>';
    return out;
  }

  /* O corpo aberto de um aprovado, igual na aba viva e no hall. */
  function corpoAberto(p, f, chave, extraRodape) {
    var corpo = '<div style="padding: 10px 24px 30px;">' + cabecalhoDecisao(p, chave);
    if (f) {
      corpo += '<div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 24px 40px;">' +
        camposFicha(f).map(function (c) {
          return '<div style="' + c.wrap + '">' +
            '<div style="' + c.regua + '"></div>' +
            '<div style="' + c.rotuloStyle + '">' + c.rotulo + '</div>' +
            '<div style="' + c.nomeStyle + '">' + esc(c.nome) + '</div>' +
            '<div style="font-family: Newsreader, Georgia, serif; font-size: 16px; font-weight: 300; line-height: 1.68; color: #d5d1c8; text-wrap: pretty;">' + esc(c.texto) + '</div>' +
            '</div>';
        }).join('') +
        '</div>';
    } else {
      corpo += '<div style="font-size: 12.5px; color: #6d7178; padding: 6px 0 14px;">Aprovado sem ficha gerada — o Estágio B não chegou a escrevê-la.</div>';
    }
    corpo += '<div style="display: flex; gap: 20px; align-items: center; flex-wrap: wrap; margin-top: 24px; padding-top: 16px; border-top: 1px solid #242a30;">' +
        linksPaper(p) +
        '<span style="font-size: 11.5px; color: #6d7178;">' + esc((p.vt || []).join(' · ')) + '</span>' +
        (extraRodape || '') +
      '</div>' +
      '</div>';
    return corpo;
  }

  /* Marcas do card recolhido: contradiz pratica e artefato aberto (com link
     direto para o repositorio, quando ha). */
  function marcasCard(p) {
    var out = '';
    if (p.pc) {
      out += '<span' + ev('e', mostraTip('contradiz prática', p.pc, 'marca')) + ev('l', escondeTip()) +
        ' style="font-size: 10.5px; color: #e8a37c; border: 1px solid #e8a37c59; border-radius: 100px; padding: 3px 8px; white-space: nowrap;">≠ prática</span>';
    }
    if (p.ao) {
      out += p.gh
        ? '<a href="' + esc(p.gh) + '" target="_blank" rel="noopener" onclick="event.stopPropagation()" style="font-size: 10.5px; white-space: nowrap; border-bottom: none; color: ' + VERDE + '; border: 1px solid ' + VERDE + '59; border-radius: 100px; padding: 3px 8px;">artefato ↗</a>'
        : '<span style="font-size: 10.5px; white-space: nowrap; color: ' + VERDE + '; border: 1px solid ' + VERDE + '59; border-radius: 100px; padding: 3px 8px;">artefato</span>';
    }
    if (p.fo) {
      out += '<span' + ev('e', mostraTip('somente princípio', p.fo, 'marca')) + ev('l', escondeTip()) +
        ' style="font-size: 10.5px; color: #a8a49b; border: 1px solid #a8a49b59; border-radius: 100px; padding: 3px 8px; white-space: nowrap;">princípio</span>';
    }
    return out;
  }

  function secao(numero, titulo) {
    return '<div style="display: flex; align-items: baseline; gap: 14px; margin-bottom: 14px;">' +
      '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 11px; color: ' + ACCENT + ';">' + numero + '</span>' +
      '<span style="font-size: 11px; font-weight: 600; letter-spacing: 0.18em; text-transform: uppercase; color: #a8a49b;">' + titulo + '</span>' +
      '<span style="flex: 1; height: 1px; background: #242a30;"></span>' +
      '</div>';
  }

  function linhaFiltro(rotulo, zIndex, conteudo) {
    return '<div style="display: grid; grid-template-columns: 74px minmax(0, 1fr); gap: 16px; align-items: start; position: relative; z-index: ' + zIndex + ';">' +
      '<div style="font-size: 10px; font-weight: 600; letter-spacing: 0.14em; color: #8b8f96; padding-top: 11px;">' + rotulo + '</div>' +
      '<div style="display: flex; gap: 10px; flex-wrap: wrap;">' + conteudo + '</div>' +
      '</div>';
  }

  /* Rodape comum as tres abas: a procedencia do dado e os modelos que o
     produziram nao mudam de aba para aba. */
  function rodape(esquerda) {
    return '<div style="display: flex; justify-content: space-between; align-items: baseline; gap: 28px; padding-top: 24px; margin-top: 30px; border-top: 1px solid #242a30; font-size: 10.5px; letter-spacing: 0.1em; color: #5f636a;">' +
      '<span>' + esquerda + '</span>' +
      '<span>ESTÁGIO A: ' + esc(DADOS.modeloA) + ' · ESTÁGIO B: ' + esc(DADOS.modeloB) + '</span>' +
      '</div>';
  }

  /* Navegacao entre as tres abas. Sublinhado em vez de pilula: as pilulas ja
     significam "filtro" em todo o resto do painel, e uma aba nao filtra nada -
     ela troca a pergunta que a pagina responde. `aprovados` e a contagem do
     recorte vivo, nao da janela inteira. */
  function navAbas(aprovados) {
    var s = state;
    var itens = [
      { valor: 'aprovados', label: 'Aprovados', nota: aprovados + ' no recorte' },
      { valor: 'panorama', label: 'Panorama', nota: '5 seções' },
      { valor: 'historico', label: 'Registro histórico', nota: (DADOS.hall || []).length + ' trimestres' }
    ];
    return '<div style="display: flex; gap: 30px; margin-top: 26px; border-bottom: 1px solid #242a30;">' +
      itens.map(function (i) {
        var on = s.aba === i.valor;
        return '<div class="aba"' + ev('c', function () { setState({ aba: i.valor, menu: null, aberta: null, abertaH: null, justExp: {} }); }) +
          ' style="display: flex; align-items: baseline; gap: 10px; padding: 0 2px 13px; margin-bottom: -1px; border-bottom: 2px solid ' +
          (on ? ACCENT : 'transparent') + '; color: ' + (on ? '#f5f3ee' : '#8b8f96') + ';">' +
          '<span style="font-size: 13.5px; font-weight: ' + (on ? '600' : '400') + ';">' + i.label + '</span>' +
          '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 11px; color: ' + (on ? '#8b8f96' : '#5f636a') + ';">' + esc(i.nota) + '</span>' +
          '</div>';
      }).join('') +
      '</div>';
  }

  var TOPO_HALL = 15;

  /* ══════════════ ABA HISTÓRICA ══════════════

     A aba viva mostra uma janela de dias; esta guarda o que saiu dela. Ela NAO
     preserva dado contra perda - nada e apagado, a serie inteira continua em
     marts/*.parquet e no banco. O que ela resolve e visibilidade: impedir que o
     recorte esconda para sempre o que a comunidade mais votou.

     Os 15 aprovados mais votados de cada trimestre, com a ficha, e os 5
     descartados mais votados, como auditoria do corte. */
  function construirHall() {
    var s = state;
    var hall = DADOS.hall || [];
    var out = [];

    if (!hall.length) {
      out.push(
        '<div class="card" style="padding: 62px 26px; text-align: center;">' +
          '<div style="font-family: Newsreader, Georgia, serif; font-size: 28px; font-weight: 400; color: #f5f3ee; margin-bottom: 12px;">Nenhum período saiu da janela ainda</div>' +
          '<div style="font-size: 13px; line-height: 1.65; color: #8b8f96; max-width: 580px; margin: 0 auto;">Um paper entra no registro histórico quando completa ' +
            (DADOS.diasRefresh || DADOS.diasHall) + ' dias — a mesma marca em que o pipeline para de reconsultar os votos dele. Até lá ele está na aba <em style="color: #a8a49b;">Aprovados</em>, com o número de votos ainda vivo.</div>' +
        '</div>');
      out.push(rodape('REGISTRO HISTÓRICO · NENHUM PERÍODO FECHADO'));
      return out.join('');
    }

    var atual = null;
    hall.forEach(function (per) { if (per.per === s.perSel) atual = per; });
    if (!atual) atual = hall[0];

    /* ── nota de leitura ────────────────────────────────────────────────── */
    out.push(
      '<div class="card" style="margin: 26px 0 30px; padding: 20px 24px; display: flex; align-items: flex-start; gap: 16px;">' +
        '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="' + ACCENT + '" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" style="flex: none; margin-top: 2px;"><circle cx="12" cy="12" r="9"></circle><path d="M12 8v5"></path><path d="M12 16.5v.01"></path></svg>' +
        '<div style="font-size: 12.5px; line-height: 1.7; color: #a8a49b; max-width: 880px; text-wrap: pretty;">' +
          'As abas <em style="color: #ecebe6; font-style: normal;">Aprovados</em> e <em style="color: #ecebe6; font-style: normal;">Panorama</em> mostram os últimos ' + DADOS.janela + ' dias. Aqui ficam, de cada trimestre já fora dela, os ' + TOPO_HALL + ' aprovados mais votados, com a ficha inteira, e os 5 descartados mais votados, como auditoria do corte. ' +
          '<span style="color: #6d7178;">Nada é apagado em lugar nenhum: a série completa continua no banco e nos Parquet. Os votos aqui estão congelados porque o refresh para de reconsultá-los aos ' + (DADOS.diasRefresh || DADOS.diasHall) + ' dias.</span>' +
        '</div>' +
      '</div>'
    );

    /* ── seletor de trimestre ──────────────────────────────────────────── */
    var chipsPer = hall.map(function (per) {
      var on = per.per === atual.per;
      return '<div class="' + (on ? 'chip chip-on' : 'chip') + '"' +
        ev('c', function () { setState({ perSel: per.per, abertaH: null, justExp: {} }); }) +
        ' style="' + (on ? pillOnGlobal() : pill(false)) + '">' +
        esc(per.rot) +
        '<span style="margin-left: 7px; font-family: \'IBM Plex Mono\', monospace; font-size: 11px; opacity: 0.62;">' + per.n + '</span>' +
        (per.cons ? '<span style="margin-left: 8px; font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; opacity: 0.7;">consolidando</span>' : '') +
        '</div>';
    }).join('');

    out.push(
      '<div style="display: flex; flex-direction: column; gap: 14px; margin-bottom: 30px;">' +
        '<div style="display: flex; align-items: center; gap: 14px; flex-wrap: wrap;">' +
          '<span style="font-size: 10px; font-weight: 600; letter-spacing: 0.14em; color: #8b8f96; width: 74px;">PERÍODO</span>' + chipsPer +
        '</div>' +
      '</div>'
    );

    var avisoCons = atual.cons
      ? '<span style="display: inline-flex; align-items: center; gap: 7px; font-size: 11.5px; color: ' + ACCENT + '; background: rgba(217,164,65,0.1); border: 1px solid rgba(217,164,65,0.35); border-radius: 100px; padding: 6px 13px;">' +
          '<span style="display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: ' + ACCENT + ';"></span>' +
          'em consolidação — o trimestre ainda não saiu inteiro do corte</span>'
      : '<span style="font-size: 11.5px; color: #6d7178;">período fechado · ranking definitivo</span>';

    /* ── 01 · os mais votados entre os aprovados ────────────────────────── */
    out.push(secao('01', 'Os mais votados entre os aprovados'));

    var ap = atual.ap.slice()
      .sort(function (a, b) { return b.u - a.u || a.id.localeCompare(b.id); })
      .slice(0, TOPO_HALL);

    var colunasH = '30px 132px minmax(240px, 1.3fr) minmax(200px, 1fr) 110px 56px 54px';
    var linhasAp = ap.map(function (p, i) {
      var aberta = s.abertaH === p.id;
      var corpo = aberta
        ? corpoAberto(p, p.f ? p : null, 'hall:' + p.id,
            p.uq ? '<span style="font-size: 11.5px; color: #5f636a;">votos medidos em ' + esc(diaCurto(p.uq)) + '</span>' : '')
        : '';
      return '<div style="border-bottom: 1px solid #1d2226;">' +
        '<div class="row" data-card="' + esc(p.id) + '"' + ev('c', function () { setState({ abertaH: aberta ? null : p.id }); }) + ' style="display: grid; grid-template-columns: ' + colunasH + '; gap: 14px; padding: 14px 24px; align-items: center;">' +
          '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 12px; color: ' + (i < 3 ? ACCENT : '#4a5058') + ';">' + (i + 1) + '</span>' +
          '<span>' + seloNatureza(p.nt) + '</span>' +
          '<div style="display: flex; flex-direction: column; gap: 3px; min-width: 0;">' +
            '<span style="font-size: 13.5px; color: #ecebe6; line-height: 1.3; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">' + esc(p.t) + '</span>' +
            '<span style="font-size: 11.5px; color: #6d7178; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">' + esc(p.org || '—') + (p.f ? '' : ' · sem ficha') + '</span>' +
          '</div>' +
          '<span style="font-size: 11.5px; color: #8b8f96; line-height: 1.5;">' + esc(parArea(p)) + '</span>' +
          celulaVertente(p) +
          '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 12.5px; color: #ecebe6; text-align: right;">' + p.u + '</span>' +
          '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 11.5px; color: #6d7178; text-align: right;">' + diaCurto(p.d) + '</span>' +
        '</div>' + corpo +
        '</div>';
    }).join('');

    out.push(
      '<div class="card" style="overflow-x: auto; margin-bottom: 34px;">' +
        '<div style="display: flex; justify-content: space-between; align-items: flex-end; gap: 28px; padding: 22px 24px 18px;">' +
          '<div style="display: flex; flex-direction: column; gap: 5px;">' +
            '<div style="font-family: Newsreader, Georgia, serif; font-size: 26px; font-weight: 400; line-height: 1.1; color: #f5f3ee;">O que ficou do ' + esc(atual.rot) + '</div>' +
            '<div style="font-size: 12.5px; color: #8b8f96;">' + ap.length + ' de ' + atual.na + ' aprovados, ordenados por voto da comunidade. Clique para abrir o porquê da classificação — e a ficha completa.</div>' +
          '</div>' + avisoCons +
        '</div>' +
        '<div style="display: grid; grid-template-columns: ' + colunasH + '; gap: 14px; padding: 11px 24px; border-top: 1px solid #242a30; border-bottom: 1px solid #242a30; background: #131619; font-size: 10.5px; font-weight: 600; letter-spacing: 0.14em; color: #8b8f96;">' +
          '<span>#</span><span>NATUREZA</span><span>TÍTULO</span><span>ÁREA &gt; SUB-ÁREA</span><span>VERTENTE</span><span style="text-align: right;">VOTOS</span><span style="text-align: right;">DIA</span>' +
        '</div>' +
        linhasAp +
        (linhasAp ? '' : '<div style="padding: 54px 24px; text-align: center; font-size: 13px; color: #6d7178;">Nenhum aprovado neste trimestre.</div>') +
      '</div>'
    );

    /* ── 02 · auditoria: votados e descartados ──────────────────────────── */
    out.push(secao('02', 'Auditoria: votados pela comunidade, descartados pelo pipeline'));

    var linhasDe = atual.de.map(function (p, i) {
      return '<div style="display: grid; grid-template-columns: 30px 66px minmax(0, 1fr); gap: 16px; padding: 15px 24px; border-bottom: 1px solid #1d2226; align-items: start;">' +
        '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 12px; color: #4a5058; padding-top: 2px;">' + (i + 1) + '</span>' +
        '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 13px; color: #9aa1a9; text-align: right; padding-top: 1px;">' + p.u + '</span>' +
        '<div style="display: flex; flex-direction: column; gap: 6px; min-width: 0;">' +
          '<div style="display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap;">' +
            '<a href="' + esc(p.url) + '" target="_blank" rel="noopener" style="font-size: 13.5px; color: #ecebe6; border-bottom-color: rgba(236,235,230,0.18);">' + esc(p.t) + '</a>' +
            (p.rf
              ? '<span style="font-size: 10.5px; color: #8b8f96; background: #1d2226; border: 1px solid #2b3138; border-radius: 100px; padding: 3px 9px;">' + esc(rotulo(p.rf)) + '</span>'
              : '') +
            '<span style="font-size: 11.5px; color: #6d7178;">' + esc(p.org || '—') + ' · ' + diaCurto(p.d) + '</span>' +
          '</div>' +
          (function () {
            var aviso = avisoDecisao(p.h);
            return aviso
              ? '<div style="font-size: 12.5px; font-style: italic; color: #6d7178;">' + aviso + '</div>'
              : '<div style="font-family: Newsreader, Georgia, serif; font-size: 15px; font-weight: 300; line-height: 1.6; color: #a8a49b; text-wrap: pretty;">' + esc(p.j) + '</div>';
          })() +
        '</div>' +
        '</div>';
    }).join('');

    out.push(
      '<div class="card" style="overflow-x: auto; margin-bottom: 34px;">' +
        '<div style="display: flex; justify-content: space-between; align-items: flex-end; gap: 28px; padding: 22px 24px 18px;">' +
          '<div style="display: flex; flex-direction: column; gap: 5px;">' +
            '<div style="font-family: Newsreader, Georgia, serif; font-size: 26px; font-weight: 400; line-height: 1.1; color: #f5f3ee;">O outro lado do voto</div>' +
            '<div style="font-size: 12.5px; color: #8b8f96;">Os ' + atual.de.length + ' mais votados entre os ' + atual.nd + ' descartados do trimestre, com a regra e a justificativa que os tiraram.' +
              (atual.nx ? ' <span style="color: #6d7178;">Outros ' + atual.nx + ' do trimestre nunca chegaram a ser classificados e ficam fora das duas listas.</span>' : '') +
            '</div>' +
          '</div>' +
          '<span style="font-size: 11.5px; color: #6d7178; text-align: right; max-width: 300px; line-height: 1.5;">Upvote não entra em decisão nenhuma do pipeline. Esta lista existe para medir a divergência, não para reabrir o descarte.</span>' +
        '</div>' +
        linhasDe +
        (linhasDe ? '' : '<div style="padding: 54px 24px; text-align: center; font-size: 13px; color: #6d7178;">Nenhum descarte neste trimestre.</div>') +
      '</div>'
    );

    var somaDe = 0;
    hall.forEach(function (per) { somaDe += per.de.length; });
    out.push(rodape('REGISTRO HISTÓRICO · ' + hall.length + ' TRIMESTRE(S) · ' + TOPO_HALL + ' APROVADOS · ' + somaDe + ' DESCARTADOS'));
    return out.join('');
  }

  // a pilula "ligada" tambem e usada fora de construir()
  function pillOnGlobal() {
    return 'display: inline-flex; align-items: center; gap: 0; font-size: 12.5px; line-height: 1; padding: 8px 15px; border-radius: 100px; white-space: nowrap; background: ' + ACCENT + '; border: 1px solid ' + ACCENT + '; color: #14161a; font-weight: 600;';
  }

  /* Pilula com bolinha de cor e contador - o mesmo desenho para natureza,
     marca e veredito, que e o que os testes procuram. */
  var COM_CONTAGEM = 'margin-left: 7px; font-family: \'IBM Plex Mono\', monospace; font-size: 11px; opacity: 0.62;';
  function pilula(rotuloP, on, corP, n, fn, dica, extra) {
    return '<div class="' + (on ? 'chip chip-on' : 'chip') + '"' + ev('c', fn) +
      (dica ? ev('e', dica) + ev('l', escondeTip()) : '') +
      ' style="' + pill(on, corP) + (extra || '') + '">' +
      '<span style="display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 8px; background: ' + corP + ';"></span>' + esc(rotuloP) +
      (n === null || n === undefined ? '' : '<span style="' + COM_CONTAGEM + '">' + n + '</span>') +
      '</div>';
  }

  function construir() {
    var s = state;
    var todos = DADOS.papers;
    var sel = filtrados();
    var total = sel.length;

    /* Um recorte por dimensao, cada um com a SUA solta: e o que faz os
       numeros da barra de filtro descreverem o recorte em vigor em vez da
       janela inteira, sem que o seletor se apague depois do primeiro clique. */
    var recDia = filtrados('diasSel');
    var recVeredito = filtrados('vereditos');
    var recArea = filtrados('areas');
    var recSubarea = filtrados('subareas');
    var recVert = filtrados('vertentes');
    var recOrg = filtrados('orgs');
    var recNatureza = filtrados('naturezas');
    var recMarca = filtrados('marcas');

    var aprovadosSel = sel.filter(function (p) { return p.v === 'aprovado'; });
    var nFora = total - aprovadosSel.length;

    // Aprovado nao classificado (linha anterior a reclassificacao total) na
    // janela inteira: e o que decide se a pilula e a nota de transicao existem.
    var naoClassificados = todos.filter(function (p) { return p.v === 'aprovado' && natureza(p) === NAO_CLASSIFICADO; }).length;
    var naturezasVisiveis = NATUREZAS.concat(naoClassificados ? [NAO_CLASSIFICADO] : []);

    var dias = [];
    todos.forEach(function (p) { if (p.d && dias.indexOf(p.d) < 0) dias.push(p.d); });
    dias.sort();

    var out = [];
    out.push('<div style="background: #0d0f11; color: #ecebe6; padding: 44px 46px 60px;">');

    /* ══════════════ CABEÇALHO ══════════════ */
    out.push(
      '<div style="display: flex; justify-content: space-between; align-items: flex-end; gap: 40px; padding-bottom: 26px; border-bottom: 1px solid #242a30;">' +
        '<div style="display: flex; flex-direction: column; gap: 12px;">' +
          '<div style="display: flex; align-items: center; gap: 9px;">' +
            '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="' + ACCENT + '" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"></circle><path d="M12 3a14 14 0 0 0 0 18"></path><path d="M12 3a14 14 0 0 1 0 18"></path><path d="M3.5 9h17"></path><path d="M3.5 15h17"></path></svg>' +
            '<span style="font-size: 11px; font-weight: 500; letter-spacing: 0.2em; text-transform: uppercase; color: ' + ACCENT + ';">hf-papers-db</span>' +
          '</div>' +
          '<div style="font-family: Newsreader, Georgia, serif; font-size: 66px; font-weight: 300; line-height: 0.96; letter-spacing: -0.02em; color: #f5f3ee;">Daily Papers,<span style="font-style: italic; font-weight: 400; color: ' + ACCENT + ';"> triados</span></div>' +
          '<div style="font-family: Newsreader, Georgia, serif; font-size: 17px; font-weight: 300; line-height: 1.55; color: #a8a49b; max-width: 680px; text-wrap: pretty;">Papers do Hugging Face Daily Papers, classificados pelo que afirmam e pelo tema, e resumidos em fichas.</div>' +
        '</div>' +
        '<div style="display: flex; gap: 34px; text-align: right; padding-bottom: 4px;">' +
          '<div style="display: flex; flex-direction: column; gap: 5px;">' +
            '<span style="font-size: 10px; letter-spacing: 0.16em; color: #6d7178;">JANELA</span>' +
            '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 14px; color: #ecebe6;">' +
              esc(dias.length ? diaCurto(dias[0]) + ' – ' + diaCurto(dias[dias.length - 1]) : '—') +
              '<span style="color: #6d7178;"> · ' + DADOS.janela + 'd</span>' +
            '</span>' +
          '</div>' +
          '<div style="display: flex; flex-direction: column; gap: 5px;">' +
            '<span style="font-size: 10px; letter-spacing: 0.16em; color: #6d7178;">PAPERS</span>' +
            '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 14px; color: #ecebe6;">' + todos.length +
              (DADOS.pendentes ? '<span style="color: #6d7178;"> · +' + DADOS.pendentes + ' na fila</span>' : '') +
            '</span>' +
          '</div>' +
          '<div style="display: flex; flex-direction: column; gap: 5px;">' +
            '<span style="font-size: 10px; letter-spacing: 0.16em; color: #6d7178;">EXTRAÍDO</span>' +
            '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 14px; color: #ecebe6;">' + esc(DADOS.gerado.replace('T', ' ').slice(0, 16)) + '</span>' +
          '</div>' +
        '</div>' +
      '</div>'
    );

    out.push(navAbas(aprovadosSel.length));

    /* A aba historica nao passa pela barra de filtro: `filtrados()` recorta
       DADOS.papers, que e so a janela. O hall tem o seletor de trimestre, e
       nada mais. */
    if (s.aba === 'historico') {
      out.push(construirHall());
      out.push('</div>');
      return out.join('');
    }

    /* ══════════════ NOTA DE TRANSIÇÃO ══════════════ */
    out.push(
      '<div class="card" style="margin: 24px 0 0; padding: 16px 22px; display: flex; align-items: flex-start; gap: 14px;">' +
        '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="' + ACCENT + '" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" style="flex: none; margin-top: 2px;"><circle cx="12" cy="12" r="9"></circle><path d="M12 8v5"></path><path d="M12 16.5v.01"></path></svg>' +
        '<div style="font-size: 12.5px; line-height: 1.65; color: #a8a49b; text-wrap: pretty;">' +
          'Desde 20/10/2026 o painel não separa mais <em style="font-style: normal; color: #ecebe6;">estrito</em> e <em style="font-style: normal; color: #ecebe6;">amplo</em>. Cada aprovado diz que tipo de afirmação faz (<em style="font-style: normal; color: #ecebe6;">natureza</em>) e se localiza por área, sub-área e vertente. ' +
          'Papers de treino e de pesquisa deixaram de ser descartados.' +
          (naoClassificados
            ? ' <span style="color: #6d7178;">' + naoClassificados + ' aprovados da janela ainda são do regime anterior e aparecem como <em>não classificado</em> até a reclassificação total.</span>'
            : '') +
        '</div>' +
      '</div>'
    );

    /* ══════════════ FILTROS ══════════════ */
    var contaDia = {};
    recDia.forEach(function (p) { if (p.d) contaDia[p.d] = (contaDia[p.d] || 0) + 1; });
    var itensDia = dias.slice().reverse().map(function (d) {
      return { valor: d, label: diaCurto(d), n: contaDia[d] || 0 };
    });

    var contaArea = {};
    recArea.forEach(function (p) { if (p.a) contaArea[p.a] = (contaArea[p.a] || 0) + 1; });
    var itensArea = DADOS.areas.map(function (a) {
      return { valor: a.a, label: a.a, n: contaArea[a.a] || 0 };
    }).sort(function (x, y) { return y.n - x.n || x.label.localeCompare(y.label); });

    var contaSubarea = {};
    recSubarea.forEach(function (p) { if (p.sa) contaSubarea[p.sa] = (contaSubarea[p.sa] || 0) + 1; });
    var itensSubarea = Object.keys(DADOS.subdef || {}).map(function (sa) {
      return { valor: sa, label: sa, n: contaSubarea[sa] || 0 };
    }).sort(function (x, y) { return y.n - x.n || x.label.localeCompare(y.label); });

    var contaVert = {};
    recVert.forEach(function (p) { var k = dominante(p); contaVert[k] = (contaVert[k] || 0) + 1; });
    var itensVert = (DADOS.vertentes || []).map(function (v) {
      return { valor: v.v, label: v.v, n: contaVert[v.v] || 0 };
    }).sort(function (x, y) { return y.n - x.n || x.label.localeCompare(y.label); });
    if (contaVert[VERTENTE_NULA] || s.vertentes.indexOf(VERTENTE_NULA) >= 0) {
      itensVert.push({ valor: VERTENTE_NULA, label: 'sem vertente', n: contaVert[VERTENTE_NULA] || 0 });
    }

    /* Organizacao e a excecao a regra dos zeros: nao e vocabulario controlado,
       e uma lista de zeros nao informa nada que a busca do menu ja nao resolva.
       Menos a que estiver MARCADA: o filtro em vigor nunca sai do menu. */
    var contaOrg = {};
    recOrg.forEach(function (p) { if (p.org) contaOrg[p.org] = (contaOrg[p.org] || 0) + 1; });
    s.orgs.forEach(function (o) { if (o !== '__sem-org__' && !contaOrg[o]) contaOrg[o] = 0; });
    var semOrg = recOrg.filter(function (p) { return !p.org; }).length;
    var itensOrg = Object.keys(contaOrg).map(function (o) {
      return { valor: o, label: o, n: contaOrg[o] };
    }).sort(function (x, y) { return y.n - x.n || x.label.localeCompare(y.label); });
    if (semOrg || s.orgs.indexOf('__sem-org__') >= 0) {
      itensOrg.push({ valor: '__sem-org__', label: 'sem organização', n: semOrg });
    }

    var contaNat = {};
    recNatureza.forEach(function (p) { if (p.v === 'aprovado') { var k = natureza(p); contaNat[k] = (contaNat[k] || 0) + 1; } });
    var chipsNatureza = naturezasVisiveis.map(function (k) {
      var r = rotuloNatureza(k);
      return pilula(r, s.naturezas.indexOf(k) >= 0, corNatureza(k), contaNat[k] || 0,
        function () { alternaLista('naturezas', k); },
        mostraTip(r, k === NAO_CLASSIFICADO ? DEF_NAO_CLASSIFICADO : (DEF_NATUREZA[k] || ''), 'natureza'));
    }).join('') + '<span style="font-size: 11.5px; color: #6d7178; align-self: center;">recorta só os aprovados</span>';

    var chipsMarca = MARCAS.map(function (m) {
      var n = recMarca.filter(function (p) { return p.v === 'aprovado' && temMarca(p, m.k); }).length;
      return pilula(m.r, s.marcas.indexOf(m.k) >= 0, VERDE, n, function () { alternaLista('marcas', m.k); },
        mostraTip(m.r, m.def, 'marca'));
    }).join('');

    // Veredito so na aba Panorama: a aba Aprovados ja e so aprovado
    var chipsVeredito = [{ k: 'aprovado', c: VERDE }, { k: 'fora', c: COR_FORA }].map(function (v) {
      var n = recVeredito.filter(function (p) { return p.v === v.k; }).length;
      return pilula(v.k, s.vereditos.indexOf(v.k) >= 0, v.c, n, function () { alternaLista('vereditos', v.k); });
    }).join('');

    var ativos = [];
    if (s.diasSel.length) ativos.push(s.diasSel.length === 1 ? diaCurto(s.diasSel[0]) : s.diasSel.length + ' dias');
    if (s.naturezas.length) ativos.push(s.naturezas.map(rotuloNatureza).join('+'));
    if (s.marcas.length) ativos.push(s.marcas.map(function (k) { return MARCAS.filter(function (m) { return m.k === k; })[0].r; }).join(' e '));
    if (s.aba === 'panorama' && s.vereditos.length) ativos.push(s.vereditos.join('+'));
    if (s.areas.length) ativos.push(s.areas.length === 1 ? s.areas[0] : s.areas.length + ' áreas');
    if (s.subareas.length) ativos.push(s.subareas.length === 1 ? s.subareas[0] : s.subareas.length + ' sub-áreas');
    if (s.vertentes.length) ativos.push(s.vertentes.length === 1
      ? (s.vertentes[0] === VERTENTE_NULA ? 'sem vertente' : 'dominante: ' + s.vertentes[0])
      : s.vertentes.length + ' vertentes dominantes');
    if (s.regrasFora.length) ativos.push(s.regrasFora.length === 1 ? 'regra: ' + rotulo(s.regrasFora[0]) : s.regrasFora.length + ' regras');
    if (s.orgs.length) ativos.push(s.orgs.length === 1 ? (s.orgs[0] === '__sem-org__' ? 'sem organização' : s.orgs[0]) : s.orgs.length + ' organizações');
    if (s.buscaQ) ativos.push('"' + s.buscaQ + '"');
    var resumoFiltro = ativos.length ? total + ' de ' + todos.length + ' · ' + ativos.join(' · ') : todos.length + ' papers, sem recorte';

    var estiloLimpar = 'display: inline-flex; align-items: center; gap: 7px; font-size: 12px; padding: 8px 14px; border-radius: 100px; background: ' +
      (ativos.length ? 'rgba(217,164,65,0.12)' : '#1b1f23') + '; border: 1px solid ' + (ativos.length ? 'rgba(217,164,65,0.5)' : '#2b3138') +
      '; color: ' + (ativos.length ? ACCENT : '#6d7178') + ';';

    var zDia = s.menu === 'diasSel' ? 90 : 4;
    var zTema = (s.menu === 'areas' || s.menu === 'subareas' || s.menu === 'vertentes') ? 90 : 2;
    var zOrg = s.menu === 'orgs' ? 90 : 1;

    out.push(
      '<div class="card" style="margin: 14px 0 30px; padding: 20px 22px 22px; display: flex; flex-direction: column; gap: 15px;">' +
        '<div style="display: flex; align-items: center; justify-content: space-between; gap: 20px; flex-wrap: wrap;">' +
          '<div style="display: flex; align-items: center; gap: 10px;">' +
            '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#767a80" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5h16l-6.5 7.5V19l-3 1.5v-8L4 5z"></path></svg>' +
            '<span style="font-size: 11px; font-weight: 600; letter-spacing: 0.16em; text-transform: uppercase; color: #a8a49b;">Recorte</span>' +
            '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 12px; color: #6d7178;">' + esc(resumoFiltro) + '</span>' +
          '</div>' +
          '<div style="display: flex; align-items: center; gap: 14px;">' +
            '<div style="position: relative; display: flex; align-items: center;">' +
              '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#6d7178" stroke-width="1.7" stroke-linecap="round" style="position: absolute; left: 13px;"><circle cx="11" cy="11" r="6.5"></circle><path d="M16 16l4.5 4.5"></path></svg>' +
              '<input id="q-principal" class="busca" type="text" value="' + esc(s.busca) + '"' +
                ev('i', function (e) { digitaBusca(e.target.value); }) +
                ' placeholder="buscar título, organização ou ficha" style="font-family: \'Instrument Sans\', sans-serif; font-size: 13px; padding: 9px 14px 9px 36px; width: 300px; border: 1px solid #2b3138; border-radius: 100px; background: #1b1f23; color: #ecebe6; outline: none;">' +
            '</div>' +
            '<div class="chip"' + ev('c', function () {
                state.busca = '';
                setState({ diasSel: [], vereditos: [], areas: [], subareas: [], vertentes: [], regrasFora: [], orgs: [], naturezas: [], marcas: [], buscaQ: '', aberta: null, menu: null, buscaMenu: '', justExp: {}, diaPag: null });
              }) + ' style="' + estiloLimpar + '">' +
              '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"></path></svg><span>limpar</span>' +
            '</div>' +
          '</div>' +
        '</div>' +
        '<div style="height: 1px; background: #242a30;"></div>' +
        linhaFiltro('NATUREZA', 5, chipsNatureza) +
        linhaFiltro('MARCAS', 5, chipsMarca) +
        (s.aba === 'panorama'
          ? linhaFiltro('VEREDITO', 4, chipsVeredito +
              (DADOS.pendentes
                ? '<span' + ev('e', mostraTip('Ainda sem veredito',
                    'O refresh grava paper novo depois que a classificação já passou; ele entra na próxima rodada. Nunca classificado não é o mesmo que fora.')) +
                    ev('l', escondeTip()) +
                    ' style="font-size: 11.5px; color: #6d7178; border-bottom: 1px dotted #3a4048; cursor: help; align-self: center;">+' +
                    DADOS.pendentes + ' na fila, sem veredito</span>'
                : ''))
          : '') +
        linhaFiltro('DIA', zDia, montaMenu('DIA', 'diasSel', itensDia, { todos: 'todos os dias' })) +
        linhaFiltro('TEMA', zTema,
          montaMenu('ÁREA', 'areas', itensArea, { todos: 'todas' }) +
          montaMenu('SUB-ÁREA', 'subareas', itensSubarea, { todos: 'todas' }) +
          montaMenu('VERTENTE', 'vertentes', itensVert, { todos: 'todas' })) +
        linhaFiltro('AUTORIA', zOrg, montaMenu('ORGANIZAÇÃO', 'orgs', itensOrg, { todos: 'todas' })) +
      '</div>'
    );

    if (s.menu) {
      out.push('<div' + ev('c', function () { setState({ menu: null, buscaMenu: '' }); }) + ' style="position: fixed; inset: 0; z-index: 80;"></div>');
    }

    /* As duas abas filtraveis dividem tudo acima desta linha. O que vem
       abaixo e exclusivo de cada uma. */
    if (s.aba === 'panorama') {

    /* ══════════════ STAT TILES ══════════════ */
    var comFicha = aprovadosSel.filter(function (p) { return p.f; }).length;
    var comArtefato = aprovadosSel.filter(function (p) { return p.ao; }).length;
    var contradizem = aprovadosSel.filter(function (p) { return p.pc; }).length;
    function marca(c) { return 'display: inline-block; width: 5px; height: 5px; border-radius: 50%; background: ' + c + ';'; }
    var tiles = [
      { rotulo: 'papers no recorte', valor: total, sufixo: 'de ' + todos.length, cor: '#f5f3ee', marca: marca('#4a5058'), nota: dias.length + ' dias de publicação cobertos' },
      { rotulo: 'aprovados', valor: aprovadosSel.length, sufixo: pct(aprovadosSel.length, total) + '%', cor: VERDE, marca: marca(VERDE), nota: comFicha + ' com ficha escrita · ' + nFora + ' descartados' },
      { rotulo: 'artefato aberto', valor: comArtefato, sufixo: pct(comArtefato, aprovadosSel.length) + '% dos aprovados', cor: '#f5f3ee', marca: marca(VERDE), nota: 'evidência no HF ou no abstract, confirmada como liberada' },
      { rotulo: 'contradizem prática', valor: contradizem, sufixo: pct(contradizem, aprovadosSel.length) + '% dos aprovados', cor: '#f5f3ee', marca: marca('#e8a37c'), nota: 'achados contra algo que o leitor faz hoje, nomeado na ficha' }
    ];
    out.push('<div style="display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin-bottom: 34px;">' +
      tiles.map(function (k) {
        return '<div class="card" style="padding: 18px 20px 17px; display: flex; flex-direction: column; gap: 9px;">' +
          '<div style="display: flex; align-items: center; gap: 7px;">' +
            '<span style="' + k.marca + '"></span>' +
            '<span style="font-size: 10px; font-weight: 600; letter-spacing: 0.14em; text-transform: uppercase; color: #767a80;">' + esc(k.rotulo) + '</span>' +
          '</div>' +
          '<div style="display: flex; align-items: baseline; gap: 9px;">' +
            '<span style="font-family: Newsreader, Georgia, serif; font-weight: 400; font-size: 46px; line-height: 0.9; letter-spacing: -0.02em; color: ' + k.cor + ';">' + k.valor + '</span>' +
            '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 12px; color: #6d7178;">' + esc(k.sufixo) + '</span>' +
          '</div>' +
          '<div style="font-size: 12px; line-height: 1.42; color: #8b8f96; text-wrap: pretty;">' + esc(k.nota) + '</div>' +
          '</div>';
      }).join('') + '</div>');

    /* ══════════════ 01 · VOLUME E SELETIVIDADE ══════════════ */
    out.push(secao('01', 'Volume e seletividade'));

    /* Empilhado de baixo para cima: descartados, depois as naturezas na
       ordem do banco, o nao classificado no topo. */
    var camadas = ['fora'].concat(naturezasVisiveis);
    function corCamada(k) { return k === 'fora' ? COR_FORA : corNatureza(k); }
    function rotuloCamada(k) { return k === 'fora' ? 'fora' : rotuloNatureza(k); }
    function camadaDe(p) { return p.v === 'fora' ? 'fora' : natureza(p); }

    var nCol = Math.max(1, dias.length);
    var porDia = {};
    dias.forEach(function (d) { porDia[d] = { total: 0, ap: 0 }; camadas.forEach(function (k) { porDia[d][k] = 0; }); });
    sel.forEach(function (p) {
      var c = porDia[p.d];
      if (!c) return;
      c[camadaDe(p)] = (c[camadaDe(p)] || 0) + 1;
      c.total++;
      if (p.v === 'aprovado') c.ap++;
    });
    var maxDia = Math.max.apply(null, dias.map(function (d) { return porDia[d].total; }).concat([1]));

    var legenda = camadas.map(function (k) {
      return '<div style="display: flex; align-items: center; gap: 6px; font-size: 11.5px; color: #a8a49b; white-space: nowrap;">' +
        '<span style="display: inline-block; width: 8px; height: 8px; border-radius: 2px; background: ' + corCamada(k) + ';"></span>' + esc(rotuloCamada(k)) + '</div>';
    }).join('');

    function detalheDia(c) {
      return camadas.filter(function (k) { return c[k]; }).map(function (k) { return c[k] + ' ' + rotuloCamada(k); }).join(' · ');
    }

    var barrasDia = dias.map(function (d) {
      var c = porDia[d];
      var segs = camadas.filter(function (k) { return c[k] > 0; }).map(function (k) {
        return '<div style="flex: ' + c[k] + '; background: ' + corCamada(k) + '; min-height: 3px; border-radius: 1px;"></div>';
      }).join('');
      return '<div style="flex: 1; display: flex; flex-direction: column; align-items: center; gap: 8px; height: 100%; justify-content: flex-end;">' +
        '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 12px; color: #a8a49b;">' + c.total + '</span>' +
        '<div class="bar"' +
          ev('e', mostraTip(diaCurto(d) + ' · ' + c.total + ' papers', detalheDia(c))) +
          ev('l', escondeTip()) +
          ' style="width: 74%; height: ' + ((c.total / maxDia) * 100) + '%; display: flex; flex-direction: column-reverse; gap: 2px; min-height: 4px;">' + segs + '</div>' +
        '</div>';
    }).join('');
    var rotulosDia = dias.map(function (d) {
      return '<span style="flex: 1; text-align: center; font-family: \'IBM Plex Mono\', monospace; font-size: 11px; color: #6d7178;">' + diaCurto(d) + '</span>';
    }).join('');

    /* ── taxa de aprovação ao longo do tempo ────────────────────────────── */
    var idxDia = {};
    dias.forEach(function (d, i) { idxDia[d] = i; });
    var serieTaxa = dias.filter(function (d) { return porDia[d].total > 0; }).map(function (d) {
      var c = porDia[d];
      return { d: d, c: c, ap: c.ap, tot: c.total, x: ((idxDia[d] + 0.5) / nCol) * 100 };
    });
    serieTaxa.forEach(function (r, i) {
      r.taxa = r.ap / r.tot;
      var ini = Math.max(0, i - 4);
      var sa = 0, st = 0;
      for (var k = ini; k <= i; k++) { sa += serieTaxa[k].ap; st += serieTaxa[k].tot; }
      /* Media movel sobre a razao agregada dos cinco dias, nao sobre a media
         das cinco taxas: um dia de 3 papers nao pode pesar igual a um de 40. */
      r.mm = st ? sa / st : 0;
    });
    var mostraMM = serieTaxa.length >= 8;
    var raioPonto = mostraMM ? 5 : 7;

    function ptsTaxa(campo) {
      return serieTaxa.map(function (r) { return [r.x, 100 - r[campo] * 100]; });
    }
    var desenhoTaxa = [0, 25, 50, 75, 100].map(function (g) {
      return '<line x1="0" y1="' + g + '" x2="100" y2="' + g + '" stroke="' + (g === 50 ? '#242a30' : '#1d2226') + '" stroke-width="1" vector-effect="non-scaling-stroke"></line>';
    }).join('');
    if (mostraMM) desenhoTaxa += poliLinha(ptsTaxa('mm'), '#6d7178', 1.4, '5 4');
    desenhoTaxa += poliLinha(ptsTaxa('taxa'), VERDE, 2, null);

    var celulasTaxa = dias.map(function (d) {
      var c = porDia[d];
      var r = null;
      serieTaxa.forEach(function (x) { if (x.d === d) r = x; });
      var ponto = r
        ? '<span style="position: absolute; left: 50%; bottom: ' + (r.taxa * 100) + '%; width: ' + raioPonto + 'px; height: ' + raioPonto + 'px; margin-left: -' + (raioPonto / 2) + 'px; margin-bottom: -' + (raioPonto / 2) + 'px; border-radius: 50%; background: ' + VERDE + '; border: 1px solid #0d0f11;"></span>'
        : '';
      return '<div' +
        ev('e', mostraTip(diaCurto(d) + ' · ' + (r ? pct(r.ap, r.tot) + '% aprovado' : 'sem dado'), r ? c.total + ' papers · ' + detalheDia(c) : 'nenhum paper neste recorte')) +
        ev('l', escondeTip()) +
        ' style="flex: 1; position: relative; height: 100%; cursor: pointer;">' + ponto + '</div>';
    }).join('');

    var eixoTaxaY = [100, 50, 0].map(function (g) {
      return '<span style="position: absolute; top: ' + (100 - g) + '%; right: 0; transform: translateY(-50%); font-family: \'IBM Plex Mono\', monospace; font-size: 10.5px; color: #6d7178;">' + g + '%</span>';
    }).join('');

    var legendaTaxa = [
      { rot: '% aprovado', c: VERDE, tracos: false },
      { rot: 'média móvel 5d', c: '#6d7178', tracos: true }
    ].filter(function (l) { return mostraMM || l.c === VERDE; }).map(function (l) {
      return '<div style="display: flex; align-items: center; gap: 6px; font-size: 11.5px; color: #a8a49b; white-space: nowrap;">' +
        '<span style="display: inline-block; width: 14px; height: 0; border-top: 2px ' + (l.tracos ? 'dashed' : 'solid') + ' ' + l.c + ';"></span>' + l.rot + '</div>';
    }).join('');

    var gutter = 'display: grid; grid-template-columns: 36px minmax(0, 1fr); gap: 10px; align-items: end;';

    out.push(
      '<div class="card" style="padding: 22px 24px 20px; margin-bottom: 34px; display: flex; flex-direction: column; gap: 18px;">' +
        '<div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 18px; flex-wrap: wrap;">' +
          '<div style="display: flex; flex-direction: column; gap: 5px;">' +
            '<div style="font-family: Newsreader, Georgia, serif; font-size: 26px; font-weight: 400; line-height: 1.1; color: #f5f3ee;">O lote diário e o que sobrou dele</div>' +
            '<div style="font-size: 12.5px; color: #8b8f96;">Papers por dia de publicação no HF: descartados embaixo, aprovados empilhados por natureza.</div>' +
          '</div>' +
          '<div style="display: flex; gap: 15px; padding-top: 5px; flex-wrap: wrap;">' + legenda + '</div>' +
        '</div>' +
        '<div style="' + gutter + '"><div></div>' +
          '<div style="display: flex; align-items: flex-end; gap: 0; height: 200px; border-bottom: 1px solid #333a41;">' + barrasDia + '</div>' +
        '</div>' +
        '<div style="display: flex; justify-content: space-between; align-items: flex-end; gap: 18px; padding-top: 4px; border-top: 1px solid #242a30;">' +
          '<div style="display: flex; flex-direction: column; gap: 4px; padding-top: 14px;">' +
            '<div style="font-size: 13.5px; color: #ecebe6;">Taxa de aprovação ao longo do tempo</div>' +
            '<div style="font-size: 12px; color: #8b8f96;">aprovados ÷ total do dia, no recorte. Mede seletividade do pipeline — não qualidade nem acurácia.</div>' +
          '</div>' +
          '<div style="display: flex; gap: 13px;">' + legendaTaxa + '</div>' +
        '</div>' +
        '<div style="' + gutter + '">' +
          '<div style="position: relative; height: 104px;">' + eixoTaxaY + '</div>' +
          '<div style="position: relative; height: 104px; border-bottom: 1px solid #333a41;">' +
            svgPlano(desenhoTaxa) +
            '<div style="position: absolute; inset: 0; display: flex; gap: 0;">' + celulasTaxa + '</div>' +
          '</div>' +
        '</div>' +
        '<div style="' + gutter + '"><div></div><div style="display: flex; gap: 0;">' + rotulosDia + '</div></div>' +
        (serieTaxa.length ? '' : '<div style="font-size: 12.5px; color: #6d7178; text-align: center; padding: 6px 0;">Nenhum dia com paper dentro deste recorte.</div>') +
      '</div>'
    );

    /* ══════════════ 02 · NATUREZA × VERTENTE ══════════════ */
    out.push(secao('02', 'Natureza × vertente'));

    /* A matriz solta as duas dimensoes dela: e o seletor das duas, e marcar
       uma celula nao pode apagar as outras. Clique alterna o par (natureza,
       vertente dominante) - marca ou desmarca os dois. Colunas por volume,
       a maior primeiro; a celula ganha a cor da natureza da linha. */
    var selMatriz = filtrados(['naturezas', 'vertentes']).filter(function (p) { return p.v === 'aprovado'; });
    var linhasN = NATUREZAS.slice();
    if (selMatriz.some(function (p) { return !p.nt; })) linhasN.push(NAO_CLASSIFICADO);
    var celula = {}, maxCel = 1, somaLinha = {}, somaCol = {};
    selMatriz.forEach(function (p) {
      var n = natureza(p), d = dominante(p);
      var k = n + '|' + d;
      celula[k] = (celula[k] || 0) + 1;
      if (celula[k] > maxCel) maxCel = celula[k];
      somaLinha[n] = (somaLinha[n] || 0) + 1;
      somaCol[d] = (somaCol[d] || 0) + 1;
    });
    var colunasV = Object.keys(somaCol).sort(function (x, y) {
      return (x === VERTENTE_NULA) - (y === VERTENTE_NULA) || somaCol[y] - somaCol[x] || x.localeCompare(y);
    });
    function rotuloVert(v) { return v === VERTENTE_NULA ? 'sem vertente' : v; }
    var gradeMatriz = '160px repeat(' + Math.max(1, colunasV.length) + ', minmax(0, 1fr)) 64px';
    var cabMatriz = '<div style="display: grid; grid-template-columns: ' + gradeMatriz + '; gap: 4px; align-items: end;">' +
      '<span></span>' +
      colunasV.map(function (d) {
        return '<span style="font-size: 11px; text-align: center; color: #a8a49b; padding-bottom: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">' + esc(rotuloVert(d)) + '</span>';
      }).join('') +
      '<span style="font-size: 10.5px; text-align: right; color: #6d7178; padding-bottom: 4px;">total</span>' +
      '</div>';
    var corpoMatriz = linhasN.map(function (n) {
      var rotN = rotuloNatureza(n);
      var corN = corNatureza(n);
      return '<div style="display: grid; grid-template-columns: ' + gradeMatriz + '; gap: 4px; align-items: stretch;">' +
        '<span' + ev('e', mostraTip(rotN, n === NAO_CLASSIFICADO ? DEF_NAO_CLASSIFICADO : (DEF_NATUREZA[n] || ''), (somaLinha[n] || 0) + ' aprovados')) + ev('l', escondeTip()) +
          ' style="font-size: 12.5px; color: #ecebe6; align-self: center;">' + esc(rotN) + '</span>' +
        colunasV.map(function (d) {
          var v = celula[n + '|' + d] || 0;
          var on = s.naturezas.indexOf(n) >= 0 && s.vertentes.indexOf(d) >= 0;
          var alfa = v ? Math.round(18 + (v / maxCel) * 200).toString(16) : '00';
          if (alfa.length < 2) alfa = '0' + alfa;
          return '<div class="seg"' +
            ev('c', function () {
              var ns = state.naturezas.slice(), vs = state.vertentes.slice();
              if (on) {
                ns.splice(ns.indexOf(n), 1); vs.splice(vs.indexOf(d), 1);
              } else {
                if (ns.indexOf(n) < 0) ns.push(n);
                if (vs.indexOf(d) < 0) vs.push(d);
              }
              setState({ naturezas: ns, vertentes: vs, aberta: null, justExp: {}, diaPag: null });
            }) +
            ev('e', mostraTip(rotN + ' · ' + rotuloVert(d), v + (v === 1 ? ' aprovado' : ' aprovados') + ' · clique para filtrar')) + ev('l', escondeTip()) +
            ' style="cursor: pointer; height: 38px; display: flex; align-items: center; justify-content: center; border-radius: 3px; font-family: \'IBM Plex Mono\', monospace; font-size: 12px; background: ' +
            corN + alfa + '; color: ' + (v ? '#f5f3ee' : '#4a5058') + ';' + (on ? ' box-shadow: inset 0 0 0 1.5px ' + ACCENT + ';' : '') + '">' + (v || '·') + '</div>';
        }).join('') +
        '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 11.5px; color: #8b8f96; text-align: right; align-self: center;">' + (somaLinha[n] || 0) + '</span>' +
        '</div>';
    }).join('');
    var rodapeMatriz = '<div style="display: grid; grid-template-columns: ' + gradeMatriz + '; gap: 4px; padding-top: 6px; border-top: 1px solid #242a30;">' +
      '<span style="font-size: 10.5px; color: #6d7178;">total</span>' +
      colunasV.map(function (d) {
        return '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 11.5px; color: #8b8f96; text-align: center;">' + (somaCol[d] || 0) + '</span>';
      }).join('') +
      '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 11.5px; color: #ecebe6; text-align: right;">' + selMatriz.length + '</span>' +
      '</div>';

    out.push(
      '<div class="card" style="padding: 22px 24px 20px; margin-bottom: 34px; display: flex; flex-direction: column; gap: 10px;">' +
        '<div style="display: flex; flex-direction: column; gap: 5px; margin-bottom: 8px; max-width: 760px;">' +
          '<div style="font-family: Newsreader, Georgia, serif; font-size: 26px; font-weight: 400; line-height: 1.1; color: #f5f3ee;">O que os aprovados afirmam, e para quê</div>' +
          '<div style="font-size: 12.5px; color: #8b8f96; line-height: 1.5;">Linhas: natureza da afirmação. Colunas: vertente dominante, da mais frequente à menos. A intensidade da célula acompanha a contagem. Clique numa célula para filtrar pelo par.</div>' +
        '</div>' +
        (selMatriz.length
          ? cabMatriz + corpoMatriz + rodapeMatriz
          : '<div style="padding: 44px 0; text-align: center; font-size: 12.5px; color: #6d7178;">Nenhum aprovado dentro deste recorte.</div>') +
      '</div>'
    );

    /* ══════════════ 03 · VOCABULÁRIO DA GRADE ══════════════ */
    out.push(secao('03', 'Vocabulário da grade'));

    /* Um recorte para as duas vistas, e por isso a ordem das barras e a mesma
       nas duas: o alternador troca o QUE cada barra decompoe, nunca quais
       barras existem nem em que ordem. So `areas` sai do recorte: as barras
       SAO o seletor de area. */
    var selArea = filtrados('areas');
    var areaMap = {};
    var semArea = 0;
    selArea.forEach(function (p) {
      if (!p.a) { semArea++; return; }
      if (!areaMap[p.a]) { areaMap[p.a] = { total: 0, ap: 0, sub: {} }; camadas.forEach(function (k) { areaMap[p.a][k] = 0; }); }
      var c = areaMap[p.a];
      c[camadaDe(p)] = (c[camadaDe(p)] || 0) + 1;
      c.total++;
      if (p.v === 'aprovado') c.ap++;
      if (p.sa) c.sub[p.sa] = (c.sub[p.sa] || 0) + 1;
    });
    var areasOrd = Object.keys(areaMap).sort(function (x, y) {
      return areaMap[y].total - areaMap[x].total || x.localeCompare(y);
    });
    var maxArea = Math.max.apply(null, areasOrd.map(function (a) { return areaMap[a].total; }).concat([1]));

    var defArea = {};
    (DADOS.areas || []).forEach(function (a) { defArea[a.a] = a.def || ''; });
    var defSub = DADOS.subdef || {};
    /* Corte da cauda das barras normalizadas. Nao e sobre pixel - 2% de uma
       barra larga ainda da uns 25px: e sobre a legenda. Empilhada por
       vertente, cada area traz 4 a 6 lascas abaixo de 2%, e uma legenda de dez
       verbetes onde metade aponta para uma lasca de tres papers custa a
       leitura das cinco que valem. O que a cauda carrega nao some: vai para
       "outras", que diz quantas sao e quais no tooltip. */
    var CORTE_CAUDA = 0.02;

    /* Decompoe uma barra: devolve as fatias acima do corte mais, se sobrar
       mais de uma, a fatia "outras" no fim.

       `ordemFixa` decide o arranjo: com ela as fatias saem sempre na mesma
       ordem (vertentes, onde a posicao e a identidade); sem ela saem por
       tamanho decrescente (sub-areas, onde a legenda de cada barra e que
       nomeia). Uma cauda com UM membro so volta inteira ao lugar dela: agregar
       um item sob o rotulo "outras" custaria o nome dele sem economizar
       fatia nenhuma. */
    function decompoe(conta, total, ordemFixa) {
      var chaves = ordemFixa
        ? ordemFixa.filter(function (k) { return conta[k]; })
        : Object.keys(conta).sort(function (x, y) { return conta[y] - conta[x] || x.localeCompare(y); });
      var grandes = [], cauda = [];
      /* Chave que a ordem fixa nao conhece vai para a cauda, e nao para o
         lixo: `ordemFixa` so cobre o que tem tom, e descartar o resto faria a
         barra continuar normalizando a 100% com papers a menos dentro dela. */
      if (ordemFixa) {
        Object.keys(conta).sort().forEach(function (k) {
          if (ordemFixa.indexOf(k) < 0) cauda.push(k);
        });
      }
      chaves.forEach(function (k) {
        (total && conta[k] / total < CORTE_CAUDA ? cauda : grandes).push(k);
      });
      /* Segundo corte, pelo teto da rampa: se sobrar mais fatia nomeada do que
         passo de cor, as menores descem para a cauda. Sem ele a grade crescer
         daria duas fatias do mesmo tom na mesma barra - e a legenda deixaria
         de decidir qual e qual. */
      if (grandes.length > MAX_FATIAS) {
        var porTamanho = grandes.slice().sort(function (x, y) { return conta[y] - conta[x] || x.localeCompare(y); });
        var mantidas = porTamanho.slice(0, MAX_FATIAS);
        porTamanho.slice(MAX_FATIAS).forEach(function (k) { cauda.push(k); });
        grandes = grandes.filter(function (k) { return mantidas.indexOf(k) >= 0; });
      }
      if (cauda.length === 1) {
        grandes.push(cauda[0]);
        cauda = [];
        if (ordemFixa) {
          grandes.sort(function (x, y) { return ordemFixa.indexOf(x) - ordemFixa.indexOf(y); });
        } else {
          grandes.sort(function (x, y) { return conta[y] - conta[x] || x.localeCompare(y); });
        }
      }
      var fatias = grandes.map(function (k) { return { k: k, n: conta[k], cauda: null }; });
      if (cauda.length) {
        var n = 0;
        cauda.forEach(function (k) { n += conta[k]; });
        // a cauda vai listada por tamanho decrescente no tooltip, mesmo quando
        // a barra segue ordem fixa: ali o que interessa e o que pesa mais
        cauda.sort(function (x, y) { return conta[y] - conta[x] || x.localeCompare(y); });
        fatias.push({
          k: '__outras__', n: n,
          cauda: cauda.map(function (k) { return k + ' ' + conta[k]; }).join(' · ')
        });
      }
      return fatias;
    }

    function rotuloFatia(k) { return k === '__outras__' ? 'outras' : (k === VERTENTE_NULA ? 'sem vertente' : k); }

    /* Barra normalizada a 100%: aqui a pergunta e composicao, nao volume - o
       volume esta escrito no rotulo da linha. Sem a normalizacao as tres areas
       menores viravam tocos de 5% de largura e a composicao delas, que e o
       assunto da vista, nao se enxergava. */
    function barraComposta(a, fatias, corDe, defDe, legendaPorBarra) {
      var c = areaMap[a];
      var on = s.areas.indexOf(a) >= 0;
      /* O denominador e a soma das fatias, nao `c.total`: e a barra que se
         normaliza pelas fatias que desenha (`flex` dentro de `width: 100%`).
         Com `c.total` no rotulo e a soma na geometria, uma area com papers sem
         sub-area desenharia uma fatia de 24% da largura dizendo "15,7%" - e o
         corte de 2% cairia sobre fatia que na barra vale quase 3%. */
      var base = 0;
      fatias.forEach(function (f) { base += f.n; });
      var segs = fatias.map(function (f) {
        var parte = base ? (f.n / base) * 100 : 0;
        return '<div class="seg"' +
          ev('e', mostraTip(
            rotuloFatia(f.k),
            f.cauda ? f.cauda : (defDe[f.k] || ''),
            f.n + (f.n === 1 ? ' paper · ' : ' papers · ') + parte.toFixed(1) + '% de ' + a)) +
          ev('l', escondeTip()) +
          ' style="flex: ' + f.n + '; min-width: 0; background: ' + corDe(f.k) + ';' + contornoFatia(f.k) + '"></div>';
      }).join('');
      var legenda = legendaPorBarra
        ? '<div style="display: flex; flex-wrap: wrap; gap: 4px 12px; padding-top: 1px;">' +
            fatias.map(function (f) {
              return '<span style="display: inline-flex; align-items: center; gap: 5px; font-size: 10.5px; color: #a8a49b; max-width: 100%;">' +
                '<span style="display: inline-block; flex: none; width: 16px; height: 12px; border-radius: 2px; background: ' + corDe(f.k) + ';' + contornoFatia(f.k) + '"></span>' +
                '<span>' + esc(rotuloFatia(f.k)) + ' · ' + (base ? 100 * f.n / base : 0).toFixed(1) + '%</span></span>';
            }).join('') +
          '</div>'
        : '';
      return '<div style="display: flex; flex-direction: column; gap: 6px;">' +
        '<div style="display: flex; justify-content: space-between; align-items: baseline; gap: 12px;">' +
          '<span' + ev('c', function () { alternaLista('areas', a); }) +
            ev('e', mostraTip(a, defArea[a] || '', c.total + ' papers')) + ev('l', escondeTip()) +
            ' style="font-size: 13.5px; cursor: pointer; color: ' + (on ? ACCENT : '#ecebe6') + '; font-weight: ' + (on ? '600' : '400') + '; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">' + esc(a) + '</span>' +
          '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 11.5px; color: #8b8f96; white-space: nowrap;">' + c.total + '</span>' +
        '</div>' +
        '<div style="height: 14px; background: #1d2226; border-radius: 2px; overflow: hidden;">' +
          '<div style="display: flex; height: 100%; width: 100%; gap: 2px;">' + segs + '</div>' +
        '</div>' +
        // trilho vazio le como falha de render; a linha diz por que esta vazio
        (fatias.length ? legenda
          : '<div style="font-size: 10.5px; color: #6d7178; font-style: italic;">nenhum paper desta área tem o rótulo registrado</div>') +
        '</div>';
    }

    /* ── vista Distribuição: largura absoluta, empilhada por natureza ─────── */
    var barrasArea = areasOrd.map(function (a) {
      var c = areaMap[a];
      var on = s.areas.indexOf(a) >= 0;
      var segs = camadas.slice().reverse().filter(function (k) { return c[k] > 0; }).map(function (k) {
        return '<div class="bar" style="flex: ' + c[k] + '; background: ' + corCamada(k) + ';"></div>';
      }).join('');
      return '<div' + ev('c', function () { alternaLista('areas', a); }) +
        ev('e', mostraTip(a, defArea[a] || '', detalheDia(c))) +
        ev('l', escondeTip()) +
        ' style="display: flex; flex-direction: column; gap: 6px; cursor: pointer;">' +
        '<div style="display: flex; justify-content: space-between; align-items: baseline; gap: 12px;">' +
          '<span style="font-size: 13.5px; color: ' + (on ? ACCENT : '#ecebe6') + '; font-weight: ' + (on ? '600' : '400') + '; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">' + esc(a) + '</span>' +
          '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 11.5px; color: #8b8f96; white-space: nowrap;">' + c.total + ' · ' + pct(c.ap, c.total) + '% aprovado</span>' +
        '</div>' +
        '<div style="height: 14px; background: #1d2226; border-radius: 2px; overflow: hidden;">' +
          '<div style="display: flex; height: 100%; width: ' + ((c.total / maxArea) * 100) + '%; gap: 2px; min-width: 3px;">' + segs + '</div>' +
        '</div>' +
        '</div>';
    }).join('');

    /* ── vista Sub-áreas: 100%, ordenada por tamanho dentro de cada barra ─── */
    var semSub = selArea.filter(function (p) { return p.a && !p.sa; }).length;
    var barrasSub = areasOrd.map(function (a) {
      var c = areaMap[a];
      var totalSub = 0;
      for (var k in c.sub) if (Object.prototype.hasOwnProperty.call(c.sub, k)) totalSub += c.sub[k];
      var fatias = decompoe(c.sub, totalSub, null);
      // o tom sai da POSICAO na barra, nao da sub-area: sao 64 rotulos e
      // nenhuma legenda global daria conta deles, entao quem nomeia e a
      // legenda de cada barra, logo abaixo dela
      var t = tons(fatias.filter(function (f) { return f.k !== '__outras__'; }).length);
      var tom = {};
      var i = 0;
      fatias.forEach(function (f) { tom[f.k] = f.k === '__outras__' ? FUNDO_OUTRAS : t[i++]; });
      return barraComposta(a, fatias, function (k) { return tom[k]; }, defSub, true);
    }).join('');

    var vista = s.vistaArea === 'sub' ? 'sub' : 'dist';
    var LEGENDAS_VISTA = {
      dist: 'Barras na largura do volume, empilhadas como o lote diário: descartados e as naturezas. A LLM escolhe a área de uma lista fechada. Clique para filtrar.',
      sub: 'Cada barra vale 100% e mostra do que a área é feita; o número à direita é o volume. ' +
        'Tons quentes e texturas separam as fatias; os nomes e percentuais aparecem abaixo de cada barra. ' +
        'Fatias abaixo de 2% viram “outras”, que o tooltip abre.',

    };
    /* O que ficou de fora sai escrito, em toda vista: sem isso a soma das
       barras nao bate com o numero da pilula de recorte e o painel parece ter
       perdido papers. */
    var faltantes = [];
    if (semArea) faltantes.push(semArea + (semArea === 1 ? ' paper sem área primária' : ' papers sem área primária'));
    if (vista === 'sub' && semSub) faltantes.push(semSub + ' sem sub-área');
    var notaVista = faltantes.length
      ? ' <span style="color: #6d7178;">' + faltantes.join(' e ') + ': fora das barras.</span>'
      : '';
    var corpoVista = { dist: barrasArea, sub: barrasSub }[vista];

    out.push(
      '<div class="card" style="padding: 22px 24px 20px; margin-bottom: 34px; display: flex; flex-direction: column; gap: 18px;">' +
        '<div style="display: flex; flex-wrap: wrap; justify-content: space-between; align-items: flex-start; gap: 18px;">' +
          '<div style="display: flex; flex-direction: column; gap: 5px; flex: 1 1 400px; min-width: 0; max-width: 720px;">' +
            '<div style="font-family: Newsreader, Georgia, serif; font-size: 26px; font-weight: 400; line-height: 1.1; color: #f5f3ee;">Área primária</div>' +
            '<div style="font-size: 12.5px; color: #8b8f96; line-height: 1.5; text-wrap: pretty;">' + LEGENDAS_VISTA[vista] + notaVista + '</div>' +
          '</div>' +
          '<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 9px; padding-top: 3px; max-width: 100%;">' +
            chipVista('Distribuição', vista === 'dist', function () { setState({ vistaArea: 'dist' }); }) +
            chipVista('Sub-áreas', vista === 'sub', function () { setState({ vistaArea: 'sub' }); }) +
          '</div>' +
        '</div>' +
        (corpoVista
          ? '<div style="display: flex; flex-direction: column; gap: ' + (vista === 'sub' ? '18px' : '13px') + ';">' + corpoVista + '</div>'
          : '<div style="padding: 44px 0; text-align: center; font-size: 12.5px; color: #6d7178;">Nenhuma área dentro deste recorte.</div>') +
      '</div>'
    );

    /* ══════════════ 04 · REGRAS DO CORTE ══════════════ */
    out.push(secao('04', 'Regras do corte'));

    var selPareto = filtrados('regrasFora');
    var descartes = selPareto.filter(function (p) { return p.v === 'fora'; });
    var contaRegra = {};
    descartes.forEach(function (p) {
      var k = chaveRegra(p);
      contaRegra[k] = (contaRegra[k] || 0) + 1;
    });
    var regrasOrd = Object.keys(contaRegra).sort(function (x, y) { return contaRegra[y] - contaRegra[x] || x.localeCompare(y); });
    var totalDesc = descartes.length;
    var maxRegra = Math.max.apply(null, regrasOrd.map(function (k) { return contaRegra[k]; }).concat([1]));
    var antigas = regrasOrd.filter(function (k) { return /regra antiga/.test(rotulo(k)); }).length;

    var linhasPareto = regrasOrd.map(function (k) {
      var n = contaRegra[k];
      var parte = totalDesc ? (n / totalDesc) * 100 : 0;
      var on = s.regrasFora.indexOf(k) >= 0;
      var apagada = k === REGRA_NULA || /regra antiga/.test(rotulo(k));
      return '<div' +
        ev('c', function () { alternaLista('regrasFora', k); }) +
        ev('e', mostraTip(rotulo(k), n + ' descartes · ' + parte.toFixed(1) + '% dos descartados')) +
        ev('l', escondeTip()) +
        ' style="display: flex; flex-direction: column; gap: 6px; padding-bottom: 12px; cursor: pointer;">' +
        '<div style="display: flex; align-items: baseline; justify-content: space-between; flex-wrap: wrap; gap: 6px;">' +
          '<span style="font-size: 13px; color: ' + (on ? ACCENT : (apagada ? '#8b8f96' : '#ecebe6')) + '; font-weight: ' + (on ? '600' : '400') + '; font-style: ' + (apagada ? 'italic' : 'normal') + '; line-height: 1.45;">' + esc(rotulo(k)) + '</span>' +
          '<span style="flex: none; font-family: \'IBM Plex Mono\', monospace; font-size: 11.5px; color: #8b8f96; white-space: nowrap;">' +
            n + ' <span style="color: #5f636a;">· ' + parte.toFixed(1) + '% dos descartados</span></span>' +
        '</div>' +
        '<div style="height: 13px; background: #1d2226; border-radius: 2px; overflow: hidden;">' +
          '<div class="bar" style="height: 100%; width: ' + ((n / maxRegra) * 100) + '%; min-width: 2px; background: ' + COR_FORA + '; border-radius: 2px;"></div>' +
        '</div>' +
        '</div>';
    }).join('');

    out.push(
      '<div class="card" style="padding: 22px 24px 20px; margin-bottom: 34px; display: flex; flex-direction: column; gap: 18px;">' +
        '<div style="display: flex; flex-direction: column; gap: 5px; max-width: 760px;">' +
          '<div style="font-family: Newsreader, Georgia, serif; font-size: 26px; font-weight: 400; line-height: 1.1; color: #f5f3ee;">Onde o pipeline corta</div>' +
          '<div style="font-size: 12.5px; color: #8b8f96; line-height: 1.5;">Motivos de descarte, do mais frequente ao menos frequente: geração de mídia, percepção e robótica, e o que não é sobre modelo de linguagem. Clique para filtrar.' +
            (antigas ? ' <span style="color: #6d7178;">As regras em itálico saíram em 20/10/2026 e só aparecem em descartes anteriores à reclassificação total.</span>' : '') +
          '</div>' +
        '</div>' +
        (linhasPareto
          ? '<div>' + linhasPareto + '</div>'
          : '<div style="padding: 44px 0; text-align: center; font-size: 12.5px; color: #6d7178;">Nenhum descarte dentro deste recorte.</div>') +
      '</div>'
    );

    /* ══════════════ 05 · ATENÇÃO E ADOÇÃO ══════════════ */
    out.push(secao('05', 'Atenção e adoção'));

    /* Crescimento absoluto entre observações dentro da mesma janela de 7 dias.
       Não tratamos ausência de snapshot como zero nem extrapolamos intervalos. */
    var ROXO_VOTO = '#9085e9';
    function medidasVoto(p) {
      return (DADOS.serie[p.id] || []).filter(function (m) {
        return diaNum(m[0]) !== null && typeof m[1] === 'number' && isFinite(m[1]) && m[1] >= 0;
      }).slice().sort(function (a, b) { return a[0].localeCompare(b[0]); });
    }
    var fimVoto = diaNum(String(DADOS.gerado).slice(0, 10));
    var hojeNum = fimVoto; // também usado na idade das medições da dispersão
    var inicioVoto = fimVoto - 7;
    var crescimento = [];
    sel.forEach(function (p) {
      var ms = medidasVoto(p).filter(function (m) { return diaNum(m[0]) >= inicioVoto && diaNum(m[0]) <= fimVoto; });
      if (ms.length < 2) return;
      var a = ms[0], b = ms[ms.length - 1];
      if (b[1] <= a[1] || b[0] === a[0]) return;
      crescimento.push({ p: p, de: a, ate: b, delta: b[1] - a[1] });
    });
    crescimento.sort(function (a, b) { return b.delta - a.delta || a.p.id.localeCompare(b.p.id); });
    var topVotos = crescimento.slice(0, 10);
    // Escala comum de votos absolutos: círculo vazio = início, cheio = fim.
    var maxTotalVoto = Math.max.apply(null, topVotos.map(function (r) { return r.ate[1]; }).concat([1]));
    var barrasVoto = topVotos.map(function (r, i) {
      var xInicio = r.de[1] / maxTotalVoto * 100;
      var xFim = r.ate[1] / maxTotalVoto * 100;
      var intervalo = diaCurto(r.de[0]) + '–' + diaCurto(r.ate[0]);
      return '<a class="voto-item" href="' + esc(r.p.url) + '" target="_blank" rel="noopener"' +
        ev('e', mostraTip(r.p.t, '+' + r.delta + ' votos · ' + r.de[1] + ' → ' + r.ate[1] + ' · ' + intervalo + ' · ' + (r.p.v === 'fora' ? 'fora' : rotuloNatureza(natureza(r.p))))) + ev('l', escondeTip()) +
        '><div class="voto-item-miolo"><div class="voto-item-cab">' + esc(r.p.t) + '</div>' +
        '<div class="voto-tracao" aria-hidden="true">' +
          '<span class="voto-tracao-linha" style="left: ' + xInicio + '%; width: ' + (xFim - xInicio) + '%; background: ' + corPaper(r.p) + ';"></span>' +
          '<span class="voto-tracao-inicio" style="left: ' + xInicio + '%; border-color: ' + corPaper(r.p) + ';"></span>' +
          '<span class="voto-tracao-fim" style="left: ' + xFim + '%; background: ' + corPaper(r.p) + ';"></span>' +
        '</div><div class="voto-item-detalhe">' + r.de[1] + ' → ' + r.ate[1] + ' votos · ' + intervalo + '</div></div>' +
        '<b class="voto-item-ganho">+' + r.delta + '</b></a>';
    }).join('');
    var legendaVotos = camadas.map(function (k) {
      return '<span style="background: ' + corCamada(k) + ';"></span>' + esc(rotuloCamada(k));
    }).join('');

    /* Curva por idade: somente observações reais, de papers acompanhados desde
       o dia 0/1 e com medição aos 14 dias ou depois. Backfills tardios não
       contam como evidência de amadurecimento. A amostra pode variar por idade;
       buracos não recebem interpolação e ficam explícitos no desenho. */
    var MIN_VOTO = 5, HORIZONTE_VOTO = 30;
    var acumuloVoto = {}, nMaduros = 0;
    sel.forEach(function (p) {
      var base = diaNum(p.d);
      if (base === null) return;
      var ms = medidasVoto(p).filter(function (m) { return diaNum(m[0]) >= base && diaNum(m[0]) <= fimVoto; });
      if (ms.length < 2 || diaNum(ms[0][0]) - base > 1) return;
      var ultimo = ms[ms.length - 1];
      if (diaNum(ultimo[0]) - base < 14 || ultimo[1] <= 0) return;
      nMaduros++;
      ms.forEach(function (m) {
        var idade = diaNum(m[0]) - base;
        if (idade > HORIZONTE_VOTO) return;
        if (!acumuloVoto[idade]) acumuloVoto[idade] = [];
        acumuloVoto[idade].push(m[1] / ultimo[1] * 100);
      });
    });
    var curvaVoto = [];
    for (var iv = 0; iv <= HORIZONTE_VOTO; iv++) {
      var xs = acumuloVoto[iv] || [];
      curvaVoto.push(xs.length < MIN_VOTO ? null : { idade: iv, n: xs.length, med: quartil(xs, .5), q1: quartil(xs, .25), q3: quartil(xs, .75) });
    }
    var validosVoto = curvaVoto.filter(Boolean);
    // `.filter(...)[0]` e nao `.find(...)`: `find` e ES6 e o painel roda em
    // visualizador de HTML antigo, onde o TypeError levaria a pagina inteira.
    var marcoVoto = validosVoto.filter(function (r) { return r.med >= 90; })[0];
    var maxIdadeVoto = validosVoto.length ? Math.max(14, validosVoto[validosVoto.length - 1].idade) : 14;
    var tetoVoto = Math.max(100, Math.ceil(Math.max.apply(null, validosVoto.map(function (r) { return r.q3; }).concat([100])) / 25) * 25);
    function passoEixo(intervalo, alvo) {
      var bruto = intervalo / Math.max(1, alvo);
      var mag = Math.pow(10, Math.floor(Math.log(bruto) / Math.LN10));
      var n = bruto / mag;
      return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * mag;
    }
    function xv(v) { return 3 + v / maxIdadeVoto * 94; }
    function yv(v) { return 95 - v / tetoVoto * 90; }
    var desenhoVoto = '', eixoVotoY = '', eixoVotoX = '';
    for (var gy = 0; gy <= tetoVoto; gy += tetoVoto / 4) {
      desenhoVoto += poliLinha([[3, yv(gy)], [97, yv(gy)]], '#2b3138', 1, null);
      eixoVotoY += '<span style="position: absolute; right: 0; top: ' + yv(gy) + '%; transform: translateY(-50%); font-size: 10px; color: #8b8f96;">' + Math.round(gy) + '%</span>';
    }
    desenhoVoto += poliLinha([[3, yv(90)], [97, yv(90)]], '#8b8f96', 1, '4 4');
    trechos(curvaVoto).forEach(function (tr) {
      if (tr.length > 1) {
        desenhoVoto += poliArea(tr.map(function (r) { return [xv(r.idade), yv(r.q3)]; }).concat(tr.slice().reverse().map(function (r) { return [xv(r.idade), yv(r.q1)]; })), ROXO_VOTO, .16);
        desenhoVoto += poliLinha(tr.map(function (r) { return [xv(r.idade), yv(r.med)]; }), ROXO_VOTO, 2.5, null);
      } else {
        var r = tr[0];
        desenhoVoto += poliLinha([[xv(r.idade), yv(r.q1)], [xv(r.idade), yv(r.q3)]], ROXO_VOTO, 1.5, null);
      }
    });
    var marcasVoto = validosVoto.map(function (r) {
      return '<button class="mark voto-ponto" aria-label="Dia ' + r.idade + ': mediana ' + r.med.toFixed(1) + '%, ' + r.n + ' papers"' +
        ev('e', mostraTip('Dia +' + r.idade + ' desde o HF Daily', 'Mediana ' + r.med.toFixed(1) + '% · P25–P75: ' + r.q1.toFixed(1) + '–' + r.q3.toFixed(1) + '% · ' + r.n + ' papers medidos')) + ev('l', escondeTip()) +
        ' style="position: absolute; left: ' + xv(r.idade) + '%; top: ' + yv(r.med) + '%; width: 10px; height: 10px; padding: 0; margin: -5px; border-radius: 50%; background: ' + ROXO_VOTO + '; border: 2px solid #16191c;"></button>';
    }).join('');
    for (var gx = 0; gx <= maxIdadeVoto; gx += Math.max(1, passoEixo(maxIdadeVoto, 5))) {
      eixoVotoX += '<span style="position: absolute; left: ' + xv(gx) + '%; transform: translateX(-50%); font-size: 10px; color: #8b8f96;">' + gx + '</span>';
    }
    var graficoVoto = validosVoto.length ?
      '<div class="voto-nota">% do último total observado por paper</div>' +
      '<div style="display: grid; grid-template-columns: 36px minmax(0, 1fr); gap: 6px;"><div style="position: relative; height: 228px;">' + eixoVotoY + '</div><div style="position: relative; height: 228px;">' + svgPlano(desenhoVoto) + marcasVoto + '</div></div>' +
      '<div style="margin-left: 42px;"><div style="height: 18px; position: relative;">' + eixoVotoX + '</div><div class="voto-nota" style="text-align: center;">Dias desde a entrada no HF Daily</div></div>' :
      '<div class="voto-nota" style="padding: 60px 0;">Amostra insuficiente: nenhuma idade reúne pelo menos ' + MIN_VOTO + ' papers com acompanhamento desde o início e medição aos 14 dias ou depois.</div>';
    out.push('<div class="votos-grid"><div class="card voto-card" id="votos-crescimento">' +
      '<div><div class="voto-titulo">Os 10 papers que mais ganharam votos</div><div class="voto-nota" style="margin-top: 6px;">Ganho absoluto medido nos últimos 7 dias, até ' + diaCurto(String(DADOS.gerado).slice(0, 10)) + '. Círculo vazio: início; preenchido: fim, na mesma escala de votos. Clique no título para abrir o paper.</div><div class="voto-legenda">' + legendaVotos + '</div></div>' +
      '<div class="voto-ranking" tabindex="0" aria-label="Ranking de crescimento de votos">' + (barrasVoto || '<div class="voto-nota">Nenhum paper com duas medições e crescimento positivo nesta janela.</div>') + '</div>' +
      '<div class="voto-nota" style="margin-top: auto; border-top: 1px solid #242a30; padding-top: 12px;">Última menos primeira medição disponível na janela. O intervalo de cada paper aparece na lista; não é uma taxa diária.</div></div>' +
      '<div class="card voto-card" id="votos-maturacao"><div><div class="voto-titulo">Quando os votos chegam a 90%?</div><div class="voto-nota" style="margin-top: 6px;">A linha roxa mostra a mediana do percentual de votos acumulados em relação ao último total observado de cada paper. Chegar a 90% não significa estabilização definitiva.</div></div>' +
      '<div class="voto-resumo"><div><strong>' + (marcoVoto ? 'D+' + marcoVoto.idade : '—') + '</strong><div class="voto-nota">primeira idade medida com mediana ≥ 90%</div></div><div><strong>' + nMaduros + '</strong><div class="voto-nota">papers com histórico elegível</div></div></div>' +
      '<div class="voto-legenda"><span style="height: 2px; width: 18px; background: ' + ROXO_VOTO + ';"></span>mediana<span style="background: #9085e929;"></span>P25–P75<span style="height: 0; width: 18px; border-top: 1px dashed #8b8f96;"></span>90%</div>' + graficoVoto +
      '<div class="voto-nota" style="border-top: 1px solid #242a30; padding-top: 12px;">Entram papers com pelo menos duas medições, a primeira no dia 0 ou 1 e a última aos 14 dias ou depois, com total de votos positivo. Papers com uma única medição ou histórico ainda curto ficam de fora. Cada ponto usa apenas quem foi medido naquela idade, com mínimo de ' + MIN_VOTO + ' papers; por isso, a amostra varia ao longo da curva. Lacunas não são interpoladas e o último total observado ainda pode crescer.</div></div></div>');

    /* ── upvotes no HF × stars no GitHub ────────────────────────────────── */
    /* So papers com repositorio. `gs = 0` e um repositorio sem estrela nenhuma
       e continua no grafico, na base do eixo; paper sem repositorio nao tem
       coordenada Y e fica de fora - as duas coisas parecem "zero" e nao sao. */
    var selGh = sel.filter(function (p) { return !s.ghVeredito || p.v === s.ghVeredito; });
    var comRepo = selGh.filter(function (p) { return p.oa === 1; });
    var semRepo = selGh.length - comRepo.length;
    var zeroStar = comRepo.filter(function (p) { return !p.gs; }).length;
    var maxU = Math.max.apply(null, comRepo.map(function (p) { return p.u; }).concat([1]));
    var maxG = Math.max.apply(null, comRepo.map(function (p) { return p.gs; }).concat([1]));
    var rotulados = {};
    comRepo.slice().sort(function (a, b) { return b.u - a.u; }).slice(0, 3).forEach(function (p) { rotulados[p.id] = 1; });
    comRepo.slice().sort(function (a, b) { return b.gs - a.gs; }).slice(0, 3).forEach(function (p) { rotulados[p.id] = 1; });

    var pontosGh = comRepo.map(function (p) {
      var x = escalaLog(p.u, maxU), y = escalaLog(p.gs, maxG);
      var forma = p.pp
        ? 'width: 9px; height: 9px; margin-left: -4.5px; margin-bottom: -4.5px; transform: rotate(45deg); border-radius: 1px;'
        : 'width: 8px; height: 8px; margin-left: -4px; margin-bottom: -4px; border-radius: 50%;';
      var aDireita = x > 62;
      var rot = rotulados[p.id]
        ? '<span style="position: absolute; ' +
          (aDireita ? 'right: ' + (100 - x) + '%; margin-right: 9px; text-align: right;' : 'left: ' + x + '%; margin-left: 9px;') +
          ' bottom: ' + y + '%; margin-bottom: -6px; font-size: 10.5px; color: #8b8f96; white-space: nowrap; pointer-events: none;">' + esc(rotuloCurto(p.t, 34)) + '</span>'
        : '';
      var classe = p.v === 'fora' ? 'fora' : rotuloNatureza(natureza(p));
      return '<a class="mark" href="' + esc(p.url) + '" target="_blank" rel="noopener"' +
        ev('e', mostraTip(p.t, p.u + ' votos · ' + p.gs + ' stars · ' + p.c + ' comentários · ' + classe + ' · ' + (p.a ? parArea(p) : 'sem área') + ' · ' + (p.org || 'sem organização') +
          (hojeNum !== null && diaNum(p.d) !== null ? ' · ' + (hojeNum - diaNum(p.d)) + 'd no HF' : ''))) +
        ev('l', escondeTip()) +
        ' style="position: absolute; left: ' + x + '%; bottom: ' + y + '%; ' + forma +
        ' background: ' + corPaper(p) + '; opacity: 0.78; border-bottom: none;"></a>' + rot;
    }).join('');
    var gradeGh = [25, 50, 75].map(function (g) {
      return '<div style="position: absolute; left: 0; right: 0; bottom: ' + g + '%; height: 1px; background: #1d2226;"></div>' +
        '<div style="position: absolute; top: 0; bottom: 0; left: ' + g + '%; width: 1px; background: #1d2226;"></div>';
    }).join('');
    var eixoGhY = ticksLog(maxG).map(function (v) {
      return '<span style="position: absolute; bottom: ' + escalaLog(v, maxG) + '%; right: 0; transform: translateY(50%); font-family: \'IBM Plex Mono\', monospace; font-size: 10.5px; color: #6d7178;">' + v + '</span>';
    }).join('');
    var eixoGhX = ticksLog(maxU).map(function (v) {
      return '<span style="position: absolute; left: ' + escalaLog(v, maxU) + '%; transform: translateX(-50%); font-family: \'IBM Plex Mono\', monospace; font-size: 10.5px; color: #6d7178;">' + v + '</span>';
    }).join('');

    var legendaGh = '<div style="display: flex; gap: 15px; flex-wrap: wrap; align-items: center;">' +
      ['', 'aprovado', 'fora'].map(function (v) {
        return '<button type="button" class="chip" aria-pressed="' + (s.ghVeredito === v) + '"' + ev('c', function () { setState({ ghVeredito: v }); }) +
          ' style="' + (s.ghVeredito === v ? pillOnGlobal() : pill(false)) + ' font: inherit; font-size: 11.5px; padding: 6px 12px;">' + (v || 'todos') + '</button>';
      }).join('') +
      '<div class="voto-legenda" style="margin-top: 0;">' + camadas.map(function (k) {
        return '<span style="background: ' + corCamada(k) + '; border-radius: 50%; width: 8px;"></span>' + esc(rotuloCamada(k));
      }).join('') + '</div>' +
      '<div style="display: flex; align-items: center; gap: 6px; font-size: 11.5px; color: #a8a49b;">' +
        '<span style="display: inline-block; width: 8px; height: 8px; border: 1px solid #f5f3ee; background: transparent; transform: rotate(45deg);"></span>com página do projeto</div>' +
      '</div>';

    out.push(
      '<div class="card" style="padding: 22px 24px 20px; margin-bottom: 34px; display: flex; flex-direction: column; gap: 16px;">' +
        '<div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 18px;">' +
          '<div style="display: flex; flex-direction: column; gap: 5px; max-width: 700px;">' +
            '<div style="font-family: Newsreader, Georgia, serif; font-size: 26px; font-weight: 400; line-height: 1.1; color: #f5f3ee;">Upvotes no HF × stars no GitHub</div>' +
            '<div style="font-size: 12.5px; color: #8b8f96;">Um ponto por paper com repositório, nas duas escalas logarítmicas, na cor da natureza. ' +
              '<span style="color: #6d7178;">' + zeroStar + ' com repositório e zero star ficam na base do eixo; ' + semRepo + ' sem repositório não entram.</span></div>' +
          '</div>' +
        '</div>' +
        legendaGh +
        (comRepo.length
          ? '<div style="display: grid; grid-template-columns: 40px minmax(0, 1fr); gap: 10px;">' +
              '<div style="position: relative; height: 268px;">' + eixoGhY + '</div>' +
              '<div style="position: relative; height: 268px; border-left: 1px solid #333a41; border-bottom: 1px solid #333a41;">' + gradeGh + pontosGh +
                '<span style="position: absolute; left: 10px; top: 7px; font-size: 10.5px; letter-spacing: 0.14em; color: #8b8f96;">STARS ↑</span>' +
              '</div>' +
              '<div></div>' +
              '<div><div style="position: relative; height: 14px;">' + eixoGhX + '</div>' +
                '<div style="text-align: right; font-size: 10px; letter-spacing: 0.13em; color: #6d7178;">UPVOTES →</div>' +
              '</div>' +
            '</div>'
          : '<div style="padding: 76px 0; text-align: center; font-size: 12.5px; color: #6d7178;">Nenhum paper com repositório dentro deste recorte.</div>') +
      '</div>'
    );

    }  // fim da aba Panorama

    /* ══════════════ APROVADOS · POR DIA ══════════════

       Paginacao por DIA de publicacao, e nao por blocos de dez: com o escopo do
       ADR 004 sao dezenas de aprovados por dia, e o dia e a unidade em que o
       painel e lido. So o dia visivel e desenhado. Dentro do dia, a ordem e o
       voto - upvote ordena a exibicao, nunca classifica nem corta. O filtro de veredito do
       Panorama nao vale aqui: esta aba e so de aprovados. */
    if (s.aba === 'aprovados') {

    var listaAp = filtrados('vereditos').filter(function (p) { return p.v === 'aprovado'; });
    var porDiaAp = {};
    listaAp.forEach(function (p) { (porDiaAp[p.d] = porDiaAp[p.d] || []).push(p); });
    var diasAp = Object.keys(porDiaAp).sort().reverse();   // mais recente primeiro
    var diaAtual = diasAp.indexOf(s.diaPag) >= 0 ? s.diaPag : (diasAp[0] || null);
    var posDia = diaAtual ? diasAp.indexOf(diaAtual) : -1;
    var doDia = (porDiaAp[diaAtual] || []).slice().sort(function (a, b) {
      return b.u - a.u || a.id.localeCompare(b.id);
    });

    var colunas = '132px minmax(240px, 1.3fr) 150px minmax(200px, 1fr) 110px 56px';
    var linhasFicha = doDia.map(function (p) {
      var f = fichaPorId[p.id];
      var aberta = s.aberta === p.id;
      return '<div style="border-bottom: 1px solid #1d2226;">' +
        '<div class="row" data-card="' + esc(p.id) + '"' + ev('c', function () { setState({ aberta: aberta ? null : p.id }); }) + ' style="display: grid; grid-template-columns: ' + colunas + '; gap: 14px; padding: 14px 24px; align-items: center;">' +
          '<span>' + seloNatureza(p.nt) + '</span>' +
          '<div style="display: flex; flex-direction: column; gap: 4px; min-width: 0;">' +
            '<span style="font-size: 13.5px; color: #ecebe6; line-height: 1.35; text-wrap: pretty;">' + esc(p.t) + '</span>' +
            (p.org || !f
              ? '<span style="font-size: 11.5px; color: #6d7178; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">' + esc([p.org, f ? '' : 'sem ficha'].filter(Boolean).join(' · ')) + '</span>'
              : '') +
          '</div>' +
          '<span style="display: flex; gap: 6px; flex-wrap: wrap;">' + marcasCard(p) + '</span>' +
          '<span style="font-size: 11.5px; color: #8b8f96; line-height: 1.5;">' + esc(parArea(p)) + '</span>' +
          celulaVertente(p) +
          '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 12.5px; color: #ecebe6; text-align: right;">' + p.u + '</span>' +
        '</div>' + (aberta ? corpoAberto(p, f, 'jan:' + p.id, '<span style="font-size: 11.5px; color: #6d7178;">' + esc(p.org || '') + '</span>') : '') +
        '</div>';
    }).join('');

    function navDia(alvo, texto, ativo) {
      return ativo
        ? '<div class="chip" data-nav-dia="' + esc(texto) + '"' + ev('c', function () { setState({ diaPag: alvo, aberta: null, justExp: {} }); }) +
            ' style="' + pill(false) + ' font-size: 11.5px; padding: 6px 12px;">' + texto + '</div>'
        : '<div style="' + pill(false) + ' font-size: 11.5px; padding: 6px 12px; opacity: 0.35;">' + texto + '</div>';
    }
    var navegacao = diaAtual
      ? '<div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">' +
          navDia(diasAp[posDia + 1], '← dia anterior', posDia + 1 < diasAp.length) +
          '<span data-dia-atual="' + esc(diaAtual) + '" style="font-family: \'IBM Plex Mono\', monospace; font-size: 13px; color: #ecebe6;">' + diaCurto(diaAtual) +
            '<span style="color: #6d7178;"> · ' + doDia.length + ' aprovado(s) · dia ' + (posDia + 1) + ' de ' + diasAp.length + '</span></span>' +
          navDia(diasAp[posDia - 1], 'dia seguinte →', posDia > 0) +
        '</div>'
      : '';

    out.push(
      '<div class="card" style="overflow-x: auto;">' +
        '<div style="display: flex; justify-content: space-between; align-items: flex-end; gap: 28px; padding: 22px 24px 18px; flex-wrap: wrap;">' +
          '<div style="display: flex; flex-direction: column; gap: 5px;">' +
            '<div style="font-family: Newsreader, Georgia, serif; font-size: 26px; font-weight: 400; line-height: 1.1; color: #f5f3ee;">Aprovados, dia a dia</div>' +
            '<div style="font-size: 12.5px; color: #8b8f96;">Ordenados por voto. Clique numa linha para abrir o porquê da classificação — e a ficha completa.</div>' +
          '</div>' +
          navegacao +
        '</div>' +
        '<div style="display: grid; grid-template-columns: ' + colunas + '; gap: 14px; padding: 11px 24px; border-top: 1px solid #242a30; border-bottom: 1px solid #242a30; background: #131619; font-size: 10.5px; font-weight: 600; letter-spacing: 0.14em; color: #8b8f96;">' +
          '<span>NATUREZA</span><span>TÍTULO</span><span>MARCAS</span><span>ÁREA &gt; SUB-ÁREA</span><span>VERTENTE</span><span style="text-align: right;">VOTOS</span>' +
        '</div>' +
        linhasFicha +
        (linhasFicha ? '' : '<div style="padding: 54px 24px; text-align: center; font-size: 13px; color: #6d7178;">Nenhum paper aprovado dentro deste recorte.</div>') +
        '<div style="display: flex; align-items: center; gap: 14px; padding: 15px 24px; flex-wrap: wrap;">' +
          '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 11px; color: #6d7178;">' +
            listaAp.length + ' aprovado(s) no recorte, em ' + diasAp.length + ' dia(s).' +
          '</span>' +
          navegacao +
        '</div>' +
      '</div>'
    );

    }  // fim da aba Aprovados

    /* ══════════════ RODAPÉ ══════════════ */
    out.push(rodape('FONTE: data/hfpapers.db → marts/*.parquet · ' + todos.length + ' PAPERS · ' + DADOS.fichas.length + ' FICHAS'));

    out.push('</div>');
    return out.join('');
  }

  function render() {
    // guarda foco/cursor: o re-render troca o input inteiro a cada tecla
    var ativo = document.activeElement;
    var focoId = ativo && ativo.id ? ativo.id : null;
    var caret = focoId ? ativo.selectionStart : null;

    H = [];
    root.innerHTML = construir();

    root.querySelectorAll('[data-c]').forEach(function (el) {
      el.addEventListener('click', H[+el.getAttribute('data-c')]);
    });
    root.querySelectorAll('[data-e]').forEach(function (el) {
      el.addEventListener('mouseenter', H[+el.getAttribute('data-e')]);
      el.addEventListener('mousemove', H[+el.getAttribute('data-e')]);
    });
    root.querySelectorAll('[data-l]').forEach(function (el) {
      el.addEventListener('mouseleave', H[+el.getAttribute('data-l')]);
    });
    root.querySelectorAll('[data-i]').forEach(function (el) {
      el.addEventListener('input', H[+el.getAttribute('data-i')]);
    });

    if (focoId) {
      var novo = document.getElementById(focoId);
      if (novo) {
        novo.focus();
        if (caret !== null && novo.setSelectionRange) novo.setSelectionRange(caret, caret);
      }
    }
  }

  render();
})();
