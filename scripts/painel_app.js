/* Painel Daily Papers - porte do design canvas para HTML/JS puro.
 *
 * O desenho nasceu como artboard `.dc.html` da Claude Design (Artifact
 * "Painel Daily Papers"). Aquele arquivo so roda dentro do runtime do canvas;
 * este e o mesmo layout e a mesma logica de recorte reescritos em JS de
 * navegador, para o painel abrir em qualquer lugar.
 *
 * Duas diferencas deliberadas em relacao ao original:
 *
 * 1. O tooltip nao passa pelo estado. No canvas cada hover era um setState e
 *    um re-render; com 268 pontos de dispersao isso pisca no navegador. Aqui o
 *    tooltip e um no fixo que so muda de posicao e texto.
 *
 * 2. A linha de filtro que esta com o menu aberto sobe para z-index 90. No
 *    canvas as linhas ficam em 4/3/2/1 e a cortina de fechar em 80 - o que
 *    deixaria o proprio menu embaixo da cortina num navegador de verdade.
 *
 * O resto (cores, tipografia, ordem das secoes, textos) e o artboard.
 */
(function () {
  'use strict';

  /* ACCENT e so link e destaque (ticket 04). Ele ja significou "aprovado" na
     linha da taxa, no heatmap e na matriz - e por isso brigava com o proprio
     papel de chamar atencao: metade do painel ficava amarela. Aprovado agora
     tem cor propria, VERDE, e ela vale em todo lugar onde a medida e "quanto
     passou". */
  var ACCENT = '#d9a441';
  var VERDE = '#4ec07a';

  var COMPACTA = false;

  var root = document.getElementById('painel');
  var elTip = document.getElementById('tip');

  var state = {
    aba: 'aprovados',
    diasSel: [], vereditos: [], areas: [], subareas: [], vertentes: [], orgs: [],
    // recortes que so o grafico produz (nao ha menu para eles na barra de
    // filtro): `regrasFora` vem do clique no Pareto e `criterios` do clique no
    // card espelho dele ("Por que o pipeline aprova"). Entram em `filtrados()`
    // como qualquer dimensao.
    regrasFora: [], criterios: [],
    // 'dia' por padrao: a aba abre no que chegou hoje, nao no mais votado
    busca: '', ordem: 'dia', aberta: null,
    // "mostrar mais" da tabela de aprovados: quantas paginas alem da primeira
    // estao abertas. Nao zera quando o recorte muda - quem pediu para ver mais
    // uma vez quer continuar vendo mais.
    maisAprovados: 0,
    menu: null, buscaMenu: '',
    perSel: null, abertaH: null,
    // Controles locais dos cards; não alteram o recorte global.
    // `vistaArea`: 'dist' | 'sub'.
    vistaArea: 'dist', taxaDecomp: false, ghVeredito: '',
    // "mais" do cabecalho da decisao, por card aberto (chave: secao + id) -
    // um objeto, nao um id unico, porque o card da aba viva e o do hall podem
    // estar abertos ao mesmo tempo (abas diferentes, mesmo estado).
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

  function setState(patch) {
    for (var k in patch) if (Object.prototype.hasOwnProperty.call(patch, k)) state[k] = patch[k];
    render();
  }

  /* ── cores das series (dataviz, coluna dark; hex literais) ─────────────── */
  function cor(v) { return v === 'estrito' ? '#3987e5' : v === 'amplo' ? '#d95926' : '#6b7480'; }
  function corTexto(v) { return v === 'estrito' ? '#6aa9ee' : v === 'amplo' ? '#e8794c' : '#8b8f96'; }

  /* Chave do motivo de descarte. `regra_fora` so existe para quem saiu, e a
     cobertura hoje e parcial - o Pareto exige que o nulo continue visivel em
     vez de sumir da contagem, entao ele vira uma categoria de verdade. */
  var REGRA_NULA = '__sem-regra__';
  function chaveRegra(p) { return p.rf || REGRA_NULA; }

  /* ── enum → rótulo legível ──────────────────────────────────────────────
     UM mapa para os tres vocabularios que o painel imprime: os 10 criterios de
     veredito, as 6 regras de descarte e a categoria do nulo. Um so porque os
     dois lugares que os exibem nao podem divergir - a linha do veredito da
     ficha ("ESTRITO · artefato aberto + benchmark"), a contraparte de uma
     decisao de fronteira (que pode ser criterio OU regra, por isso o mesmo
     registro atende as duas) e as barras dos dois cards da secao 03.

     Mora aqui, e nao em `gerar_painel.py`, porque o navegador e o unico
     consumidor: serializar 16 strings dentro de `DADOS` as repetiria no
     arquivo distribuido sem nenhum leitor em Python. Os ENUMS vem de
     `src/hfpapers/llm/schemas.py` (REGRAS_FORA, CRITERIOS_ESTRITO,
     CRITERIOS_AMPLO) - copiados de la, nao inventados; um enum novo que
     aparecer sem entrada aqui sai como o proprio enum, feio mas honesto. */
  var CRITERIOS_ESTRITO = [
    'padrao_arquitetural', 'artefato_aberto', 'invalida_pratica',
    'vulnerabilidade', 'tecnica_de_avaliacao'
  ];
  var CRITERIOS_AMPLO = [
    'benchmark', 'panorama', 'framework_conceitual',
    'principio_sem_o_como', 'exige_acesso_interno'
  ];
  var CRITERIOS = CRITERIOS_ESTRITO.concat(CRITERIOS_AMPLO);

  var ROTULOS = {
    // criterios de veredito (schemas.CRITERIOS_ESTRITO)
    padrao_arquitetural: 'padrão arquitetural',
    artefato_aberto: 'artefato aberto',
    invalida_pratica: 'invalida prática corrente',
    vulnerabilidade: 'vulnerabilidade',
    tecnica_de_avaliacao: 'técnica de avaliação',
    // (schemas.CRITERIOS_AMPLO)
    benchmark: 'benchmark',
    panorama: 'panorama',
    framework_conceitual: 'framework conceitual',
    principio_sem_o_como: 'princípio sem o como',
    exige_acesso_interno: 'exige acesso interno',
    // regras de descarte (schemas.REGRAS_FORA, na ordem de teste)
    treino_ou_postreino: 'treino ou pós-treino',
    geracao_de_midia: 'geração de mídia',
    percepcao_robotica_embodied: 'percepção robótica / embodied',
    relatorio_tecnico_de_modelo: 'relatório técnico de modelo',
    fora_de_escopo: 'fora de escopo',
    portabilidade_reprovada: 'portabilidade reprovada'
  };
  ROTULOS[REGRA_NULA] = 'regra não registrada';

  function rotulo(k) {
    return Object.prototype.hasOwnProperty.call(ROTULOS, k) ? ROTULOS[k] : String(k);
  }
  /* Lado do criterio, na ordem canonica do `schemas.py`. A ficha lista os criterios nessa ordem -
     um paper estrito le "artefato aberto + benchmark", nunca o contrario. */
  function ordemCriterio(k) {
    var i = CRITERIOS.indexOf(k);
    return i < 0 ? CRITERIOS.length : i;
  }
  function criteriosOrdenados(lista) {
    return (lista || []).slice().sort(function (a, b) {
      return ordemCriterio(a) - ordemCriterio(b) || a.localeCompare(b);
    });
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

  /* `exceto` deixa uma ou mais dimensoes de fora: e o que mantem as outras
     opcoes de um seletor visiveis depois que ele ja filtrou (senao marcar a 2a
     area pelo grafico ficaria impossivel - a 1a teria apagado as demais
     barras). Aceita string ou array: a matriz de areas precisa soltar as duas
     dimensoes de area de uma vez para nao virar uma unica celula acesa.

     TODAS as dimensoes sao soltaveis, inclusive `diasSel` e `vereditos`, que
     por muito tempo nao eram: as contagens da barra de filtro dependem disso
     (ver `construir`), e sem soltar o veredito o chip `estrito` teria de se
     contar num universo do qual ele mesmo ja tirou os outros dois. */
  function filtrados(exceto) {
    var s = state;
    var q = (s.busca || '').trim().toLowerCase();
    var solta = typeof exceto === 'string' ? [exceto] : (exceto || []);
    function livre(dim) { return solta.indexOf(dim) >= 0; }
    return DADOS.papers.filter(function (p) {
      if (!livre('diasSel') && s.diasSel.length && s.diasSel.indexOf(p.d) < 0) return false;
      if (!livre('vereditos') && s.vereditos.length && s.vereditos.indexOf(p.v) < 0) return false;
      // dentro de cada dimensao a selecao e OR; entre dimensoes, AND
      if (!livre('areas') && s.areas.length && s.areas.indexOf(p.a) < 0) return false;
      if (!livre('subareas') && s.subareas.length && s.subareas.indexOf(p.sa) < 0) return false;
      // Vertente DOMINANTE, nao "tem a vertente": `p.vt` chega ordenado por
      // `ponte_paper_vertente.ordem` e a primeira e a que manda. O menu filtra
      // pelo mesmo criterio com que a vista "Vertentes" empilha - se um
      // filtrasse por presenca e o outro empilhasse por dominante, marcar uma
      // vertente devolveria barras que nao somam o numero da pilula.
      if (!livre('vertentes') && s.vertentes.length &&
        s.vertentes.indexOf(dominante(p)) < 0) return false;
      // marcar uma regra e marcar um recorte de descartados: quem foi aprovado
      // nao tem regra nenhuma e nao pode entrar pela porta do nulo
      if (!livre('regrasFora') && s.regrasFora.length && (p.v !== 'fora' || s.regrasFora.indexOf(chaveRegra(p)) < 0)) return false;
      // espelho exato da regra acima: criterio de veredito so existe para quem
      // foi aprovado, entao marcar um criterio ja implica excluir os `fora`
      if (!livre('criterios') && s.criterios.length &&
        (p.v === 'fora' || !s.criterios.some(function (c) { return (p.cr || []).indexOf(c) >= 0; }))) return false;
      if (!livre('orgs') && s.orgs.length) {
        var chave = p.org || '__sem-org__';
        if (s.orgs.indexOf(chave) < 0) return false;
      }
      if (q) {
        var alvo = (p.t + ' ' + (p.org || '') + ' ' + p.id).toLowerCase();
        if (alvo.indexOf(q) < 0) return false;
      }
      return true;
    });
  }

  /* liga/desliga um valor numa dimensao de selecao multipla */
  function alternaLista(campo, valor) {
    var l = state[campo].slice();
    var i = l.indexOf(valor);
    if (i < 0) l.push(valor); else l.splice(i, 1);
    // `aberta` some porque o card que estava aberto pode nem sobreviver ao
    // novo recorte; `justExp` some pelo mesmo motivo - guardar o "mais" de um
    // card que o filtro tirou de cena so acumularia estado morto.
    var novo = { aberta: null, justExp: {} };
    novo[campo] = l;
    setState(novo);
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

  /* Os cinco campos da ficha, na ordem normativa, cada um com sua cor.
     Os hexes sao os slots dark do catalogo na ordem canonica (aqua, yellow,
     magenta, violet, red) - validados como conjunto contra o fundo do card.
     Azul e laranja ficam de fora de proposito: pertencem a estrito e amplo. */
  function camposFicha(f) {
    var cores = {
      'ACHADO': '#199e70',
      'PADRÃO EXTRAÍDO': '#c98500',
      'IMPLICAÇÃO PRÁTICA': '#d55181',
      'EXEMPLO CONCRETO': '#9085e9',
      'RESSALVA': '#e66767'
    };
    var bruto = [
      { rotulo: 'ACHADO', texto: f.ach, nome: '', largo: true },
      { rotulo: 'PADRÃO EXTRAÍDO', texto: f.pm || '', nome: f.pn || '', largo: true, condicional: true },
      { rotulo: 'IMPLICAÇÃO PRÁTICA', texto: f.imp, nome: '', largo: false },
      { rotulo: 'EXEMPLO CONCRETO', texto: f.ex, nome: '', largo: false },
      { rotulo: 'RESSALVA', texto: f.res, nome: '', largo: true }
    ];
    return bruto.filter(function (c) { return !c.condicional || c.nome; }).map(function (c) {
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

  /* Cabecalho da decisao: por que o veredito saiu estrito ou amplo, acima dos
     cinco campos da ficha (ou sozinho, quando nao ha ficha). Nao e um sexto
     campo - os cinco falam do paper, este fala da decisao do pipeline - entao
     ele nao usa a regua colorida nem o rotulo espacado de `camposFicha`: uma
     barra lateral na cor do veredito (azul/laranja, `cor()`) e texto em itálico
     o separam visualmente dos cinco.
     `p` precisa de {v, j, h, fr}; `chave` identifica o card para o estado do
     "mais" (aba viva e historica podem ter cards abertos ao mesmo tempo). */
  function cabecalhoDecisao(p, chave) {
    // `v` inalcancavel hoje (fora nunca chega aqui), mas o painel e publicado
    // sozinho as 08:30 pelo launchd - sem essa guarda um dado torto vira
    // TypeError em `toUpperCase()` e a pagina inteira sai em branco.
    if (!p.v) return '';

    var corV = cor(p.v);
    /* A linha do veredito diz por que ele saiu como saiu: "ESTRITO · artefato
       aberto + benchmark". Os criterios saem na ordem canonica do `schemas.py`
       (estrito antes de amplo), nao na ordem em que o Parquet os devolveu. Um
       aprovado de linha antiga nao tem criterio nenhum e a linha volta a ser
       so o veredito - sem separador solto. */
    var criterios = criteriosOrdenados(p.cr).map(rotulo).join(' + ');
    var selo = '';
    if (p.fc) {
      // a contraparte pode ser um criterio ou uma regra de descarte - o mesmo
      // mapa atende as duas, que e a razao de ele ser um so
      selo = '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 10.5px; color: #8b8f96; background: #1d2226; border: 1px solid #2b3138; border-radius: 100px; padding: 3px 9px;">fronteira: quase ' + esc(rotulo(p.fc)) + '</span>';
    } else if (p.fr) {
      // fronteira de linha antiga, gravada antes de a contraparte existir
      selo = '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 10.5px; color: #8b8f96; background: #1d2226; border: 1px solid #2b3138; border-radius: 100px; padding: 3px 9px;">decisão de fronteira</span>';
    }

    var miolo;
    var aviso = avisoDecisao(p.h);
    if (aviso) {
      miolo = '<div style="font-size: 12.5px; font-style: italic; color: #6d7178;">' + aviso + '</div>';
    } else {
      var texto = p.j || '';
      var aberto = !!state.justExp[chave];
      var precisaCortar = texto.length > LIMITE_JUSTIFICATIVA;
      var exibido = (precisaCortar && !aberto) ? rotuloCurto(texto, LIMITE_JUSTIFICATIVA) : texto;
      // classe `mais`: sem ela o unico elemento clicavel do painel sem hover
      // seria este link (todo o resto - `a`, `.chip`, `.aba`, `.row`, `.mark`,
      // `.bar` - tem estado de hover no CSS de gerar_painel.py).
      var botaoMais = precisaCortar
        ? ' <span class="mais" style="font-size: 12px;"' +
          ev('c', function () {
            var m = {};
            for (var k in state.justExp) if (Object.prototype.hasOwnProperty.call(state.justExp, k)) m[k] = state.justExp[k];
            m[chave] = !aberto;
            setState({ justExp: m });
          }) + '>' + (aberto ? 'menos' : 'mais') + '</span>'
        : '';
      miolo = '<div style="font-family: Newsreader, Georgia, serif; font-size: 15px; font-style: italic; font-weight: 300; line-height: 1.62; color: #c9c5bb; text-wrap: pretty;">' + esc(exibido) + botaoMais + '</div>';
    }

    return '<div style="border-left: 2px solid ' + corV + '; padding: 1px 0 1px 16px; margin-bottom: 22px;">' +
      '<div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 8px;">' +
        '<span style="font-size: 11px; font-weight: 600; letter-spacing: 0.14em; color: ' + corV + ';">POR QUE ' + esc(String(p.v).toUpperCase()) + '</span>' +
        (criterios ? '<span style="font-size: 12px; padding: 4px 10px; border-radius: 100px; color: ' + cor(p.v) + '; background: ' + cor(p.v) + '1f; border: 1px solid ' + cor(p.v) + '4d;">' + esc(criterios.toLowerCase()) + '</span>' : '') +
        selo +
      '</div>' +
      miolo +
      '</div>';
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
     ela troca a pergunta que a pagina responde. */
  /* `aprovados` e a contagem do recorte vivo, nao da janela inteira: a nota
     da primeira aba reage aos filtros para dizer quantas linhas a tabela tem
     antes de a pessoa trocar para ela. As duas primeiras abas dividem a barra
     de filtro e o mesmo `state`; a terceira nao passa por filtro nenhum. */
  function navAbas(aprovados) {
    var s = state;
    var itens = [
      { valor: 'aprovados', label: 'Aprovados', nota: aprovados + ' no recorte' },
      { valor: 'panorama', label: 'Panorama', nota: '4 seções' },
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

  /* ══════════════ ABA HISTÓRICA ══════════════

     A aba viva mostra uma janela de dias; esta guarda o que saiu dela. Ela NAO
     preserva dado contra perda - nada e apagado, a serie inteira continua em
     marts/*.parquet e no banco. O que ela resolve e visibilidade: impedir que o
     recorte esconda para sempre o que a comunidade mais votou.

     O ranking de um trimestre congela sozinho, sem passo de "selagem": quando o
     ultimo dia dele cruza o corte, nem entram papers novos no grupo (data_hf_daily
     e imutavel) nem os votos se mexem (o refresh para de re-consultar na mesma
     marca de dias). Ate isso acontecer o trimestre e marcado "em consolidação",
     porque o top-10 dele ainda muda a cada dia que passa. */
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
          'As abas <em style="color: #ecebe6; font-style: normal;">Aprovados</em> e <em style="color: #ecebe6; font-style: normal;">Panorama</em> mostram os últimos ' + DADOS.janela + ' dias. Aqui ficam, de cada trimestre já fora dela, os mais votados pela comunidade — ' +
          'os dez aprovados com a ficha inteira e os dez que o pipeline descartou. ' +
          '<span style="color: #6d7178;">Nada é apagado em lugar nenhum: a série completa continua no banco e nos Parquet. Os votos aqui estão congelados porque o refresh para de reconsultá-los aos ' + (DADOS.diasRefresh || DADOS.diasHall) + ' dias — medido, eles param de se mexer por volta do décimo quarto.</span>' +
        '</div>' +
      '</div>'
    );

    /* ── seletor de trimestre ───────────────────────────────────────────── */
    // `per` e nao `h`: `h` e o registrador global de handlers, e sombrea-lo aqui
    // deixaria a proxima edicao deste callback sem como registrar evento
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
      '<div style="display: flex; align-items: center; gap: 14px; flex-wrap: wrap; margin-bottom: 30px;">' +
        '<span style="font-size: 10px; font-weight: 600; letter-spacing: 0.14em; color: #8b8f96;">PERÍODO</span>' +
        chipsPer +
      '</div>'
    );

    var avisoCons = atual.cons
      ? '<span style="display: inline-flex; align-items: center; gap: 7px; font-size: 11.5px; color: ' + ACCENT + '; background: rgba(217,164,65,0.1); border: 1px solid rgba(217,164,65,0.35); border-radius: 100px; padding: 6px 13px;">' +
          '<span style="display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: ' + ACCENT + ';"></span>' +
          'em consolidação — o trimestre ainda não saiu inteiro do corte</span>'
      : '<span style="font-size: 11.5px; color: #6d7178;">período fechado · ranking definitivo</span>';

    /* ── 01 · os dez aprovados mais votados ─────────────────────────────── */
    out.push(secao('01', 'Os mais votados entre os aprovados'));

    var linhasAp = atual.ap.map(function (p, i) {
      var aberta = s.abertaH === p.id;
      var badge = 'display: inline-flex; align-items: center; justify-content: center; font-size: 10.5px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; padding: 4px 0; border-radius: 100px; color: ' + cor(p.v) + '; background: ' + cor(p.v) + '1f; border: 1px solid ' + cor(p.v) + '4d;';

      var corpo = '';
      if (aberta) {
        corpo = '<div style="padding: 10px 24px 30px;">';
        corpo += cabecalhoDecisao(p, 'hall:' + p.id);
        if (p.f) {
          // ordem normativa da ficha: Achado, Padrao Extraido, Implicacao,
          // Exemplo, Ressalva. O Padrao some quando o achado e puramente empirico.
          corpo += '<div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 24px 40px;">' +
            camposFicha(p).map(function (c) {
              return '<div style="' + c.wrap + '">' +
                '<div style="' + c.regua + '"></div>' +
                '<div style="' + c.rotuloStyle + '">' + c.rotulo + '</div>' +
                '<div style="' + c.nomeStyle + '">' + esc(c.nome) + '</div>' +
                '<div style="font-family: Newsreader, Georgia, serif; font-size: 16px; font-weight: 300; line-height: 1.68; color: #d5d1c8; text-wrap: pretty;">' + esc(c.texto) + '</div>' +
                '</div>';
            }).join('') +
            '</div>';
        } else {
          corpo += '<div style="font-size: 12.5px; color: #6d7178; padding: 6px 0 14px;">Aprovado sem ficha gerada — o Estágio B não chegou a escrevê-la. Ele fica no ranking porque tirá-lo faria o top-10 mentir sobre quem foi mais votado.</div>';
        }
        corpo += '<div style="display: flex; gap: 20px; align-items: center; margin-top: 24px; padding-top: 16px; border-top: 1px solid #242a30;">' +
            '<a href="' + esc(p.url) + '" target="_blank" rel="noopener" style="font-family: \'IBM Plex Mono\', monospace; font-size: 12px;">' + esc(p.id) + ' ↗</a>' +
            '<span style="font-size: 11.5px; color: #6d7178;">' + esc((p.vt || []).join(' · ')) + '</span>' +
            (p.uq ? '<span style="font-size: 11.5px; color: #5f636a;">votos medidos em ' + esc(diaCurto(p.uq)) + '</span>' : '') +
          '</div>' +
          '</div>';
      }

      return '<div style="border-bottom: 1px solid #1d2226;">' +
        '<div class="row"' + ev('c', function () { setState({ abertaH: aberta ? null : p.id }); }) + ' style="display: grid; grid-template-columns: 30px 78px minmax(200px, 1fr) 280px 150px 56px 54px; gap: 14px; padding: 14px 24px; align-items: center;">' +
          '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 12px; color: ' + (i < 3 ? ACCENT : '#4a5058') + ';">' + (i + 1) + '</span>' +
          '<span style="' + badge + '">' + esc(p.v) + '</span>' +
          '<div style="display: flex; flex-direction: column; gap: 3px; min-width: 0;">' +
            '<span style="font-size: 13.5px; color: #ecebe6; line-height: 1.3; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">' + esc(p.t) + '</span>' +
            '<span style="font-size: 11.5px; color: #6d7178; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">' + esc(p.org || '—') + (p.f ? '' : ' · sem ficha') + '</span>' +
          '</div>' +
          '<span style="font-size: 11.5px; color: #8b8f96; line-height: 1.5;">' + esc(parArea(p)) + '</span>' +
          '<span style="font-size: 11.5px; color: #a8a49b; line-height: 1.5;">' + esc((p.vt || []).join(' · ') || '—') + '</span>' +
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
            '<div style="font-size: 12.5px; color: #8b8f96;">' + atual.ap.length + ' de ' + atual.na + ' aprovados, ordenados por voto da comunidade. Clique para abrir o porquê da decisão — e a ficha completa.</div>' +
          '</div>' + avisoCons +
        '</div>' +
        '<div style="display: grid; grid-template-columns: 30px 78px minmax(200px, 1fr) 280px 150px 56px 54px; gap: 14px; padding: 11px 24px; border-top: 1px solid #242a30; border-bottom: 1px solid #242a30; background: #131619; font-size: 10.5px; font-weight: 600; letter-spacing: 0.14em; color: #8b8f96;">' +
          '<span>#</span><span>CRITÉRIO</span><span>TÍTULO</span><span>ÁREA &gt; SUB-ÁREA</span><span>VERTENTE</span><span style="text-align: right;">VOTOS</span><span style="text-align: right;">DIA</span>' +
        '</div>' +
        linhasAp +
        (linhasAp ? '' : '<div style="padding: 54px 24px; text-align: center; font-size: 13px; color: #6d7178;">Nenhum aprovado neste trimestre.</div>') +
      '</div>'
    );

    /* ── 02 · votados e descartados ─────────────────────────────────────── */
    out.push(secao('02', 'Votados pela comunidade, descartados pelo pipeline'));

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
          '<span style="font-size: 11.5px; color: #6d7178; text-align: right; max-width: 300px; line-height: 1.5;">Upvote não entra em decisão nenhuma do pipeline. Esta lista existe para medir a divergência, não para reabrir o veredito.</span>' +
        '</div>' +
        linhasDe +
        (linhasDe ? '' : '<div style="padding: 54px 24px; text-align: center; font-size: 13px; color: #6d7178;">Nenhum descarte neste trimestre.</div>') +
      '</div>'
    );

    var somaAp = 0, somaDe = 0;
    hall.forEach(function (per) { somaAp += per.ap.length; somaDe += per.de.length; });
    out.push(rodape('REGISTRO HISTÓRICO · ' + hall.length + ' TRIMESTRE(S) · ' + somaAp + ' APROVADOS · ' + somaDe + ' DESCARTADOS'));
    return out.join('');
  }

  // a pilula "ligada" tambem e usada pelo seletor de trimestre, que roda fora
  // de construir() - onde a variavel local `pillOn` nao alcanca
  function pillOnGlobal() {
    return 'display: inline-flex; align-items: center; gap: 0; font-size: 12.5px; line-height: 1; padding: 8px 15px; border-radius: 100px; white-space: nowrap; background: ' + ACCENT + '; border: 1px solid ' + ACCENT + '; color: #14161a; font-weight: 600;';
  }

  function construir() {
    var s = state;
    var todos = DADOS.papers;
    var sel = filtrados();
    var total = sel.length;

    /* Um recorte por dimensao, cada um com a SUA solta. E o que faz os
       numeros da barra de filtro descreverem o recorte em vigor em vez da
       janela inteira: marcado `estrito`, o menu de area precisa dizer 7 em
       "Modelo & treino", nao 524.

       A dimensao se solta de si mesma porque senao o menu se apagaria depois
       do primeiro clique - marcada uma area, todas as outras iriam a zero e a
       segunda ficaria inalcancavel. E a mesma razao de `exceto` existir para
       os graficos; aqui ela vale para o proprio seletor. */
    var recDia = filtrados('diasSel');
    var recVeredito = filtrados('vereditos');
    var recArea = filtrados('areas');
    var recSubarea = filtrados('subareas');
    var recVert = filtrados('vertentes');
    var recOrg = filtrados('orgs');

    var conta = { fora: 0, amplo: 0, estrito: 0 };
    sel.forEach(function (p) { if (conta[p.v] !== undefined) conta[p.v]++; });
    var aprovados = conta.amplo + conta.estrito;

    var pillOn = 'display: inline-flex; align-items: center; gap: 0; font-size: 12.5px; line-height: 1; padding: 8px 15px; border-radius: 100px; white-space: nowrap; background: ' + ACCENT + '; border: 1px solid ' + ACCENT + '; color: #14161a; font-weight: 600;';

    var dias = [];
    todos.forEach(function (p) { if (p.d && dias.indexOf(p.d) < 0) dias.push(p.d); });
    dias.sort();

    var comContagem = 'margin-left: 7px; font-family: \'IBM Plex Mono\', monospace; font-size: 11px; opacity: 0.62;';

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
          '<div style="font-family: Newsreader, Georgia, serif; font-size: 17px; font-weight: 300; line-height: 1.55; color: #a8a49b; max-width: 640px; text-wrap: pretty;">Papers do Hugging Face Daily Papers, classificados e resumidos em fichas.</div>' +
        '</div>' +
        '<div style="display: flex; gap: 34px; text-align: right; padding-bottom: 4px;">' +
          '<div style="display: flex; flex-direction: column; gap: 5px;">' +
            '<span style="font-size: 10px; letter-spacing: 0.16em; color: #6d7178;">JANELA</span>' +
            '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 14px; color: #ecebe6;">' +
              esc(dias.length ? diaCurto(dias[0]) + ' – ' + diaCurto(dias[dias.length - 1]) : '—') +
              '<span style="color: #6d7178;"> · ' + DADOS.janela + 'd</span>' +
            '</span>' +
          '</div>' +
          // Morava na aba "Janela", que deixou de existir: a contagem descreve
          // as duas abas filtraveis, entao sobe para o cabecalho, que e de todas.
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

    out.push(navAbas(aprovados));

    /* A aba historica sai aqui. Ela nao passa pela barra de filtro de proposito:
       `filtrados()` recorta DADOS.papers, que e so a janela - deixar o filtro
       de dia/area/organizacao valer para o hall zeraria a aba inteira assim que
       alguem marcasse um dia. O hall tem o seletor de trimestre e nada mais. */
    if (s.aba === 'historico') {
      out.push(construirHall());
      out.push('</div>');
      return out.join('');
    }

    /* ══════════════ FILTROS ══════════════ */
    /* Um recorte por regra do Pareto ja implica `fora`: aprovado nao tem regra
       nenhuma. Sem dizer isso aqui, a linha mostra os tres chips apagados
       enquanto o painel so traz descartados - e clicar em `estrito` zeraria o
       recorte em silencio. O chip nao deixa de ser clicavel; so para de mentir. */
    var regraAtiva = s.regrasFora.length > 0;
    // simetrico: um recorte por criterio ja implica aprovado, porque criterio
    // de veredito so existe para quem passou
    var criterioAtivo = s.criterios.length > 0;
    var chipsVeredito = ['estrito', 'amplo', 'fora'].map(function (v) {
      var on = s.vereditos.indexOf(v) >= 0;
      var n = recVeredito.filter(function (p) { return p.v === v; }).length;
      var implicito = regraAtiva && v === 'fora' && !on;
      var anulado = (regraAtiva && v !== 'fora') || (criterioAtivo && v === 'fora');
      var extra = implicito
        ? ' border-style: dashed; border-color: ' + cor(v) + '; color: ' + corTexto(v) + ';'
        : (anulado ? ' opacity: 0.4;' : '');
      var dica = implicito
        ? ev('e', mostraTip('em vigor pelo filtro de regra', 'Uma regra de descarte só existe para quem saiu: o recorte já está restrito a fora.')) + ev('l', escondeTip())
        : (anulado
          ? ev('e', mostraTip('zeraria o recorte', (regraAtiva
              ? 'O filtro de regra já restringe a descartados; somar ' + v + ' não deixa nenhum paper de pé.'
              : 'O filtro de critério já restringe a aprovados; somar fora não deixa nenhum paper de pé.'))) + ev('l', escondeTip())
          : '');
      return '<div class="' + (on ? 'chip chip-on' : 'chip') + '"' + ev('c', function () { alternaLista('vereditos', v); }) + dica +
        ' style="' + pill(on, cor(v)) + extra + '">' +
        '<span style="display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 8px; background: ' + cor(v) + ';"></span>' + esc(v) +
        '<span style="' + comContagem + '">' + n + '</span>' +
        '</div>';
    }).join('');

    // A LISTA de dias e a janela inteira, em ordem cronologica: dia que zerou
    // continua no menu, com o zero visivel, e a ordem nao depende do recorte.
    var contaDia = {};
    recDia.forEach(function (p) { if (p.d) contaDia[p.d] = (contaDia[p.d] || 0) + 1; });
    // mais recente primeiro: e por onde se comeca a ler o painel
    var itensDia = dias.slice().reverse().map(function (d) {
      return { valor: d, label: diaCurto(d), n: contaDia[d] || 0 };
    });

    // Ordenado pela contagem DO RECORTE, entao o topo do menu e sempre o que
    // existe nele: so entre os estritos, "Avaliacao & instrumentacao" (150)
    // abre a lista e "Geracao de midia" cai para o fim, com zero.
    var contaArea = {};
    recArea.forEach(function (p) { if (p.a) contaArea[p.a] = (contaArea[p.a] || 0) + 1; });
    var itensArea = DADOS.areas.map(function (a) {
      return { valor: a.a, label: a.a, n: contaArea[a.a] || 0 };
    }).sort(function (x, y) { return y.n - x.n || x.label.localeCompare(y.label); });

    // Mesmo vocabulario completo usado nos tooltips, incluindo sub-areas
    // sem papers na janela. A contagem usa o par primario, como o filtro.
    var contaSubarea = {};
    recSubarea.forEach(function (p) { if (p.sa) contaSubarea[p.sa] = (contaSubarea[p.sa] || 0) + 1; });
    var itensSubarea = Object.keys(DADOS.subdef || {}).map(function (sa) {
      return { valor: sa, label: sa, n: contaSubarea[sa] || 0 };
    }).sort(function (x, y) { return y.n - x.n || x.label.localeCompare(y.label); });

    // Contagem por DOMINANTE, o mesmo criterio do filtro. A lista sai de
    // `DADOS.vertentes` e nao das que aparecem no recorte: uma vertente que
    // zerou precisa continuar no menu, com o zero visivel, senao o painel
    // esconde justamente a informacao de que ela zerou.
    var contaVert = {};
    recVert.forEach(function (p) { var k = dominante(p); contaVert[k] = (contaVert[k] || 0) + 1; });
    var itensVert = (DADOS.vertentes || []).map(function (v) {
      return { valor: v.v, label: v.v, n: contaVert[v.v] || 0 };
    }).sort(function (x, y) { return y.n - x.n || x.label.localeCompare(y.label); });
    // A linha do nulo so existe quando ha paper sem vertente no recorte - ou
    // quando ela e o filtro em vigor, que nao pode sumir do proprio menu.
    if (contaVert[VERTENTE_NULA] || s.vertentes.indexOf(VERTENTE_NULA) >= 0) {
      itensVert.push({ valor: VERTENTE_NULA, label: 'sem vertente', n: contaVert[VERTENTE_NULA] || 0 });
    }

    /* Organizacao e a excecao a regra dos zeros. Area, sub-area e vertente
       mantem no menu a linha que zerou, porque ali o zero e informacao de
       grade: diz que aquela celula do vocabulario nao produz estrito nenhum.
       Organizacao nao e vocabulario controlado - sao 564 nomes na janela, dos
       quais 368 zeram assim que o recorte fica so em estrito - e uma lista de
       zeros nao informa nada que a busca do menu ja nao resolva. Some.
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

    var ativos = [];
    if (s.diasSel.length) ativos.push(s.diasSel.length === 1 ? diaCurto(s.diasSel[0]) : s.diasSel.length + ' dias');
    if (s.vereditos.length) ativos.push(s.vereditos.join('+'));
    if (s.areas.length) ativos.push(s.areas.length === 1 ? s.areas[0] : s.areas.length + ' áreas');
    if (s.subareas.length) ativos.push(s.subareas.length === 1 ? s.subareas[0] : s.subareas.length + ' sub-áreas');
    // "dominante": o resumo diz por qual criterio a vertente recorta, porque
    // um paper costuma ter mais de uma e sem isso o numero pareceria errado
    if (s.vertentes.length) ativos.push(s.vertentes.length === 1
      ? (s.vertentes[0] === VERTENTE_NULA ? 'sem vertente' : 'dominante: ' + s.vertentes[0])
      : s.vertentes.length + ' vertentes dominantes');
    // `regrasFora` so entra pelo grafico: sem ele no resumo o recorte ficaria
    // invisivel e o "limpar" pareceria quebrado
    if (s.regrasFora.length) ativos.push(s.regrasFora.length === 1 ? 'regra: ' + rotulo(s.regrasFora[0]) : s.regrasFora.length + ' regras');
    if (s.criterios.length) ativos.push(s.criterios.length === 1 ? 'critério: ' + rotulo(s.criterios[0]) : s.criterios.length + ' critérios');
    if (s.orgs.length) ativos.push(s.orgs.length === 1 ? (s.orgs[0] === '__sem-org__' ? 'sem organização' : s.orgs[0]) : s.orgs.length + ' organizações');
    if (s.busca) ativos.push('"' + s.busca + '"');
    var resumoFiltro = ativos.length ? total + ' de ' + todos.length + ' · ' + ativos.join(' · ') : todos.length + ' papers, sem recorte';

    var estiloLimpar = 'display: inline-flex; align-items: center; gap: 7px; font-size: 12px; padding: 8px 14px; border-radius: 100px; background: ' +
      (ativos.length ? 'rgba(217,164,65,0.12)' : '#1b1f23') + '; border: 1px solid ' + (ativos.length ? 'rgba(217,164,65,0.5)' : '#2b3138') +
      '; color: ' + (ativos.length ? ACCENT : '#6d7178') + ';';

    // z-index 90 na linha do menu aberto: sem isso a cortina de fechar (80)
    // ficaria por cima do proprio menu e nenhum item seria clicavel.
    var zDia = s.menu === 'diasSel' ? 90 : 4;
    // Os tres menus dividem a linha TEMA, entao ela sobe se qualquer um abrir.
    var zTema = (s.menu === 'areas' || s.menu === 'subareas' || s.menu === 'vertentes') ? 90 : 2;
    var zOrg = s.menu === 'orgs' ? 90 : 1;

    out.push(
      '<div class="card" style="margin: 24px 0 30px; padding: 20px 22px 22px; display: flex; flex-direction: column; gap: 15px;">' +
        '<div style="display: flex; align-items: center; justify-content: space-between; gap: 20px;">' +
          '<div style="display: flex; align-items: center; gap: 10px;">' +
            '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#767a80" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5h16l-6.5 7.5V19l-3 1.5v-8L4 5z"></path></svg>' +
            '<span style="font-size: 11px; font-weight: 600; letter-spacing: 0.16em; text-transform: uppercase; color: #a8a49b;">Recorte</span>' +
            '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 12px; color: #6d7178;">' + esc(resumoFiltro) + '</span>' +
          '</div>' +
          '<div style="display: flex; align-items: center; gap: 14px;">' +
            '<div style="position: relative; display: flex; align-items: center;">' +
              '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#6d7178" stroke-width="1.7" stroke-linecap="round" style="position: absolute; left: 13px;"><circle cx="11" cy="11" r="6.5"></circle><path d="M16 16l4.5 4.5"></path></svg>' +
              '<input id="q-principal" class="busca" type="text" value="' + esc(s.busca) + '"' +
                ev('i', function (e) { setState({ busca: e.target.value, aberta: null, justExp: {} }); }) +
                ' placeholder="buscar título ou organização" style="font-family: \'Instrument Sans\', sans-serif; font-size: 13px; padding: 9px 14px 9px 36px; width: 268px; border: 1px solid #2b3138; border-radius: 100px; background: #1b1f23; color: #ecebe6; outline: none;">' +
            '</div>' +
            '<div class="chip"' + ev('c', function () { setState({ diasSel: [], vereditos: [], areas: [], subareas: [], vertentes: [], regrasFora: [], criterios: [], orgs: [], busca: '', aberta: null, menu: null, buscaMenu: '', justExp: {} }); }) + ' style="' + estiloLimpar + '">' +
              '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"></path></svg><span>limpar</span>' +
            '</div>' +
          '</div>' +
        '</div>' +
        '<div style="height: 1px; background: #242a30;"></div>' +
        linhaFiltro('DIA', zDia, montaMenu('DIA', 'diasSel', itensDia, { todos: 'todos os dias' })) +
        '<div style="display: grid; grid-template-columns: 74px minmax(0, 1fr); gap: 16px; align-items: start; position: relative; z-index: 3;">' +
          '<div style="font-size: 10px; font-weight: 600; letter-spacing: 0.14em; color: #8b8f96; padding-top: 9px;">VEREDITO</div>' +
          '<div style="display: flex; gap: 7px; flex-wrap: wrap; align-items: center;">' + chipsVeredito +
            (regraAtiva
              // a nota vem um tom abaixo do resto para o nome do veredito
              // subir: em #8b8f96 nos dois, o realce de `fora` era um no-op
              ? '<span style="font-size: 11.5px; color: #6d7178;">restrito a <span style="color: ' + corTexto('fora') + ';">fora</span> pelo filtro de regra</span>'
              : (criterioAtivo
                ? '<span style="font-size: 11.5px; color: #6d7178;">restrito a <span style="color: ' + VERDE + ';">aprovados</span> pelo filtro de critério</span>'
                : '')) +
            /* Os pendentes nao estao em `DADOS.papers` (ver gerar_painel.py):
               nunca classificado nao e `fora`. Mas some-los da pagina sem
               dizer faria a soma dos tres chips nao bater com o total do dia
               na aba - entao a conta aparece aqui, ao lado dos vereditos que
               ela NAO integra. */
            (DADOS.pendentes
              ? '<span' + ev('e', mostraTip('Ainda sem veredito',
                  'O refresh grava paper novo depois que a classificação já passou; ele entra na próxima rodada. Fica fora das contagens de veredito porque nunca classificado não é o mesmo que fora.')) +
                  ev('l', escondeTip()) +
                  ' style="font-size: 11.5px; color: #6d7178; border-bottom: 1px dotted #3a4048; cursor: help;">+' +
                  DADOS.pendentes + ' na fila, sem veredito</span>'
              : '') +
          '</div>' +
        '</div>' +
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
       abaixo e exclusivo de cada uma: Panorama traz os tiles e as secoes 01 a
       04; Aprovados traz a tabela. Os blocos ficam em `if` sem reindentar
       porque o conteudo nao mudou - so a aba em que ele aparece. */
    if (s.aba === 'panorama') {

    /* ══════════════ STAT TILES ══════════════ */
    var comFicha = sel.filter(function (p) { return p.f; }).length;
    var comCodigo = sel.filter(function (p) { return p.oa; }).length;
    function marca(c) { return 'display: inline-block; width: 5px; height: 5px; border-radius: 50%; background: ' + c + ';'; }
    var tiles = [
      { rotulo: 'papers no recorte', valor: total, sufixo: 'de ' + todos.length, cor: '#f5f3ee', marca: marca('#4a5058'), nota: dias.length + ' dias de publicação cobertos' },
      // o numero e a marca em verde, nao no azul de estrito: o tile conta
      // estrito MAIS amplo, e pinta-lo com a cor de um dos dois dizia que a
      // metade laranja da conta nao estava ali. A decomposicao continua na nota
      // de baixo, onde cada veredito aparece pelo nome.
      { rotulo: 'aprovados', valor: aprovados, sufixo: pct(aprovados, total) + '%', cor: VERDE, marca: marca(VERDE), nota: conta.estrito + ' estrito · ' + conta.amplo + ' amplo' },
      { rotulo: 'fichas escritas', valor: comFicha, sufixo: 'de ' + aprovados, cor: '#f5f3ee', marca: marca('#d9a441'), nota: 'achado, padrão, implicação, exemplo, ressalva' },
      { rotulo: 'com repositório', valor: comCodigo, sufixo: pct(comCodigo, total) + '%', cor: '#f5f3ee', marca: marca('#4a5058'), nota: 'derivado de githubRepo não nulo' }
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

    /* ══════════════ 01 · VOLUME E RECÊNCIA ══════════════ */
    out.push(secao('01', 'Volume e seletividade'));

    var nCol = Math.max(1, dias.length);
    var porDia = {};
    dias.forEach(function (d) { porDia[d] = { fora: 0, amplo: 0, estrito: 0, total: 0 }; });
    sel.forEach(function (p) { if (porDia[p.d]) { porDia[p.d][p.v]++; porDia[p.d].total++; } });
    var maxDia = Math.max.apply(null, dias.map(function (d) { return porDia[d].total; }).concat([1]));

    var legenda = ['estrito', 'amplo', 'fora'].map(function (v) {
      return '<div style="display: flex; align-items: center; gap: 6px; font-size: 11.5px; color: #a8a49b; white-space: nowrap;">' +
        '<span style="display: inline-block; width: 8px; height: 8px; border-radius: 2px; background: ' + cor(v) + ';"></span>' + v + '</div>';
    }).join('');

    /* Sem fresta entre as colunas (`gap: 0`, largura interna na barra): o painel
       da taxa fica exatamente sobre o de volume porque os dois derivam a
       posicao da mesma coluna de `flex: 1`. Com `gap` em px o centro da coluna
       i sai do centro percentual em ate meia fresta, e o ponto da taxa deixaria
       de cair sobre a barra do proprio dia - que e a unica razao de os dois
       paineis existirem alinhados em vez de num eixo duplo. */
    var barrasDia = dias.map(function (d) {
      var c = porDia[d];
      var segs = ['fora', 'amplo', 'estrito'].filter(function (v) { return c[v] > 0; }).map(function (v) {
        return '<div style="flex: ' + c[v] + '; background: ' + cor(v) + '; min-height: 3px; border-radius: 1px;"></div>';
      }).join('');
      return '<div style="flex: 1; display: flex; flex-direction: column; align-items: center; gap: 8px; height: 100%; justify-content: flex-end;">' +
        '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 12px; color: #a8a49b;">' + c.total + '</span>' +
        '<div class="bar"' +
          ev('e', mostraTip(diaCurto(d) + ' · ' + c.total + ' papers', c.estrito + ' estrito · ' + c.amplo + ' amplo · ' + c.fora + ' fora')) +
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
      return { d: d, c: c, ap: c.estrito + c.amplo, tot: c.total, x: ((idxDia[d] + 0.5) / nCol) * 100 };
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
    // com poucas datas a media movel de cinco dias e quase a serie inteira -
    // ela viraria uma segunda linha dizendo o mesmo, entao some e o ponto do
    // dia cresce para assumir a leitura
    var mostraMM = serieTaxa.length >= 8;
    var raioPonto = mostraMM ? 5 : 7;

    function ptsTaxa(campo) {
      return serieTaxa.map(function (r) { return [r.x, 100 - r[campo] * 100]; });
    }
    var gradeTaxa = [0, 25, 50, 75, 100].map(function (g) {
      return '<line x1="0" y1="' + g + '" x2="100" y2="' + g + '" stroke="' + (g === 50 ? '#242a30' : '#1d2226') + '" stroke-width="1" vector-effect="non-scaling-stroke"></line>';
    }).join('');
    var desenhoTaxa = gradeTaxa;
    if (s.taxaDecomp) {
      desenhoTaxa += poliLinha(serieTaxa.map(function (r) { return [r.x, 100 - (r.c.estrito / r.tot) * 100]; }), cor('estrito'), 1.2, '3 3');
      desenhoTaxa += poliLinha(serieTaxa.map(function (r) { return [r.x, 100 - (r.c.amplo / r.tot) * 100]; }), cor('amplo'), 1.2, '3 3');
    }
    if (mostraMM) desenhoTaxa += poliLinha(ptsTaxa('mm'), '#6d7178', 1.4, '5 4');
    desenhoTaxa += poliLinha(ptsTaxa('taxa'), VERDE, 2, null);

    var celulasTaxa = dias.map(function (d) {
      var c = porDia[d];
      var r = null;
      serieTaxa.forEach(function (x) { if (x.d === d) r = x; });
      var ponto = r
        ? '<span style="position: absolute; left: 50%; bottom: ' + (r.taxa * 100) + '%; width: ' + raioPonto + 'px; height: ' + raioPonto + 'px; margin-left: -' + (raioPonto / 2) + 'px; margin-bottom: -' + (raioPonto / 2) + 'px; border-radius: 50%; background: ' + VERDE + '; border: 1px solid #0d0f11;"></span>'
        : '';
      var l2 = r
        ? c.total + ' papers · ' + c.estrito + ' estrito (' + pct(c.estrito, c.total) + '%) · ' + c.amplo + ' amplo (' + pct(c.amplo, c.total) + '%) · ' + c.fora + ' fora'
        : 'nenhum paper neste recorte';
      return '<div' +
        ev('e', mostraTip(diaCurto(d) + ' · ' + (r ? pct(r.ap, r.tot) + '% aprovado' : 'sem dado'), l2)) +
        ev('l', escondeTip()) +
        ' style="flex: 1; position: relative; height: 100%; cursor: pointer;">' + ponto + '</div>';
    }).join('');

    /* Mesma ancoragem dos eixos da maturacao e da dispersao: cada rotulo
       centrado no proprio valor. Com `space-between` o 100% encostava o topo
       do texto em y=0 e o 0% o rodape em y=104 - meia linha de erro em cada
       extremo, e so o 50% caia no lugar certo. */
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
        '<div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 18px;">' +
          '<div style="display: flex; flex-direction: column; gap: 5px;">' +
            '<div style="font-family: Newsreader, Georgia, serif; font-size: 26px; font-weight: 400; line-height: 1.1; color: #f5f3ee;">O lote diário e o que sobrou dele</div>' +
            '<div style="font-size: 12.5px; color: #8b8f96;">Papers por dia de publicação no HF, empilhados por veredito.</div>' +
          '</div>' +
          '<div style="display: flex; gap: 15px; padding-top: 5px;">' + legenda + '</div>' +
        '</div>' +
        '<div style="' + gutter + '"><div></div>' +
          '<div style="display: flex; align-items: flex-end; gap: 0; height: 200px; border-bottom: 1px solid #333a41;">' + barrasDia + '</div>' +
        '</div>' +
        '<div style="display: flex; justify-content: space-between; align-items: flex-end; gap: 18px; padding-top: 4px; border-top: 1px solid #242a30;">' +
          '<div style="display: flex; flex-direction: column; gap: 4px; padding-top: 14px;">' +
            '<div style="font-size: 13.5px; color: #ecebe6;">Taxa de aprovação ao longo do tempo</div>' +
            '<div style="font-size: 12px; color: #8b8f96;">(estrito + amplo) ÷ total do dia. Mede seletividade do pipeline — não qualidade nem acurácia.</div>' +
          '</div>' +
          '<div style="display: flex; align-items: center; gap: 14px;">' +
            '<div style="display: flex; gap: 13px;">' + legendaTaxa + '</div>' +
            chipVista('decompor', s.taxaDecomp, function () { setState({ taxaDecomp: !s.taxaDecomp }); }) +
          '</div>' +
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

    /* ══════════════ 02 · VOCABULÁRIO DA GRADE ══════════════ */
    out.push(secao('02', 'Vocabulário da grade'));

    /* Um recorte para as tres vistas, e por isso a ordem das barras e a mesma
       nas tres: o alternador troca o QUE cada barra decompoe, nunca quais
       barras existem nem em que ordem. Sem isso o clique em "Sub-áreas"
       reembaralharia as linhas e o leitor perderia o lugar.

       So `areas` sai do recorte, e pelo motivo de sempre: as barras SAO o
       seletor de area, entao marcar uma apagaria as outras nove. `vertentes`
       fica dentro: quem marcar uma vertente no menu quer ver a barra encolher,
       nao ver o grafico ignorar o proprio filtro - o menu da barra de recorte
       nao e um seletor deste card. */
    var selArea = filtrados('areas');
    var areaMap = {};
    var semArea = 0;
    selArea.forEach(function (p) {
      if (!p.a) { semArea++; return; }
      if (!areaMap[p.a]) areaMap[p.a] = { fora: 0, amplo: 0, estrito: 0, total: 0, sub: {} };
      var c = areaMap[p.a];
      c[p.v]++; c.total++;
      if (p.sa) c.sub[p.sa] = (c.sub[p.sa] || 0) + 1;
    });
    // desempate alfabetico: `painel.html` e commitado todo dia e duas areas
    // empatadas em volume trocariam de lugar entre rodadas sem significar nada
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

    /* ── vista Distribuição: largura absoluta, empilhada por veredito ─────── */
    var barrasArea = areasOrd.map(function (a) {
      var c = areaMap[a];
      var on = s.areas.indexOf(a) >= 0;
      var segs = ['estrito', 'amplo', 'fora'].filter(function (v) { return c[v] > 0; }).map(function (v) {
        return '<div class="bar" style="flex: ' + c[v] + '; background: ' + cor(v) + ';"></div>';
      }).join('');
      return '<div' + ev('c', function () { alternaLista('areas', a); }) +
        ev('e', mostraTip(a, defArea[a] || '', c.estrito + ' estrito · ' + c.amplo + ' amplo · ' + c.fora + ' fora')) +
        ev('l', escondeTip()) +
        ' style="display: flex; flex-direction: column; gap: 6px; cursor: pointer;">' +
        '<div style="display: flex; justify-content: space-between; align-items: baseline; gap: 12px;">' +
          '<span style="font-size: 13.5px; color: ' + (on ? ACCENT : '#ecebe6') + '; font-weight: ' + (on ? '600' : '400') + '; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">' + esc(a) + '</span>' +
          '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 11.5px; color: #8b8f96; white-space: nowrap;">' + c.total + ' · ' + pct(c.estrito + c.amplo, c.total) + '% aprovado</span>' +
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
      dist: 'A LLM escolhe de uma lista fechada — nunca inventa rótulo. Clique para filtrar.',
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

    /* ══════════════ 03 · REGRAS DO CORTE ══════════════ */
    out.push(secao('03', 'Regras do corte'));

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

    var linhasPareto = regrasOrd.map(function (k) {
      var n = contaRegra[k];
      var parte = totalDesc ? (n / totalDesc) * 100 : 0;
      var on = s.regrasFora.indexOf(k) >= 0;
      var nulo = k === REGRA_NULA;
      // O preenchimento conserva a identidade do veredito, inclusive ao filtrar.
      var corBarra = cor('fora');
      return '<div' +
        ev('c', function () { alternaLista('regrasFora', k); }) +
        ev('e', mostraTip(rotulo(k), n + ' descartes · ' + parte.toFixed(1) + '% dos descartados')) +
        ev('l', escondeTip()) +
        ' style="display: flex; flex-direction: column; gap: 6px; padding-bottom: 12px; cursor: pointer;">' +
        // o rotulo agora ocupa a linha inteira: a metade direita pertencia a
        // curva do acumulado, que saiu (com seis regras ela era decorativa e
        // o numero dela nao era legivel sobre as barras)
        '<div style="display: flex; align-items: baseline; justify-content: space-between; flex-wrap: wrap; gap: 6px;">' +
          '<span style="font-size: 13px; color: ' + (on ? ACCENT : (nulo ? '#8b8f96' : '#ecebe6')) + '; font-weight: ' + (on ? '600' : '400') + '; font-style: ' + (nulo ? 'italic' : 'normal') + '; line-height: 1.45;">' + esc(rotulo(k)) + '</span>' +
          '<span style="flex: none; font-family: \'IBM Plex Mono\', monospace; font-size: 11.5px; color: #8b8f96; white-space: nowrap;">' +
            n + ' <span style="color: #5f636a;">· ' + parte.toFixed(1) + '% dos descartados</span></span>' +
        '</div>' +
        '<div style="height: 13px; background: #1d2226; border-radius: 2px; overflow: hidden;">' +
          '<div class="bar" style="height: 100%; width: ' + ((n / maxRegra) * 100) + '%; min-width: 2px; background: ' + corBarra + '; border-radius: 2px;"></div>' +
        '</div>' +
        '</div>';
    }).join('');

    var cardCorte = (
      '<div class="card" style="padding: 22px 24px 20px; margin-bottom: 14px; display: flex; flex-direction: column; gap: 18px;">' +
        '<div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 12px;">' +
          '<div style="display: flex; flex-direction: column; gap: 5px; max-width: 720px;">' +
            '<div style="font-family: Newsreader, Georgia, serif; font-size: 26px; font-weight: 400; line-height: 1.1; color: #f5f3ee;">Onde o pipeline corta</div>' +
            '<div style="font-size: 12.5px; color: #8b8f96;">Motivos de descarte, do mais frequente ao menos frequente. Clique para filtrar.</div>' +
            '<div class="voto-legenda"><span style="background: ' + cor('fora') + ';"></span>fora · papers descartados</div>' +
          '</div>' +
        '</div>' +
        (linhasPareto
          ? '<div class="regras-scroll" tabindex="0" aria-label="Regras de descarte">' + linhasPareto + '</div>'
          : '<div style="padding: 44px 0; text-align: center; font-size: 12.5px; color: #6d7178;">Nenhum descarte dentro deste recorte.</div>') +
      '</div>'
    );

    /* Critérios registrados, decompostos pelo veredito final do paper. */
    var selCrit = filtrados('criterios');
    var aprovadosCrit = selCrit.filter(function (p) { return p.v !== 'fora'; });
    var contaCrit = {};
    aprovadosCrit.forEach(function (p) {
      var lista = p.cr || [];
      var vistos = {};
      lista.forEach(function (k) {
        if (vistos[k]) return;
        vistos[k] = 1;
        if (!contaCrit[k]) contaCrit[k] = { estrito: 0, amplo: 0, total: 0 };
        if (p.v === 'estrito') contaCrit[k].estrito++; else contaCrit[k].amplo++;
        contaCrit[k].total++;
      });
    });
    var maxCrit = 1;
    for (var kk in contaCrit) {
      if (Object.prototype.hasOwnProperty.call(contaCrit, kk) && contaCrit[kk].total > maxCrit) maxCrit = contaCrit[kk].total;
    }
    function barraCriterio(k) {
      var c = contaCrit[k];
      var on = s.criterios.indexOf(k) >= 0;
      var partes = [
        { v: 'estrito', n: c.estrito, cor: cor('estrito') },
        { v: 'amplo', n: c.amplo, cor: cor('amplo') }
      ].filter(function (x) { return x.n > 0; });
      var detalhe = partes.map(function (x) { return x.n + ' ' + x.v; }).join(' · ');
      return '<div' +
        ev('c', function () { alternaLista('criterios', k); }) +
        ev('e', mostraTip(rotulo(k), c.total + ' aprovado(s) por este critério · ' + detalhe)) +
        ev('l', escondeTip()) +
        ' style="display: flex; flex-direction: column; gap: 6px; padding-bottom: 12px; cursor: pointer;">' +
        '<div style="display: flex; align-items: baseline; justify-content: space-between; flex-wrap: wrap; gap: 6px;">' +
          '<span style="font-size: 13px; color: ' + (on ? ACCENT : '#ecebe6') + '; font-weight: ' + (on ? '600' : '400') + '; line-height: 1.45;">' + esc(rotulo(k)) + '</span>' +
          '<span style="flex: none; font-family: \'IBM Plex Mono\', monospace; font-size: 11.5px; color: #8b8f96; white-space: nowrap;">' +
            c.total + ' <span style="color: #5f636a;">· ' + esc(detalhe) + '</span></span>' +
        '</div>' +
        // a fresta de 2px entre os segmentos e na cor do fundo da barra, nao um
        // contorno: e o separador que a skill dataviz pede para empilhamento
        '<div style="height: 13px; background: #1d2226; border-radius: 2px; overflow: hidden;">' +
          '<div style="display: flex; gap: 2px; height: 100%; width: ' + ((c.total / maxCrit) * 100) + '%; min-width: 2px;">' +
            partes.map(function (x) {
              return '<div class="bar" style="flex: ' + x.n + '; background: ' + x.cor + '; border-radius: 2px;"></div>';
            }).join('') +
          '</div>' +
        '</div>' +
        '</div>';
    }

    var barrasCriterio = Object.keys(contaCrit).sort(function (a, b) {
      return contaCrit[b].total - contaCrit[a].total || ordemCriterio(a) - ordemCriterio(b);
    }).map(barraCriterio).join('');

    var legendaCriterio = ['estrito', 'amplo'].map(function (v) {
      return '<div style="display: flex; align-items: center; gap: 6px; font-size: 11.5px; color: #a8a49b; white-space: nowrap;">' +
        '<span style="display: inline-block; width: 8px; height: 8px; border-radius: 2px; background: ' +
        cor(v) + ';"></span>' + v + '</div>';
    }).join('');

    out.push('<div class="regras-grid">');
    out.push(
      '<div class="card" style="padding: 22px 24px 20px; margin-bottom: 34px; display: flex; flex-direction: column; gap: 18px;">' +
        '<div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 12px;">' +
          '<div style="display: flex; flex-direction: column; gap: 5px; max-width: 720px;">' +
            '<div style="font-family: Newsreader, Georgia, serif; font-size: 26px; font-weight: 400; line-height: 1.1; color: #f5f3ee;">Por que o pipeline aprova</div>' +
            '<div style="font-size: 12.5px; color: #8b8f96;">Critérios presentes nos aprovados, separados pelo veredito final. Um paper pode aparecer em mais de um critério. Clique para filtrar.</div>' +
          '</div>' +
          '<div style="display: flex; gap: 15px; padding-top: 5px;">' + legendaCriterio + '</div>' +
        '</div>' +
        (barrasCriterio
          ? '<div class="regras-scroll" tabindex="0" aria-label="Critérios de veredito">' + barrasCriterio + '</div>'
          : '<div style="padding: 44px 0; text-align: center; font-size: 12.5px; color: #6d7178;">Nenhum aprovado deste recorte tem critério de veredito registrado.</div>') +
      '</div>'
    );

    out.push(cardCorte, '</div>');

    /* ══════════════ 04 · ATENÇÃO E ADOÇÃO ══════════════ */
    out.push(secao('04', 'Atenção e adoção'));

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
        ev('e', mostraTip(r.p.t, '+' + r.delta + ' votos · ' + r.de[1] + ' → ' + r.ate[1] + ' · ' + intervalo + ' · ' + r.p.v)) + ev('l', escondeTip()) +
        '><div class="voto-item-miolo"><div class="voto-item-cab">' + esc(r.p.t) + '</div>' +
        '<div class="voto-tracao" aria-hidden="true">' +
          '<span class="voto-tracao-linha" style="left: ' + xInicio + '%; width: ' + (xFim - xInicio) + '%; background: ' + cor(r.p.v) + ';"></span>' +
          '<span class="voto-tracao-inicio" style="left: ' + xInicio + '%; border-color: ' + cor(r.p.v) + ';"></span>' +
          '<span class="voto-tracao-fim" style="left: ' + xFim + '%; background: ' + cor(r.p.v) + ';"></span>' +
        '</div><div class="voto-item-detalhe">' + r.de[1] + ' → ' + r.ate[1] + ' votos · ' + intervalo + '</div></div>' +
        '<b class="voto-item-ganho">+' + r.delta + '</b></a>';
    }).join('');
    var legendaVotos = ['estrito', 'amplo', 'fora'].map(function (v) {
      return '<span style="background: ' + cor(v) + ';"></span>' + v;
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
    // rotulo permanente so nos extremos: os tres mais votados e os tres mais
    // estrelados. Rotular tudo cobriria a nuvem inteira de texto.
    var rotulados = {};
    comRepo.slice().sort(function (a, b) { return b.u - a.u; }).slice(0, 3).forEach(function (p) { rotulados[p.id] = 1; });
    comRepo.slice().sort(function (a, b) { return b.gs - a.gs; }).slice(0, 3).forEach(function (p) { rotulados[p.id] = 1; });

    var pontosGh = comRepo.map(function (p) {
      var x = escalaLog(p.u, maxU), y = escalaLog(p.gs, maxG);
      var forma = p.pp
        ? 'width: 9px; height: 9px; margin-left: -4.5px; margin-bottom: -4.5px; transform: rotate(45deg); border-radius: 1px;'
        : 'width: 8px; height: 8px; margin-left: -4px; margin-bottom: -4px; border-radius: 50%;';
      // outlier perto da borda direita ganha o rotulo a esquerda do ponto:
      // ancorado sempre a direita, o titulo do paper mais votado sairia do card
      var aDireita = x > 62;
      var rot = rotulados[p.id]
        ? '<span style="position: absolute; ' +
          (aDireita ? 'right: ' + (100 - x) + '%; margin-right: 9px; text-align: right;' : 'left: ' + x + '%; margin-left: 9px;') +
          ' bottom: ' + y + '%; margin-bottom: -6px; font-size: 10.5px; color: #8b8f96; white-space: nowrap; pointer-events: none;">' + esc(rotuloCurto(p.t, 34)) + '</span>'
        : '';
      return '<a class="mark" href="' + esc(p.url) + '" target="_blank" rel="noopener"' +
        ev('e', mostraTip(p.t, p.u + ' votos · ' + p.gs + ' stars · ' + p.c + ' comentários · ' + p.v + ' · ' + (p.a ? parArea(p) : 'sem área') + ' · ' + (p.org || 'sem organização') +
          (hojeNum !== null && diaNum(p.d) !== null ? ' · ' + (hojeNum - diaNum(p.d)) + 'd no HF' : ''))) +
        ev('l', escondeTip()) +
        ' style="position: absolute; left: ' + x + '%; bottom: ' + y + '%; ' + forma +
        ' background: ' + cor(p.v) + '; opacity: 0.78; border-bottom: none;"></a>' + rot;
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

    var legendaGh = '<div style="display: flex; gap: 15px; flex-wrap: wrap;">' +
      ['', 'estrito', 'amplo', 'fora'].map(function (v) {
        return '<button type="button" class="chip" aria-pressed="' + (s.ghVeredito === v) + '"' + ev('c', function () { setState({ ghVeredito: v }); }) +
          ' style="' + (s.ghVeredito === v ? pillOnGlobal() : pill(false)) + ' font: inherit; font-size: 11.5px; padding: 6px 12px;">' +
          (v ? '<span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; background: ' + cor(v) + ';"></span>' : '') + (v || 'todos') + '</button>';
      }).join('') +
      '<div style="display: flex; align-items: center; gap: 6px; font-size: 11.5px; color: #a8a49b;">' +
        '<span style="display: inline-block; width: 8px; height: 8px; border: 1px solid #f5f3ee; background: transparent; transform: rotate(45deg);"></span>com página do projeto</div>' +
      '</div>';

    out.push(
      '<div class="card" style="padding: 22px 24px 20px; margin-bottom: 34px; display: flex; flex-direction: column; gap: 16px;">' +
        '<div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 18px;">' +
          '<div style="display: flex; flex-direction: column; gap: 5px; max-width: 700px;">' +
            '<div style="font-family: Newsreader, Georgia, serif; font-size: 26px; font-weight: 400; line-height: 1.1; color: #f5f3ee;">Upvotes no HF × stars no GitHub</div>' +
            '<div style="font-size: 12.5px; color: #8b8f96;">Um ponto por paper com repositório, nas duas escalas logarítmicas. ' +
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
          : '<div style="padding: 76px 0; text-align: center; font-size: 12.5px; color: #6d7178;">Nenhum paper com repositório dentro deste recorte — a dispersão precisa de <span style="font-family: \'IBM Plex Mono\', monospace;">tem_codigo_aberto</span> para existir.</div>') +
      '</div>'
    );

    }  // fim da aba Panorama

    /* ══════════════ APROVADOS · TABELA ══════════════ */
    if (s.aba === 'aprovados') {

    var fichaPorId = {};
    DADOS.fichas.forEach(function (f) { fichaPorId[f.p] = f; });
    // Antes so entrava quem tinha ficha; com o cabecalho da decisao todo
    // aprovado tem conteudo para mostrar, mesmo sem ficha (o Estagio B pode
    // falhar depois de emitir o veredito) - a defesa continua existindo, so
    // que agora ela mostra em vez de esconder.
    var aprovadosCard = sel.filter(function (p) { return p.v !== 'fora'; });
    if (s.ordem === 'votos') aprovadosCard.sort(function (a, b) { return b.u - a.u; });
    else if (s.ordem === 'dia') aprovadosCard.sort(function (a, b) { return (b.d || '').localeCompare(a.d || ''); });
    else aprovadosCard.sort(function (a, b) { return a.t.localeCompare(b.t); });

    var pagina = 10;
    var limite = pagina * (1 + s.maisAprovados);
    var linhasFicha = aprovadosCard.slice(0, limite).map(function (p) {
      var f = fichaPorId[p.id];
      var aberta = s.aberta === p.id;
      var badge = 'display: inline-flex; align-items: center; justify-content: center; font-size: 10.5px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; padding: 4px 0; border-radius: 100px; color: ' + cor(p.v) + '; background: ' + cor(p.v) + '1f; border: 1px solid ' + cor(p.v) + '4d;';

      var corpo = '';
      if (aberta) {
        corpo = '<div style="padding: 10px 24px 30px;">' + cabecalhoDecisao(p, 'jan:' + p.id);
        if (f) {
          // ordem normativa da ficha: Achado, Padrao Extraido, Implicacao,
          // Exemplo, Ressalva. O Padrao some quando o achado e puramente empirico.
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
        corpo += '<div style="display: flex; gap: 20px; align-items: center; margin-top: 24px; padding-top: 16px; border-top: 1px solid #242a30;">' +
            '<a href="' + esc(p.url) + '" target="_blank" rel="noopener" style="font-family: \'IBM Plex Mono\', monospace; font-size: 12px;">' + esc(p.id) + ' ↗</a>' +
            '<span style="font-size: 11.5px; color: #6d7178;">' + esc((p.vt || []).join(' · ')) + '</span>' +
          '</div>' +
          '</div>';
      }

      return '<div style="border-bottom: 1px solid #1d2226;">' +
        '<div class="row"' + ev('c', function () { setState({ aberta: aberta ? null : p.id }); }) + ' style="display: grid; grid-template-columns: 78px minmax(200px, 1fr) 280px 150px 56px 54px; gap: 14px; padding: 14px 24px; align-items: center;">' +
          '<span style="' + badge + '">' + esc(p.v) + '</span>' +
          '<div style="display: flex; flex-direction: column; gap: 3px; min-width: 0;">' +
            '<span style="font-size: 13.5px; color: #ecebe6; line-height: 1.3; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">' + esc(p.t) + '</span>' +
            '<span style="font-size: 11.5px; color: #6d7178; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">' + esc(p.org || '—') + (p.f ? '' : ' · sem ficha') + '</span>' +
          '</div>' +
          '<span style="font-size: 11.5px; color: #8b8f96; line-height: 1.5;">' + esc(parArea(p)) + '</span>' +
          '<span style="font-size: 11.5px; color: #a8a49b; line-height: 1.5;">' + esc((p.vt || []).join(' · ') || '—') + '</span>' +
          '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 12.5px; color: #ecebe6; text-align: right;">' + p.u + '</span>' +
          '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 11.5px; color: #6d7178; text-align: right;">' + diaCurto(p.d) + '</span>' +
        '</div>' + corpo +
        '</div>';
    }).join('');

    var chipsOrdem = [
      { label: 'dia', valor: 'dia' }, { label: 'votos', valor: 'votos' }, { label: 'título', valor: 'titulo' }
    ].map(function (c) {
      var on = s.ordem === c.valor;
      var menor = ' font-size: 11.5px; padding: 6px 12px;';
      return '<div class="' + (on ? 'chip chip-on' : 'chip') + '"' + ev('c', function () { setState({ ordem: c.valor }); }) +
        ' style="' + (on ? pillOn : pill(false)) + menor + '">' + c.label + '</div>';
    }).join('');

    // "mostrar mais" abre mais uma pagina; "todos" abre o resto de uma vez;
    // "recolher" volta a primeira pagina. Os tres so aparecem quando ha o que
    // abrir ou fechar - com 10 aprovados ou menos o rodape e so a contagem.
    var chipMenor = ' font-size: 11.5px; padding: 6px 12px;';
    var rodapeMais = '';
    if (aprovadosCard.length > limite) {
      var restam = aprovadosCard.length - limite;
      rodapeMais +=
        '<div class="chip"' + ev('c', function () { setState({ maisAprovados: s.maisAprovados + 1 }); }) +
          ' style="' + pill(false) + chipMenor + '">mostrar mais ' + Math.min(pagina, restam) + '</div>';
      if (restam > pagina) {
        rodapeMais +=
          '<div class="chip"' + ev('c', function () { setState({ maisAprovados: Math.ceil(aprovadosCard.length / pagina) - 1 }); }) +
            ' style="' + pill(false) + chipMenor + '">todos os ' + aprovadosCard.length + '</div>';
      }
    }
    if (s.maisAprovados > 0 && aprovadosCard.length > pagina) {
      rodapeMais +=
        '<div class="chip"' + ev('c', function () { setState({ maisAprovados: 0, aberta: null, justExp: {} }); }) +
          ' style="' + pill(false) + chipMenor + '">recolher</div>';
    }

    out.push(
      '<div class="card" style="overflow-x: auto;">' +
        '<div style="display: flex; justify-content: space-between; align-items: flex-end; gap: 28px; padding: 22px 24px 18px;">' +
          '<div style="display: flex; flex-direction: column; gap: 5px;">' +
            '<div style="font-family: Newsreader, Georgia, serif; font-size: 26px; font-weight: 400; line-height: 1.1; color: #f5f3ee;">Aprovados, decisão e ficha</div>' +
            '<div style="font-size: 12.5px; color: #8b8f96;">Clique numa linha para abrir o porquê da decisão — e a ficha completa.</div>' +
          '</div>' +
          '<div style="display: flex; align-items: center; gap: 9px;">' +
            '<span style="font-size: 10px; font-weight: 600; letter-spacing: 0.14em; color: #8b8f96;">ORDENAR</span>' + chipsOrdem +
          '</div>' +
        '</div>' +
        '<div style="display: grid; grid-template-columns: 78px minmax(200px, 1fr) 280px 150px 56px 54px; gap: 14px; padding: 11px 24px; border-top: 1px solid #242a30; border-bottom: 1px solid #242a30; background: #131619; font-size: 10.5px; font-weight: 600; letter-spacing: 0.14em; color: #8b8f96;">' +
          '<span>CRITÉRIO</span><span>TÍTULO</span><span>ÁREA &gt; SUB-ÁREA</span><span>VERTENTE</span><span style="text-align: right;">VOTOS</span><span style="text-align: right;">DIA</span>' +
        '</div>' +
        linhasFicha +
        (linhasFicha ? '' : '<div style="padding: 54px 24px; text-align: center; font-size: 13px; color: #6d7178;">Nenhum paper aprovado dentro deste recorte.</div>') +
        '<div style="display: flex; align-items: center; gap: 14px; padding: 15px 24px;">' +
          '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 11px; color: #6d7178;">' +
            (aprovadosCard.length > limite
              ? 'Mostrando ' + limite + ' de ' + aprovadosCard.length + ' aprovados.'
              : aprovadosCard.length + ' aprovado(s) neste recorte.') +
          '</span>' +
          rodapeMais +
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
