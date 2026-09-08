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

  /* Passos escuro e claro da MESMA rampa de verde. Validados com o
     `validate_palette.js` da skill dataviz contra o fundo do card (#16191c),
     em modo ordinal: L monotona, ΔL >= 0.06, extremo claro a 4,16:1, e
     ΔE 27 sob protanopia - a separacao entre eles nao depende de enxergar o
     verde. Sao passos da rampa, nao cores avulsas: mexer num deles e mexer na
     rampa, e por isso o hex mora aqui uma vez so. */
  var VERDE_ESCURO = '#2e8b57';
  var VERDE_CLARO = '#8fe0ae';

  /* Os dois papeis do passo claro, nomeados a parte de proposito: eles dizem
     coisas diferentes em cards diferentes e nunca aparecem na mesma escala -
     cada card tem a sua legenda. O valor coincidir e intencional, e a
     indirecao e o que impede o acidente inverso: reestepar um dos papeis (por
     CVD, por exemplo) sem perceber que mexeu no outro exige trocar o alias
     aqui, de olho nos dois nomes. */
  var VERDE_ESTRITO = VERDE_ESCURO;
  var VERDE_AMPLO = VERDE_CLARO;

  /* Zero da rampa de taxa da matriz de cruzamentos: cinza, e nao o fundo do
     card, porque "0% aprovado" e um valor medido e precisa ser visivel. */
  var CINZA_ESTAVEL = '#6b7480';

  /* Serie do card "Como o voto amadurece". Roxo por eliminacao deliberada:
     azul e laranja sao estrito e amplo, cinza e `fora`, verde e aprovado e
     amarelo e link - a curva do voto nao e nenhuma dessas coisas, e pintar ela
     com uma delas sugeriria um recorte por veredito que o card justamente
     deixou de fazer. O hex e o slot violeta do mesmo catalogo dark de
     `camposFicha`. */
  var ROXO_VOTO = '#9085e9';

  var COMPACTA = false;

  var root = document.getElementById('painel');
  var elTip = document.getElementById('tip');

  var state = {
    aba: 'janela',
    diasSel: [], vereditos: [], areas: [], orgs: [],
    // recortes que so o grafico produz (nao ha menu para eles na barra de
    // filtro): `regrasFora` vem do clique no Pareto, `criterios` do clique no
    // card espelho dele ("Por que o pipeline aprova"), `areasSec` do clique na
    // matriz de cruzamento. Entram em `filtrados()` como qualquer dimensao.
    regrasFora: [], criterios: [], areasSec: [],
    busca: '', ordem: 'votos', aberta: null,
    menu: null, buscaMenu: '',
    perSel: null, abertaH: null,
    // alternancias de desenho dentro de um card - nao recortam dado
    vistaArea: 'dist', taxaDecomp: false, lagGrupo: 'veredito',
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
  /* Lado do criterio, na ordem canonica do `schemas.py`. O grafico dos
     aprovados separa os dois blocos por ela e a ficha lista os criterios nela -
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

  /* Interpolacao de cor para a rampa de taxa da matriz de cruzamentos.
     Mistura em vez de alfa: com alfa a celula herdaria o que estiver atras
     dela (o card, a borda, outra celula) e a mesma intensidade mudaria de cor
     conforme o lugar - numa rampa que E o dado, isso e erro de leitura, nao
     detalhe.

     Aceita `#rrggbb` e o proprio `rgb(...)` que devolve, porque a mistura pode
     ser encadeada; sem isso a segunda chamada recebia "rgb(" no lugar de um
     hex, `parseInt` dava NaN e a celula saia transparente - sem erro nenhum no
     console. */
  function rgbDe(c) {
    if (c.charAt(0) === '#') {
      return [parseInt(c.slice(1, 3), 16), parseInt(c.slice(3, 5), 16), parseInt(c.slice(5, 7), 16)];
    }
    return c.replace(/[^0-9,]/g, '').split(',').map(Number);
  }
  function mistura(a, b, t) {
    t = t < 0 ? 0 : (t > 1 ? 1 : t);
    var ca = rgbDe(a), cb = rgbDe(b);
    return 'rgb(' + ca.map(function (v, i) {
      return Math.round(v + (cb[i] - v) * t);
    }).join(',') + ')';
  }
  /* Cor de uma taxa de aprovacao: cinza (nenhum passou) → verde (todos). A
     rampa sai do cinza e nao do fundo porque aqui o zero e um valor medido,
     nao ausencia de dado - "0% aprovado" precisa ser visivel. */
  function corTaxa(taxa) { return mistura(CINZA_ESTAVEL, VERDE, taxa); }

  /* Marcador da matriz de cruzamentos: tamanho = total, cor = taxa de
     aprovacao. O diametro sai da RAIZ da fracao porque quem le compara area,
     nao largura - escalar o diametro direto pelo valor triplicaria a mancha de
     um cruzamento que so dobrou. Piso de 9px: abaixo disso o marcador some e
     deixa de ter alvo de hover. */
  var BOLHA_MIN = 9, BOLHA_MAX = 28;
  function bolha(n, max, taxa) {
    if (!n) return '';
    var d = BOLHA_MIN + (BOLHA_MAX - BOLHA_MIN) * Math.sqrt(n / Math.max(1, max));
    return '<span style="display: block; width: ' + d.toFixed(1) + 'px; height: ' + d.toFixed(1) + 'px; ' +
      'border-radius: 50%; background: ' + corTaxa(taxa) + ';"></span>';
  }

  /* `exceto` deixa uma ou mais dimensoes de fora: e o que mantem as outras
     opcoes de um seletor visiveis depois que ele ja filtrou (senao marcar a 2a
     area pelo grafico ficaria impossivel - a 1a teria apagado as demais
     barras). Aceita string ou array: a matriz de areas precisa soltar as duas
     dimensoes de area de uma vez para nao virar uma unica celula acesa. */
  function filtrados(exceto) {
    var s = state;
    var q = (s.busca || '').trim().toLowerCase();
    var solta = typeof exceto === 'string' ? [exceto] : (exceto || []);
    function livre(dim) { return solta.indexOf(dim) >= 0; }
    return DADOS.papers.filter(function (p) {
      if (s.diasSel.length && s.diasSel.indexOf(p.d) < 0) return false;
      if (s.vereditos.length && s.vereditos.indexOf(p.v) < 0) return false;
      // dentro de cada dimensao a selecao e OR; entre dimensoes, AND
      if (!livre('areas') && s.areas.length && s.areas.indexOf(p.a) < 0) return false;
      if (!livre('areasSec') && s.areasSec.length && !s.areasSec.some(function (a) { return (p.as || []).indexOf(a) >= 0; })) return false;
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

  function mostraTip(l1, l2) {
    return function (e) {
      elTip.innerHTML =
        '<div class="tip1">' + esc(l1) + '</div>' +
        '<div class="tip2">' + esc(l2) + '</div>';
      elTip.style.display = 'block';
      elTip.style.left = (e.clientX + 16) + 'px';
      elTip.style.top = (e.clientY + 16) + 'px';
    };
  }
  function escondeTip() { return function () { elTip.style.display = 'none'; }; }

  /* Quartil por interpolacao linear, usado tambem para a mediana (q = 0,5).
     Havia uma `mediana` propria, que arredondava para inteiro porque so media
     votos; ela saiu quando a curva de maturacao passou a medir PORCENTAGEM do
     voto final - arredondar ali perderia o cruzamento dos 90% por menos de um
     ponto, e no box plot da defasagem esconderia a assimetria que o grafico
     existe para mostrar. */
  function quartil(xs, q) {
    if (!xs.length) return 0;
    var o = xs.slice().sort(function (a, b) { return a - b; });
    var pos = (o.length - 1) * q;
    var lo = Math.floor(pos), hi = Math.ceil(pos);
    if (lo === hi) return o[lo];
    return o[lo] + (o[hi] - o[lo]) * (pos - lo);
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

  /* Alternador de vista dentro de um card (Distribuicao|Cruzamentos, dia|
     semana, veredito|area). Menor e mais discreto que a pilula de filtro de
     proposito: ele nao recorta paper nenhum, so troca o desenho - e no
     vocabulario do painel a pilula cheia significa filtro. */
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
        // o rotulo do criterio vai em tinta de texto, nao na cor do veredito:
        // a cor ja foi dita pela palavra ao lado e pela barra da esquerda
        (criterios ? '<span style="font-size: 12.5px; color: #a8a49b;">· ' + esc(criterios) + '</span>' : '') +
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

  /* Rodape comum as duas abas: a procedencia do dado e os modelos que o
     produziram nao mudam de aba para aba. */
  function rodape(esquerda) {
    return '<div style="display: flex; justify-content: space-between; align-items: baseline; gap: 28px; padding-top: 24px; margin-top: 30px; border-top: 1px solid #242a30; font-size: 10.5px; letter-spacing: 0.1em; color: #5f636a;">' +
      '<span>' + esquerda + '</span>' +
      '<span>ESTÁGIO A: ' + esc(DADOS.modeloA) + ' · ESTÁGIO B: ' + esc(DADOS.modeloB) + '</span>' +
      '</div>';
  }

  /* Navegacao entre as duas abas. Sublinhado em vez de pilula: as pilulas ja
     significam "filtro" em todo o resto do painel, e uma aba nao filtra nada -
     ela troca a pergunta que a pagina responde. */
  function navAbas() {
    var s = state;
    var itens = [
      { valor: 'janela', label: 'Janela', nota: DADOS.papers.length + ' papers · ' + DADOS.janela + 'd' +
          (DADOS.pendentes ? ' · +' + DADOS.pendentes + ' na fila' : '') },
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
            (DADOS.diasRefresh || DADOS.diasHall) + ' dias — a mesma marca em que o pipeline para de reconsultar os votos dele. Até lá ele está na aba <em style="color: #a8a49b;">Janela</em>, com o número de votos ainda vivo.</div>' +
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
          'A aba <em style="color: #ecebe6; font-style: normal;">Janela</em> mostra os últimos ' + DADOS.janela + ' dias. Aqui ficam, de cada trimestre já fora dela, os mais votados pela comunidade — ' +
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
        '<div class="row"' + ev('c', function () { setState({ abertaH: aberta ? null : p.id }); }) + ' style="display: grid; grid-template-columns: 30px 78px minmax(0, 1fr) 200px 66px 60px; gap: 14px; padding: 14px 24px; align-items: center;">' +
          '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 12px; color: ' + (i < 3 ? ACCENT : '#4a5058') + ';">' + (i + 1) + '</span>' +
          '<span style="' + badge + '">' + esc(p.v) + '</span>' +
          '<div style="display: flex; flex-direction: column; gap: 3px; min-width: 0;">' +
            '<span style="font-size: 13.5px; color: #ecebe6; line-height: 1.3; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">' + esc(p.t) + '</span>' +
            '<span style="font-size: 11.5px; color: #6d7178; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">' + esc(p.org || '—') + (p.f ? '' : ' · sem ficha') + '</span>' +
          '</div>' +
          '<span style="font-size: 11.5px; color: #8b8f96; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">' + esc(parArea(p)) + '</span>' +
          '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 12.5px; color: #ecebe6; text-align: right;">' + p.u + '</span>' +
          '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 11.5px; color: #6d7178; text-align: right;">' + diaCurto(p.d) + '</span>' +
        '</div>' + corpo +
        '</div>';
    }).join('');

    out.push(
      '<div class="card" style="overflow: hidden; margin-bottom: 34px;">' +
        '<div style="display: flex; justify-content: space-between; align-items: flex-end; gap: 28px; padding: 22px 24px 18px;">' +
          '<div style="display: flex; flex-direction: column; gap: 5px;">' +
            '<div style="font-family: Newsreader, Georgia, serif; font-size: 26px; font-weight: 400; line-height: 1.1; color: #f5f3ee;">O que ficou do ' + esc(atual.rot) + '</div>' +
            '<div style="font-size: 12.5px; color: #8b8f96;">' + atual.ap.length + ' de ' + atual.na + ' aprovados, ordenados por voto da comunidade. Clique para abrir o porquê da decisão — e a ficha inteira, quando o Estágio B chegou a escrevê-la.</div>' +
          '</div>' + avisoCons +
        '</div>' +
        '<div style="display: grid; grid-template-columns: 30px 78px minmax(0, 1fr) 200px 66px 60px; gap: 14px; padding: 11px 24px; border-top: 1px solid #242a30; border-bottom: 1px solid #242a30; background: #131619; font-size: 10.5px; font-weight: 600; letter-spacing: 0.14em; color: #8b8f96;">' +
          '<span>#</span><span>CRITÉRIO</span><span>TÍTULO</span><span>ÁREA</span><span style="text-align: right;">VOTOS</span><span style="text-align: right;">DIA</span>' +
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
      '<div class="card" style="overflow: hidden; margin-bottom: 34px;">' +
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
            '</span>' +
          '</div>' +
          '<div style="display: flex; flex-direction: column; gap: 5px;">' +
            '<span style="font-size: 10px; letter-spacing: 0.16em; color: #6d7178;">EXTRAÍDO</span>' +
            '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 14px; color: #ecebe6;">' + esc(DADOS.gerado.replace('T', ' ').slice(0, 16)) + '</span>' +
          '</div>' +
        '</div>' +
      '</div>'
    );

    out.push(navAbas());

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
      var n = todos.filter(function (p) { return p.v === v; }).length;
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

    var contaDia = {};
    todos.forEach(function (p) { if (p.d) contaDia[p.d] = (contaDia[p.d] || 0) + 1; });
    // mais recente primeiro: e por onde se comeca a ler o painel
    var itensDia = dias.slice().reverse().map(function (d) {
      return { valor: d, label: diaCurto(d), n: contaDia[d] || 0 };
    });

    var contaArea = {};
    todos.forEach(function (p) { if (p.a) contaArea[p.a] = (contaArea[p.a] || 0) + 1; });
    var itensArea = DADOS.areas.map(function (a) {
      return { valor: a.a, label: a.a, n: contaArea[a.a] || 0 };
    }).sort(function (x, y) { return y.n - x.n || x.label.localeCompare(y.label); });

    var contaOrg = {};
    todos.forEach(function (p) { if (p.org) contaOrg[p.org] = (contaOrg[p.org] || 0) + 1; });
    var semOrg = todos.filter(function (p) { return !p.org; }).length;
    var itensOrg = Object.keys(contaOrg).map(function (o) {
      return { valor: o, label: o, n: contaOrg[o] };
    }).sort(function (x, y) { return y.n - x.n || x.label.localeCompare(y.label); });
    itensOrg.push({ valor: '__sem-org__', label: 'sem organização', n: semOrg });

    var ativos = [];
    if (s.diasSel.length) ativos.push(s.diasSel.length === 1 ? diaCurto(s.diasSel[0]) : s.diasSel.length + ' dias');
    if (s.vereditos.length) ativos.push(s.vereditos.join('+'));
    if (s.areas.length) ativos.push(s.areas.length === 1 ? s.areas[0] : s.areas.length + ' áreas');
    // `regrasFora` e `areasSec` so entram pelo grafico: sem eles no resumo o
    // recorte ficaria invisivel e o "limpar" pareceria quebrado
    if (s.areasSec.length) ativos.push(s.areasSec.length === 1 ? 'sec: ' + s.areasSec[0] : s.areasSec.length + ' áreas secundárias');
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
    var zTema = s.menu === 'areas' ? 90 : 2;
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
            '<div class="chip"' + ev('c', function () { setState({ diasSel: [], vereditos: [], areas: [], areasSec: [], regrasFora: [], criterios: [], orgs: [], busca: '', aberta: null, menu: null, buscaMenu: '', justExp: {} }); }) + ' style="' + estiloLimpar + '">' +
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
        linhaFiltro('TEMA', zTema, montaMenu('ÁREA', 'areas', itensArea, { todos: 'todas' })) +
        linhaFiltro('AUTORIA', zOrg, montaMenu('ORGANIZAÇÃO', 'orgs', itensOrg, { todos: 'todas' })) +
      '</div>'
    );

    if (s.menu) {
      out.push('<div' + ev('c', function () { setState({ menu: null, buscaMenu: '' }); }) + ' style="position: fixed; inset: 0; z-index: 80;"></div>');
    }

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
    out.push(secao('01', 'Volume e recência'));

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
      '<div class="card" style="padding: 22px 24px 20px; margin-bottom: 14px; display: flex; flex-direction: column; gap: 18px;">' +
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

    /* ── defasagem arXiv → HF Daily ─────────────────────────────────────── */
    /* `p.d - p.da` em dias. Negativo significaria HF Daily antes do arXiv, que
       nao existe no mundo - por isso o valor nao e corrigido nem cortado aqui:
       ele fica no grafico, em vermelho, como achado de auditoria. */
    var comLag = [];
    sel.forEach(function (p) {
      var a = diaNum(p.da), b = diaNum(p.d);
      if (a === null || b === null) return;
      comLag.push({ p: p, lag: b - a });
    });

    var chaveLag = s.lagGrupo === 'area'
      ? function (r) { return r.p.a || 'sem área'; }
      : function (r) { return r.p.v; };
    var gruposLag = {};
    comLag.forEach(function (r) {
      var k = chaveLag(r);
      if (!gruposLag[k]) gruposLag[k] = [];
      gruposLag[k].push(r);
    });
    var ordemLag = s.lagGrupo === 'area'
      ? Object.keys(gruposLag).sort(function (x, y) { return gruposLag[y].length - gruposLag[x].length || x.localeCompare(y); })
      : ['estrito', 'amplo', 'fora'].filter(function (v) { return gruposLag[v]; });

    var negativos = comLag.filter(function (r) { return r.lag < 0; }).length;
    var minLag = Math.min.apply(null, comLag.map(function (r) { return r.lag; }).concat([0]));
    var maxLag = Math.max.apply(null, comLag.map(function (r) { return r.lag; }).concat([1]));
    if (maxLag <= minLag) maxLag = minLag + 1;
    function posLag(v) { return ((v - minLag) / (maxLag - minLag)) * 100; }

    /* Passo "redondo" (1, 2, 5, 10 · 10^k) para o eixo de dias: fixar o passo
       quebraria quando um recorte deixasse a janela com 3 dias de defasagem. */
    function passoEixo(intervalo, alvo) {
      var bruto = intervalo / Math.max(1, alvo);
      var mag = Math.pow(10, Math.floor(Math.log(bruto) / Math.LN10));
      var n = bruto / mag;
      return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * mag;
    }
    /* Piso de 1: o eixo conta dias inteiros. Num recorte em que todas as
       defasagens caem em {0, 1}, o passo redondo daria 0,2 e os seis ticks
       colapsariam em "0 0 0 1 1 1", empilhando rotulo sobre rotulo. */
    var passoLag = Math.max(1, passoEixo(maxLag - minLag, 6));
    var ticksLag = [];
    for (var tl = Math.ceil(minLag / passoLag) * passoLag; tl <= maxLag + 0.001; tl += passoLag) ticksLag.push(Math.round(tl));
    // o passo redondo quase nunca cai sobre o minimo negativo; sem este tick a
    // faixa vermelha do grafico ficaria sem numero e o leitor nao saberia de
    // quantos dias e a inversao que ele esta vendo
    if (minLag < 0 && ticksLag[0] !== minLag) ticksLag.unshift(minLag);

    var MIN_CAIXA = 5;
    var caixasLag = ordemLag.map(function (k) {
      var itens = gruposLag[k];
      var xs = itens.map(function (r) { return r.lag; });
      var cg = s.lagGrupo === 'area' ? ACCENT : cor(k);
      var med = quartil(xs, 0.5);

      function ponto(r, forte) {
        var neg = r.lag < 0;
        return '<span class="mark"' +
          ev('e', mostraTip(r.p.t, r.lag + ' dia(s) · arXiv ' + diaCurto(r.p.da) + ' → HF ' + diaCurto(r.p.d) + (neg ? ' · valor negativo, provável erro de dado' : ''))) +
          ev('l', escondeTip()) +
          ' style="position: absolute; left: ' + posLag(r.lag) + '%; top: 50%; width: 7px; height: 7px; margin-left: -3.5px; margin-top: -3.5px; border-radius: 50%; background: ' +
          (neg ? '#e66767' : cg) + '; opacity: ' + (forte ? '0.9' : '0.72') + ';"></span>';
      }

      var miolo;
      if (itens.length < MIN_CAIXA) {
        /* Abaixo de cinco papers a caixa desenharia quartis que a amostra nao
           sustenta - os pontos individuais dizem a mesma coisa sem fingir
           distribuicao. */
        miolo = itens.map(function (r) { return ponto(r, true); }).join('');
      } else {
        var q1 = quartil(xs, 0.25), q3 = quartil(xs, 0.75);
        var iqr = q3 - q1;
        var limInf = q1 - 1.5 * iqr, limSup = q3 + 1.5 * iqr;
        var dentro = xs.filter(function (v) { return v >= limInf && v <= limSup; });
        var hasteInf = dentro.length ? Math.min.apply(null, dentro) : q1;
        var hasteSup = dentro.length ? Math.max.apply(null, dentro) : q3;
        var fora = itens.filter(function (r) { return r.lag < limInf || r.lag > limSup; });
        miolo =
          '<div style="position: absolute; left: ' + posLag(hasteInf) + '%; width: ' + (posLag(hasteSup) - posLag(hasteInf)) + '%; top: 50%; height: 1px; background: ' + cg + '; opacity: 0.5;"></div>' +
          '<div style="position: absolute; left: ' + posLag(hasteInf) + '%; top: 32%; bottom: 32%; width: 1px; background: ' + cg + '; opacity: 0.5;"></div>' +
          '<div style="position: absolute; left: ' + posLag(hasteSup) + '%; top: 32%; bottom: 32%; width: 1px; background: ' + cg + '; opacity: 0.5;"></div>' +
          '<div' +
            ev('e', mostraTip(k + ' · n = ' + itens.length, 'mediana ' + med + 'd · P25 ' + q1 + 'd · P75 ' + q3 + 'd · haste ' + hasteInf + '–' + hasteSup + 'd')) +
            ev('l', escondeTip()) +
            ' style="position: absolute; left: ' + posLag(q1) + '%; width: ' + (posLag(q3) - posLag(q1)) + '%; top: 22%; bottom: 22%; background: ' + cg + '26; border: 1px solid ' + cg + '; border-radius: 2px; cursor: pointer;"></div>' +
          '<div style="position: absolute; left: ' + posLag(med) + '%; top: 16%; bottom: 16%; width: 2px; margin-left: -1px; background: ' + cg + ';"></div>' +
          fora.map(function (r) { return ponto(r, false); }).join('');
      }

      return '<div style="display: grid; grid-template-columns: 168px minmax(0, 1fr) 44px; gap: 14px; align-items: center;">' +
        '<div style="display: flex; align-items: center; gap: 8px; font-size: 12.5px; color: #ecebe6; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">' +
          '<span style="flex: none; display: inline-block; width: 8px; height: 8px; border-radius: 2px; background: ' + cg + ';"></span>' + esc(k) + '</div>' +
        '<div style="position: relative; height: 40px; border-bottom: 1px solid #1d2226;">' +
          (minLag < 0 ? '<div style="position: absolute; left: 0; width: ' + posLag(0) + '%; top: 0; bottom: 0; background: rgba(230,103,103,0.08);"></div>' : '') +
          miolo +
        '</div>' +
        '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 11.5px; color: ' + (itens.length < MIN_CAIXA ? '#6d7178' : '#8b8f96') + '; text-align: right;">n ' + itens.length + '</span>' +
        '</div>';
    }).join('');

    out.push(
      '<div class="card" style="padding: 22px 24px 20px; margin-bottom: 34px; display: flex; flex-direction: column; gap: 16px;">' +
        '<div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 18px;">' +
          '<div style="display: flex; flex-direction: column; gap: 5px;">' +
            '<div style="font-family: Newsreader, Georgia, serif; font-size: 26px; font-weight: 400; line-height: 1.1; color: #f5f3ee;">Defasagem arXiv → HF Daily</div>' +
            '<div style="font-size: 12.5px; color: #8b8f96;">Dias entre a publicação no arXiv e a entrada no Daily. Caixa = P25–P75, traço = mediana, pontos = fora de 1,5×IQR.' +
              (comLag.length < sel.length ? ' <span style="color: #6d7178;">' + (sel.length - comLag.length) + ' sem uma das duas datas.</span>' : '') +
            '</div>' +
          '</div>' +
          '<div style="display: flex; align-items: center; gap: 9px; padding-top: 3px;">' +
            '<span style="font-size: 10px; font-weight: 600; letter-spacing: 0.14em; color: #8b8f96;">AGRUPAR</span>' +
            chipVista('veredito', s.lagGrupo === 'veredito', function () { setState({ lagGrupo: 'veredito' }); }) +
            chipVista('área', s.lagGrupo === 'area', function () { setState({ lagGrupo: 'area' }); }) +
          '</div>' +
        '</div>' +
        (caixasLag
          ? '<div style="display: flex; flex-direction: column; gap: 8px;">' + caixasLag + '</div>' +
            '<div style="display: grid; grid-template-columns: 168px minmax(0, 1fr) 44px; gap: 14px;"><div></div>' +
              '<div style="position: relative; height: 18px;">' +
                ticksLag.map(function (v) {
                  return '<span style="position: absolute; left: ' + posLag(v) + '%; transform: translateX(-50%); font-family: \'IBM Plex Mono\', monospace; font-size: 11px; color: ' + (v < 0 ? '#e66767' : '#6d7178') + ';">' + v + '</span>';
                }).join('') +
              '</div><div></div>' +
            '</div>' +
            (negativos
              ? '<div style="font-size: 12px; color: #e66767; background: rgba(230,103,103,0.08); border: 1px solid rgba(230,103,103,0.3); border-radius: 4px; padding: 9px 12px;">' +
                  negativos + ' paper(s) com defasagem negativa — o HF Daily viria antes do arXiv. O valor fica no gráfico como está: é problema de dado a auditar, não de escala a corrigir.</div>'
              : '')
          : '<div style="padding: 44px 0; text-align: center; font-size: 12.5px; color: #6d7178;">Nenhum paper com as duas datas dentro deste recorte.</div>') +
      '</div>'
    );

    /* ══════════════ 02 · VOCABULÁRIO E CRUZAMENTOS ══════════════ */
    out.push(secao('02', 'Vocabulário e cruzamentos'));

    var areaMap = {};
    filtrados('areas').forEach(function (p) {
      if (!p.a) return;
      if (!areaMap[p.a]) areaMap[p.a] = { fora: 0, amplo: 0, estrito: 0, total: 0 };
      areaMap[p.a][p.v]++; areaMap[p.a].total++;
    });
    var areasOrd = Object.keys(areaMap).sort(function (x, y) { return areaMap[y].total - areaMap[x].total; });
    var maxArea = Math.max.apply(null, areasOrd.map(function (a) { return areaMap[a].total; }).concat([1]));
    var barrasArea = areasOrd.map(function (a) {
      var c = areaMap[a];
      var on = s.areas.indexOf(a) >= 0;
      var segs = ['estrito', 'amplo', 'fora'].filter(function (v) { return c[v] > 0; }).map(function (v) {
        return '<div class="bar" style="flex: ' + c[v] + '; background: ' + cor(v) + ';"></div>';
      }).join('');
      return '<div' + ev('c', function () { alternaLista('areas', a); }) +
        ev('e', mostraTip(a, c.estrito + ' estrito · ' + c.amplo + ' amplo · ' + c.fora + ' fora')) +
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

    /* ── matriz área primária × secundária ──────────────────────────────── */
    /* As duas dimensoes de area saem do recorte de uma vez: filtrar por uma
       delas e depois desenhar a matriz deixaria uma linha (ou uma coluna) acesa
       e o resto apagado - e o cruzamento seria ilegivel justamente depois do
       primeiro clique nele. */
    var selMatriz = filtrados(['areas', 'areasSec']);
    var totPrim = {}, totSec = {}, cruz = {}, semSec = 0;
    selMatriz.forEach(function (p) {
      if (p.a) totPrim[p.a] = (totPrim[p.a] || 0) + 1;
      var secs = p['as'] || [];
      if (!secs.length) { semSec++; return; }
      secs.forEach(function (b) {
        totSec[b] = (totSec[b] || 0) + 1;
        if (!p.a) return;
        var k = p.a + '\u0000' + b;
        if (!cruz[k]) cruz[k] = { n: 0, ap: 0 };
        cruz[k].n++;
        if (p.v !== 'fora') cruz[k].ap++;
      });
    });
    // linhas e colunas na mesma ordem (volume da area primaria): so assim a
    // diagonal significa "primaria igual a secundaria" e pode ser neutralizada
    var eixoAreas = DADOS.areas.map(function (a) { return a.a; })
      .filter(function (a) { return totPrim[a] || totSec[a]; })
      .sort(function (x, y) { return (totPrim[y] || 0) - (totPrim[x] || 0) || x.localeCompare(y); });
    var maxCruz = 1;
    for (var kc in cruz) if (Object.prototype.hasOwnProperty.call(cruz, kc) && cruz[kc].n > maxCruz) maxCruz = cruz[kc].n;

    var colsMatriz = 'grid-template-columns: 190px repeat(' + Math.max(1, eixoAreas.length) + ', minmax(0, 1fr)); gap: 3px;';
    var cabMatriz = '<div style="display: grid; ' + colsMatriz + ' align-items: end; margin-bottom: 3px;">' +
      '<div style="font-size: 10px; font-weight: 600; letter-spacing: 0.13em; color: #6d7178; padding-bottom: 4px;">PRIMÁRIA ↓ &nbsp;SEC →</div>' +
      eixoAreas.map(function (a, j) {
        return '<div' + ev('e', mostraTip(a, 'coluna ' + (j + 1) + ' · ' + (totSec[a] || 0) + ' como área secundária')) + ev('l', escondeTip()) +
          ' style="font-family: \'IBM Plex Mono\', monospace; font-size: 11px; color: #8b8f96; text-align: center; padding-bottom: 4px; cursor: pointer;">' + (j + 1) + '</div>';
      }).join('') + '</div>';

    var linhasMatriz = eixoAreas.map(function (a, i) {
      var celulas = eixoAreas.map(function (b, j) {
        if (i === j) {
          // uma area nunca e secundaria de si mesma: a celula existe so para a
          // grade nao pular, e por isso nao acende nem responde a clique
          return '<div style="height: 34px; border-radius: 2px; background: #16191c; border: 1px dashed #242a30;"></div>';
        }
        var c = cruz[a + '\u0000' + b];
        var n = c ? c.n : 0;
        var marcada = s.areas.length === 1 && s.areas[0] === a && s.areasSec.length === 1 && s.areasSec[0] === b;
        return '<div' +
          ev('c', function () {
            setState(marcada
              ? { areas: [], areasSec: [], aberta: null, justExp: {} }
              : { areas: [a], areasSec: [b], aberta: null, justExp: {} });
          }) +
          ev('e', mostraTip(a + ' → ' + b, n ? n + ' papers · ' + (c.ap) + ' aprovados · ' + (n - c.ap) + ' descartados · ' + pct(c.ap, n) + '% aprovado' : 'nenhum paper neste cruzamento')) +
          ev('l', escondeTip()) +
          ' style="height: 34px; border-radius: 2px; display: flex; align-items: center; justify-content: center; cursor: pointer; background: ' +
          (marcada ? 'rgba(217,164,65,0.1)' : 'transparent') +
          '; border: 1px solid ' + (marcada ? ACCENT : 'transparent') + ';">' +
          bolha(n, maxCruz, n ? c.ap / n : 0) +
          '</div>';
      }).join('');
      var onLinha = s.areas.length === 1 && s.areas[0] === a;
      return '<div style="display: grid; ' + colsMatriz + ' align-items: center;">' +
        '<div' + ev('c', function () { alternaLista('areas', a); }) +
          ' style="display: flex; align-items: baseline; gap: 8px; font-size: 12px; color: ' + (onLinha ? ACCENT : '#a8a49b') + '; cursor: pointer; overflow: hidden;">' +
          '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 11px; color: #6d7178;">' + (i + 1) + '</span>' +
          '<span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">' + esc(a) + '</span>' +
        '</div>' + celulas + '</div>';
    }).join('');

    /* A matriz codifica duas medidas ao mesmo tempo, e nenhuma delas esta
       escrita na celula - entao a chave de leitura e obrigatoria, nao enfeite:
       sem ela "grande e cinza" nao significa nada. */
    var legendaMatriz =
      '<div style="display: flex; align-items: center; gap: 22px; flex-wrap: wrap; font-size: 11.5px; color: #a8a49b;">' +
        '<div style="display: flex; align-items: center; gap: 8px;">' +
          '<span style="color: #6d7178;">TAMANHO</span>' +
          [1, Math.max(2, Math.round(maxCruz / 2)), maxCruz].filter(function (v, i, l) { return l.indexOf(v) === i; })
            .map(function (v) {
              return '<span style="display: inline-flex; align-items: center; gap: 4px;">' +
                bolha(v, maxCruz, 0.5) +
                '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 10.5px; color: #6d7178;">' + v + '</span></span>';
            }).join('') +
          '<span>papers no cruzamento</span>' +
        '</div>' +
        '<div style="display: flex; align-items: center; gap: 8px;">' +
          '<span style="color: #6d7178;">COR</span>' +
          '<span>0%</span>' +
          '<span style="display: inline-block; width: 88px; height: 9px; border-radius: 100px; background: linear-gradient(to right, ' +
            corTaxa(0) + ', ' + corTaxa(0.5) + ', ' + corTaxa(1) + ');"></span>' +
          '<span>100% aprovado</span>' +
        '</div>' +
      '</div>';

    var vistaAreaCruz = s.vistaArea === 'cruz';
    out.push(
      '<div class="card" style="padding: 22px 24px 20px; margin-bottom: 34px; display: flex; flex-direction: column; gap: 18px;">' +
        '<div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 18px;">' +
          '<div style="display: flex; flex-direction: column; gap: 5px;">' +
            '<div style="font-family: Newsreader, Georgia, serif; font-size: 26px; font-weight: 400; line-height: 1.1; color: #f5f3ee;">Área primária</div>' +
            '<div style="font-size: 12.5px; color: #8b8f96;">' +
              (vistaAreaCruz
                ? 'Tamanho = papers no cruzamento, cor = taxa de aprovação. Grande e verde: muitos e muito aprovados; grande e cinza: muitos e poucos. Cada paper conta uma vez por área secundária; clique para filtrar a combinação.' +
                  (semSec ? ' <span style="color: #6d7178;">' + semSec + ' sem área secundária ficam fora da matriz.</span>' : '')
                : 'A LLM escolhe de uma lista fechada — nunca inventa rótulo. Clique para filtrar.') +
            '</div>' +
          '</div>' +
          '<div style="display: flex; align-items: center; gap: 9px; padding-top: 3px;">' +
            chipVista('Distribuição', !vistaAreaCruz, function () { setState({ vistaArea: 'dist' }); }) +
            chipVista('Cruzamentos', vistaAreaCruz, function () { setState({ vistaArea: 'cruz' }); }) +
          '</div>' +
        '</div>' +
        (vistaAreaCruz
          ? (eixoAreas.length
            ? legendaMatriz + '<div style="display: flex; flex-direction: column; gap: 3px;">' + cabMatriz + linhasMatriz + '</div>'
            : '<div style="padding: 44px 0; text-align: center; font-size: 12.5px; color: #6d7178;">Nenhuma área dentro deste recorte.</div>')
          : (barrasArea
            ? '<div style="display: flex; flex-direction: column; gap: 13px;">' + barrasArea + '</div>'
            : '<div style="padding: 44px 0; text-align: center; font-size: 12.5px; color: #6d7178;">Nenhuma área dentro deste recorte.</div>')) +
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
    var comRegra = descartes.filter(function (p) { return !!p.rf; }).length;
    var maxRegra = Math.max.apply(null, regrasOrd.map(function (k) { return contaRegra[k]; }).concat([1]));

    var linhasPareto = regrasOrd.map(function (k) {
      var n = contaRegra[k];
      var parte = totalDesc ? (n / totalDesc) * 100 : 0;
      var on = s.regrasFora.indexOf(k) >= 0;
      var nulo = k === REGRA_NULA;
      /* O nulo nao e uma regra: e a cobertura que falta. Cinza em vez do azul
         da serie, para nao ler como mais um motivo de descarte a estudar.
         Ele CONTINUA no codigo mesmo tendendo a zero (a regra virou
         obrigatoria em todo `fora`): uma categoria que some quando zera
         esconde o dia em que ela deixar de ser zero. */
      var corBarra = nulo ? '#4a5058' : (on ? ACCENT : '#3987e5');
      return '<div' +
        ev('c', function () { alternaLista('regrasFora', k); }) +
        ev('e', mostraTip(rotulo(k), n + ' descartes · ' + parte.toFixed(1) + '% dos descartados')) +
        ev('l', escondeTip()) +
        ' style="display: flex; flex-direction: column; gap: 6px; padding-bottom: 12px; cursor: pointer;">' +
        // o rotulo agora ocupa a linha inteira: a metade direita pertencia a
        // curva do acumulado, que saiu (com seis regras ela era decorativa e
        // o numero dela nao era legivel sobre as barras)
        '<div style="display: flex; align-items: baseline; gap: 12px;">' +
          '<span style="font-size: 13px; color: ' + (on ? ACCENT : (nulo ? '#8b8f96' : '#ecebe6')) + '; font-weight: ' + (on ? '600' : '400') + '; font-style: ' + (nulo ? 'italic' : 'normal') + '; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">' + esc(rotulo(k)) + '</span>' +
          '<span style="flex: none; font-family: \'IBM Plex Mono\', monospace; font-size: 11.5px; color: #8b8f96; white-space: nowrap;">' +
            n + ' <span style="color: #5f636a;">· ' + parte.toFixed(1) + '% dos descartados</span></span>' +
        '</div>' +
        '<div style="height: 13px; background: #1d2226; border-radius: 2px; overflow: hidden;">' +
          '<div class="bar" style="height: 100%; width: ' + ((n / maxRegra) * 100) + '%; min-width: 2px; background: ' + corBarra + '; border-radius: 2px;"></div>' +
        '</div>' +
        '</div>';
    }).join('');

    out.push(
      '<div class="card" style="padding: 22px 24px 20px; margin-bottom: 14px; display: flex; flex-direction: column; gap: 18px;">' +
        '<div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 18px;">' +
          '<div style="display: flex; flex-direction: column; gap: 5px; max-width: 720px;">' +
            '<div style="font-family: Newsreader, Georgia, serif; font-size: 26px; font-weight: 400; line-height: 1.1; color: #f5f3ee;">Onde o pipeline corta</div>' +
            /* Este card tinha um alternador `quantidade | % dos descartados`,
               removido junto com a linha do acumulado. Ele nao foi pedido pela
               spec e a remocao e decisao desta implementacao: as duas vistas
               diferiam so no denominador da largura (n/maior barra contra
               n/total de descartes), que e reescalonamento monotono - a mesma
               forma, outro tamanho - e o percentual que a vista `pct` existia
               para mostrar agora esta impresso em toda barra pelo rotulo fixo
               "n · X% dos descartados". Sobrava um chip que nao mudava nada
               legivel. */
            '<div style="font-size: 12.5px; color: #8b8f96;">Motivos de descarte em ordem de volume. Clique numa regra para filtrar o painel inteiro. ' +
              '<span style="color: ' + (comRegra === totalDesc ? '#6d7178' : ACCENT) + ';">Cobertura de regra: ' + comRegra + ' de ' + totalDesc + ' descartes (' + pct(comRegra, totalDesc) + '%).</span></div>' +
          '</div>' +
        '</div>' +
        (linhasPareto
          ? '<div>' + linhasPareto + '</div>'
          : '<div style="padding: 44px 0; text-align: center; font-size: 12.5px; color: #6d7178;">Nenhum descarte dentro deste recorte.</div>') +
      '</div>'
    );

    /* ── por que o pipeline aprova ──────────────────────────────────────────
       O espelho do Pareto. Duas diferencas de leitura que o subtitulo precisa
       dizer, porque nenhuma delas se ve no desenho:

       1. A contagem e por OCORRENCIA. Um paper com dois criterios entra nas
          duas barras, entao a soma das barras passa do total de aprovados -
          o subtitulo traz esse total justamente para ninguem somar.
       2. So os criterios de amplo tem barra de duas cores. Criterio de
          estrito num paper implica veredito estrito (`veredito_dos_criterios`
          em schemas.py), entao a barra dele e de uma cor so - e esta certo.
          A divisao carrega informacao no outro lado: um `benchmark` que
          acompanhou um `artefato_aberto` aparece em verde escuro. */
    var selCrit = filtrados('criterios');
    var aprovadosCrit = selCrit.filter(function (p) { return p.v !== 'fora'; });
    var contaCrit = {};
    var comCriterio = 0;
    aprovadosCrit.forEach(function (p) {
      var lista = p.cr || [];
      if (lista.length) comCriterio++;
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
    function blocoCriterios(lista) {
      return lista.filter(function (k) { return contaCrit[k]; })
        .sort(function (x, y) { return contaCrit[y].total - contaCrit[x].total || ordemCriterio(x) - ordemCriterio(y); });
    }
    var critEstrito = blocoCriterios(CRITERIOS_ESTRITO);
    var critAmplo = blocoCriterios(CRITERIOS_AMPLO);
    // enum que o schema ganhou e este mapa ainda nao conhece: sai no fim, com
    // o proprio enum como rotulo, em vez de desaparecer da contagem
    var critOutros = blocoCriterios(Object.keys(contaCrit).filter(function (k) { return CRITERIOS.indexOf(k) < 0; }));

    function barraCriterio(k) {
      var c = contaCrit[k];
      var on = s.criterios.indexOf(k) >= 0;
      var partes = [
        { v: 'estrito', n: c.estrito, cor: VERDE_ESTRITO },
        { v: 'amplo', n: c.amplo, cor: VERDE_AMPLO }
      ].filter(function (x) { return x.n > 0; });
      var detalhe = partes.map(function (x) { return x.n + ' ' + x.v; }).join(' · ');
      return '<div' +
        ev('c', function () { alternaLista('criterios', k); }) +
        ev('e', mostraTip(rotulo(k), c.total + ' aprovado(s) por este critério · ' + detalhe)) +
        ev('l', escondeTip()) +
        ' style="display: flex; flex-direction: column; gap: 6px; padding-bottom: 12px; cursor: pointer;">' +
        '<div style="display: flex; align-items: baseline; gap: 12px;">' +
          '<span style="font-size: 13px; color: ' + (on ? ACCENT : '#ecebe6') + '; font-weight: ' + (on ? '600' : '400') + '; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">' + esc(rotulo(k)) + '</span>' +
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

    // o separador fino que divide os dois blocos; o bloco de estrito vem
    // primeiro porque estrito prevalece quando os lados se misturam
    function tituloBloco(texto, primeiro) {
      return '<div style="' + (primeiro ? '' : 'border-top: 1px solid #242a30; margin-top: 6px; padding-top: 14px; ') +
        'font-size: 10px; font-weight: 600; letter-spacing: 0.14em; color: #6d7178; padding-bottom: 10px;">' + texto + '</div>';
    }
    var barrasCriterio = '';
    if (critEstrito.length) {
      barrasCriterio += tituloBloco('CARACTERIZAM ESTRITO', true) + critEstrito.map(barraCriterio).join('');
    }
    if (critAmplo.length) {
      barrasCriterio += tituloBloco('CARACTERIZAM AMPLO', !critEstrito.length) + critAmplo.map(barraCriterio).join('');
    }
    if (critOutros.length) {
      barrasCriterio += tituloBloco('FORA DO VOCABULÁRIO DESTE PAINEL', !critEstrito.length && !critAmplo.length) +
        critOutros.map(barraCriterio).join('');
    }

    var legendaCriterio = ['estrito', 'amplo'].map(function (v) {
      return '<div style="display: flex; align-items: center; gap: 6px; font-size: 11.5px; color: #a8a49b; white-space: nowrap;">' +
        '<span style="display: inline-block; width: 8px; height: 8px; border-radius: 2px; background: ' +
        (v === 'estrito' ? VERDE_ESTRITO : VERDE_AMPLO) + ';"></span>' + v + '</div>';
    }).join('');

    out.push(
      '<div class="card" style="padding: 22px 24px 20px; margin-bottom: 34px; display: flex; flex-direction: column; gap: 18px;">' +
        '<div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 18px;">' +
          '<div style="display: flex; flex-direction: column; gap: 5px; max-width: 720px;">' +
            '<div style="font-family: Newsreader, Georgia, serif; font-size: 26px; font-weight: 400; line-height: 1.1; color: #f5f3ee;">Por que o pipeline aprova</div>' +
            // A frase explica a REGRA de contagem e informa o total; nao afirma
            // qual dos dois numeros e maior. A versao anterior dizia "a soma das
            // barras passa dos N aprovados", o que so vale depois que a
            // cobertura de criterio chegar perto de 100% - hoje ela e de 2% e o
            // proprio grafico desmentia a frase tres linhas abaixo.
            '<div style="font-size: 12.5px; color: #8b8f96;">Contagem por ocorrência: um paper com dois critérios entra nos dois, então a soma das barras não é o número de aprovados. ' +
              aprovadosCrit.length + ' aprovados no recorte. Clique num critério para filtrar o painel inteiro. ' +
              '<span style="color: ' + (comCriterio === aprovadosCrit.length ? '#6d7178' : ACCENT) + ';">Cobertura de critério: ' +
              comCriterio + ' de ' + aprovadosCrit.length + ' aprovados (' + pct(comCriterio, aprovadosCrit.length) + '%).</span></div>' +
          '</div>' +
          '<div style="display: flex; gap: 15px; padding-top: 5px;">' + legendaCriterio + '</div>' +
        '</div>' +
        (barrasCriterio
          ? '<div>' + barrasCriterio + '</div>'
          : '<div style="padding: 44px 0; text-align: center; font-size: 12.5px; color: #6d7178;">Nenhum aprovado deste recorte tem critério de veredito registrado.</div>') +
      '</div>'
    );

    /* ══════════════ 04 · ATENÇÃO E ADOÇÃO ══════════════ */
    out.push(secao('04', 'Atenção e adoção'));

    /* ── como o voto amadurece ──────────────────────────────────────────────
       Uma curva so, normalizada. A versao anterior sobrepunha tres faixas
       P25–P75 (uma por veredito) em escala log, e nao dizia o que prometia: as
       amostras por idade nao eram comparaveis - so paper velho chega ao dia 20,
       entao o que subia era sobrevivencia, nao maturacao.

       Aqui cada paper vale 100% do PROPRIO voto final e a pergunta fica uma so:
       em quantos dias o voto para de se mexer? Tres decisoes sustentam isso:

       - `voto final` = ultimo snapshot do paper. So entram papers com 14 dias
         ou mais (`IDADE_FINAL`): abaixo disso "final" ainda esta subindo e o
         paper diria que amadureceu quando so foi medido cedo.
       - eixo y linear, 0 a 100%. Log aqui esconderia justamente o joelho da
         curva, que e a resposta.
       - a idade vem de `p.d` (data_hf_daily), nao do primeiro snapshot: o
         refresh nao mede todo paper no dia em que ele entra, entao "dias desde
         o primeiro snapshot" comeca o relogio em datas diferentes para cada
         paper e achata as primeiras 24 horas. */
    var MIN_AMOSTRA = 5;
    var IDADE_FINAL = 14;
    // idade medida da geracao do painel, nao do relogio do navegador: o HTML e
    // estatico e pode ser lido dias depois sem que os snapshots mudem
    var hojeNum = diaNum(String(DADOS.gerado).slice(0, 10));

    var acumulo = {};
    var nMaduros = 0, nNovos = 0;
    sel.forEach(function (p) {
      var serie = DADOS.serie[p.id];
      var base = diaNum(p.d);
      if (!serie || !serie.length || base === null || hojeNum === null) return;
      if (hojeNum - base < IDADE_FINAL) { nNovos++; return; }
      var votoFinal = null;
      for (var i = serie.length - 1; i >= 0; i--) {
        if (serie[i][1] !== null && serie[i][1] !== undefined) { votoFinal = serie[i][1]; break; }
      }
      // sem voto medido, ou final zero: nao ha fracao a formar (e dividir por
      // zero jogaria Infinity dentro da mediana)
      if (!votoFinal) return;
      nMaduros++;
      serie.forEach(function (m) {
        if (m[1] === null || m[1] === undefined) return;
        var idade = diaNum(m[0]) - base;
        // snapshot anterior ao HF Daily e dado torto: ele aparece na auditoria
        // da defasagem, nao como idade negativa nesta curva
        if (idade < 0) return;
        if (!acumulo[idade]) acumulo[idade] = [];
        acumulo[idade].push((m[1] / votoFinal) * 100);
      });
    });

    var idadeFim = -1;
    for (var ai in acumulo) {
      if (!Object.prototype.hasOwnProperty.call(acumulo, ai)) continue;
      if (acumulo[ai].length >= MIN_AMOSTRA && +ai > idadeFim) idadeFim = +ai;
    }

    var curva = [];
    for (var ic = 0; ic <= idadeFim; ic++) {
      var xsc = acumulo[ic] || [];
      // abaixo do minimo a mediana daquela idade nao se sustenta - o ponto fica
      // vazio e a linha quebra, em vez de interpolar o que falta
      if (xsc.length < MIN_AMOSTRA) { curva.push(null); continue; }
      curva.push({
        idade: ic, n: xsc.length,
        // `quartil` e nao `mediana`: esta ultima arredonda para inteiro, o que
        // aqui perderia o cruzamento dos 90% por menos de um ponto percentual
        med: quartil(xsc, 0.5), q1: quartil(xsc, 0.25), q3: quartil(xsc, 0.75)
      });
    }
    var diaEstavel = null;
    curva.forEach(function (r) { if (diaEstavel === null && r && r.med >= 90) diaEstavel = r.idade; });

    function xIdade(a) { return idadeFim > 0 ? (a / idadeFim) * 100 : 50; }
    // o clamp e so de desenho: um snapshot acima do proprio final significaria
    // voto perdido entre medicoes, e a mediana dele continua no tooltip
    function yPct(v) { return 100 - Math.max(0, Math.min(100, v)); }

    var desenhoMat = '';
    [0, 25, 50, 75, 100].forEach(function (g) {
      desenhoMat += '<line x1="0" y1="' + yPct(g) + '" x2="100" y2="' + yPct(g) + '" stroke="#1d2226" stroke-width="1" vector-effect="non-scaling-stroke"></line>';
    });
    // a referencia dos 90% e um tom acima da grade: e o patamar que a marca
    // vertical esta anunciando, e sem ela a linha tracejada nao teria contra o
    // que ser lida
    desenhoMat += '<line x1="0" y1="' + yPct(90) + '" x2="100" y2="' + yPct(90) + '" stroke="#333a41" stroke-width="1" vector-effect="non-scaling-stroke"></line>';
    trechos(curva).forEach(function (tr) {
      if (tr.length < 2) return;
      var cima = tr.map(function (r) { return [xIdade(r.idade), yPct(r.q3)]; });
      var baixo = tr.slice().reverse().map(function (r) { return [xIdade(r.idade), yPct(r.q1)]; });
      desenhoMat += poliArea(cima.concat(baixo), ROXO_VOTO, 0.16);
    });
    if (diaEstavel !== null) {
      desenhoMat += poliLinha([[xIdade(diaEstavel), 0], [xIdade(diaEstavel), 100]], ROXO_VOTO, 1.4, '4 4');
    }
    /* Idade sozinha entre dois buracos - hoje o dia 0, porque o refresh nao
       mede todo dia da primeira semana. Uma polilinha de um ponto so nao
       desenha nada, e era justamente o ponto mais informativo do grafico
       (dia 0: mediana ~80% do voto final) que sumia. Ele vira ponto com haste
       P25–P75: mesma informacao da faixa, na unica forma que um x sozinho
       comporta. O anel na cor do fundo e o que mantem o ponto legivel se a
       linha passar por perto. */
    trechos(curva).forEach(function (tr) {
      if (tr.length >= 2) {
        desenhoMat += poliLinha(tr.map(function (r) { return [xIdade(r.idade), yPct(r.med)]; }), ROXO_VOTO, 2, null);
        return;
      }
      var r = tr[0];
      desenhoMat += poliLinha([[xIdade(r.idade), yPct(r.q3)], [xIdade(r.idade), yPct(r.q1)]], ROXO_VOTO, 1.4, null);
    });
    var pontosSoltos = trechos(curva).filter(function (tr) { return tr.length === 1; }).map(function (tr) {
      var r = tr[0];
      return '<span style="position: absolute; left: ' + xIdade(r.idade) + '%; top: ' + yPct(r.med) +
        '%; width: 9px; height: 9px; margin-left: -4.5px; margin-top: -4.5px; border-radius: 50%; background: ' +
        ROXO_VOTO + '; border: 2px solid #16191c; pointer-events: none;"></span>';
    }).join('');

    var marcaEstavel = '';
    if (diaEstavel !== null) {
      // perto da borda direita o rotulo vira para a esquerda da linha, senao
      // ele sai do card - mesma regra dos rotulos da dispersao. A meia altura
      // porque a curva vive colada no topo depois que cruza os 90%: la em cima
      // o rotulo cairia em cima dela.
      var xe = xIdade(diaEstavel);
      var aEsquerda = xe > 62;
      marcaEstavel = '<span style="position: absolute; ' +
        (aEsquerda ? 'right: ' + (100 - xe) + '%; margin-right: 8px;' : 'left: ' + xe + '%; margin-left: 8px;') +
        ' top: 48%; font-size: 11px; color: ' + ROXO_VOTO + '; white-space: nowrap; pointer-events: none;">estabiliza por volta do dia +' + diaEstavel + '</span>';
    }

    var celulasMat = [];
    for (var im = 0; im <= idadeFim; im++) {
      (function (a) {
        var r = curva[a];
        celulasMat.push('<div' +
          ev('e', mostraTip('dia +' + a + ' desde o HF Daily',
            r ? 'mediana ' + r.med.toFixed(0) + '% do voto final · P25 ' + r.q1.toFixed(0) + '–P75 ' + r.q3.toFixed(0) + '% · n ' + r.n
              : 'menos de ' + MIN_AMOSTRA + ' papers medidos nesta idade')) +
          ev('l', escondeTip()) +
          ' style="flex: 1; height: 100%; cursor: pointer;"></div>');
      })(im);
    }

    var eixoMatY = [0, 25, 50, 75, 100].map(function (v) {
      return '<span style="position: absolute; top: ' + yPct(v) + '%; right: 0; transform: translateY(-50%); font-family: \'IBM Plex Mono\', monospace; font-size: 10.5px; color: #6d7178;">' + v + '%</span>';
    }).join('');
    var passoIdade = Math.max(1, passoEixo(Math.max(1, idadeFim), 6));
    var eixoMatX = '';
    for (var tx = 0; tx <= idadeFim; tx += passoIdade) {
      eixoMatX += '<span style="position: absolute; left: ' + xIdade(tx) + '%; transform: translateX(-50%); font-family: \'IBM Plex Mono\', monospace; font-size: 10.5px; color: #6d7178;">' + tx + '</span>';
    }

    /* Velocidade recente: delta entre os dois ultimos snapshots dividido pelo
       intervalo real entre eles. Sem a divisao, um paper medido de sete em sete
       dias venceria sempre um medido diariamente. */
    var vel = [];
    sel.forEach(function (p) {
      var serie = DADOS.serie[p.id];
      if (!serie || serie.length < 2) return;
      var ant = serie[serie.length - 2], ult = serie[serie.length - 1];
      if (ant[1] === null || ult[1] === null || ant[1] === undefined || ult[1] === undefined) return;
      var dias2 = diaNum(ult[0]) - diaNum(ant[0]);
      if (dias2 <= 0 || ult[1] <= ant[1]) return;
      vel.push({ p: p, taxa: (ult[1] - ant[1]) / dias2, de: ant[1], para: ult[1], dias: dias2 });
    });
    vel.sort(function (a, b) { return b.taxa - a.taxa; });
    var listaVel = vel.slice(0, 5).map(function (r) {
      return '<div' +
        ev('e', mostraTip(r.p.t, r.de + ' → ' + r.para + ' votos em ' + r.dias + ' dia(s) · ' + r.p.v)) +
        ev('l', escondeTip()) +
        ' style="display: flex; flex-direction: column; gap: 4px; cursor: pointer;">' +
        '<div style="display: flex; align-items: baseline; gap: 8px;">' +
          '<span style="flex: none; display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: ' + cor(r.p.v) + ';"></span>' +
          '<span style="font-size: 12px; color: #ecebe6; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">' + esc(r.p.t) + '</span>' +
        '</div>' +
        '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 11px; color: ' + ROXO_VOTO + '; padding-left: 15px;">+' + r.taxa.toFixed(1) + ' votos/dia</span>' +
        '</div>';
    }).join('') || '<div style="font-size: 12px; color: #6d7178; padding: 20px 0;">Nenhum paper com dois snapshots e voto crescendo neste recorte.</div>';

    /* Uma serie so, entao nao ha legenda de identidade a montar - o titulo ja
       diz o que esta plotado. O que precisa de chave sao as duas MARCAS
       (linha e faixa), que sao coisas diferentes desenhadas na mesma cor. */
    var chaveMat =
      '<div style="display: flex; gap: 15px; flex-wrap: wrap;">' +
        '<div style="display: flex; align-items: center; gap: 6px; font-size: 11.5px; color: #a8a49b; white-space: nowrap;">' +
          '<span style="display: inline-block; width: 14px; height: 0; border-top: 2px solid ' + ROXO_VOTO + ';"></span>mediana</div>' +
        '<div style="display: flex; align-items: center; gap: 6px; font-size: 11.5px; color: #a8a49b; white-space: nowrap;">' +
          '<span style="display: inline-block; width: 14px; height: 9px; border-radius: 2px; background: ' + ROXO_VOTO + '29;"></span>P25–P75</div>' +
      '</div>';

    out.push(
      '<div class="card" style="padding: 22px 24px 20px; margin-bottom: 14px; display: flex; flex-direction: column; gap: 18px;">' +
        '<div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 18px;">' +
          '<div style="display: flex; flex-direction: column; gap: 5px; max-width: 700px;">' +
            '<div style="font-family: Newsreader, Georgia, serif; font-size: 26px; font-weight: 400; line-height: 1.1; color: #f5f3ee;">Como o voto amadurece</div>' +
            '<div style="font-size: 12.5px; color: #8b8f96;">Cada paper vale 100% do próprio voto final — o último snapshot dele. ' +
              'Entram os <span style="color: #ecebe6;">' + nMaduros + '</span> papers com ' + IDADE_FINAL + ' dias ou mais; ' +
              (nNovos ? '<span style="color: #6d7178;">' + nNovos + ' mais novos ficam de fora, porque o final deles ainda está subindo.</span>' : '') +
              ' Só idades com pelo menos ' + MIN_AMOSTRA + ' papers medidos.</div>' +
          '</div>' +
          '<div style="padding-top: 5px;">' + chaveMat + '</div>' +
        '</div>' +
        '<div style="display: grid; grid-template-columns: minmax(0, 1fr) 268px; gap: 26px;">' +
          (idadeFim >= 1
            ? '<div style="display: flex; flex-direction: column; gap: 8px;">' +
                '<div style="display: grid; grid-template-columns: 34px minmax(0, 1fr); gap: 10px;">' +
                  '<div style="position: relative; height: 232px;">' + eixoMatY + '</div>' +
                  '<div style="position: relative; height: 232px; border-left: 1px solid #333a41; border-bottom: 1px solid #333a41;">' +
                    svgPlano(desenhoMat) +
                    pontosSoltos +
                    marcaEstavel +
                    '<div style="position: absolute; inset: 0; display: flex;">' + celulasMat.join('') + '</div>' +
                  '</div>' +
                '</div>' +
                '<div style="display: grid; grid-template-columns: 34px minmax(0, 1fr); gap: 10px;"><div></div>' +
                  '<div><div style="position: relative; height: 14px;">' + eixoMatX + '</div>' +
                    // o titulo do eixo mora numa linha propria: sobre os ticks
                    // ele apagaria os ultimos dias, que sao os que interessam
                    '<div style="text-align: right; font-size: 10px; letter-spacing: 0.13em; color: #6d7178;">DIAS DESDE O HF DAILY →</div>' +
                  '</div>' +
                '</div>' +
              '</div>'
            /* Dois motivos distintos para o card nao ter curva, e a mensagem
               precisa separa-los: ou nenhuma idade chegou ao minimo de
               amostra, ou chegou uma so - e uma idade sozinha nao desenha
               linha. Dizer "amostra insuficiente" no segundo caso e falso. */
            : '<div style="padding: 90px 0; text-align: center; font-size: 12.5px; color: #6d7178;">' +
                (idadeFim < 0
                  ? 'Amostra insuficiente: nenhuma idade com ' + MIN_AMOSTRA + ' papers de ' + IDADE_FINAL + ' dias ou mais neste recorte.'
                  : 'Só o dia 0 reúne ' + MIN_AMOSTRA + ' papers ou mais neste recorte: uma idade sozinha não desenha curva.') +
              '</div>') +
          '<div style="display: flex; flex-direction: column; gap: 12px; border-left: 1px solid #242a30; padding-left: 22px;">' +
            '<div style="font-size: 10px; font-weight: 600; letter-spacing: 0.14em; color: #8b8f96;">MAIOR VELOCIDADE RECENTE</div>' +
            '<div style="display: flex; flex-direction: column; gap: 13px;">' + listaVel + '</div>' +
          '</div>' +
        '</div>' +
      '</div>'
    );

    /* ── upvotes no HF × stars no GitHub ────────────────────────────────── */
    /* So papers com repositorio. `gs = 0` e um repositorio sem estrela nenhuma
       e continua no grafico, na base do eixo; paper sem repositorio nao tem
       coordenada Y e fica de fora - as duas coisas parecem "zero" e nao sao. */
    var comRepo = sel.filter(function (p) { return p.oa === 1; });
    var semRepo = sel.length - comRepo.length;
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
      ['estrito', 'amplo', 'fora'].map(function (v) {
        return '<div style="display: flex; align-items: center; gap: 6px; font-size: 11.5px; color: #a8a49b;">' +
          '<span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: ' + cor(v) + ';"></span>' + v + '</div>';
      }).join('') +
      '<div style="display: flex; align-items: center; gap: 6px; font-size: 11.5px; color: #a8a49b;">' +
        '<span style="display: inline-block; width: 8px; height: 8px; background: #8b8f96; transform: rotate(45deg);"></span>com página do projeto</div>' +
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

    /* ══════════════ 05 · FICHAS ══════════════ */
    out.push(secao('05', 'Por que passou, e o que ficou registrado'));

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

    var limite = COMPACTA ? 10 : 16;
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
        '<div class="row"' + ev('c', function () { setState({ aberta: aberta ? null : p.id }); }) + ' style="display: grid; grid-template-columns: 78px minmax(0, 1fr) 210px 66px 60px; gap: 14px; padding: 14px 24px; align-items: center;">' +
          '<span style="' + badge + '">' + esc(p.v) + '</span>' +
          '<div style="display: flex; flex-direction: column; gap: 3px; min-width: 0;">' +
            '<span style="font-size: 13.5px; color: #ecebe6; line-height: 1.3; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">' + esc(p.t) + '</span>' +
            '<span style="font-size: 11.5px; color: #6d7178; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">' + esc(p.org || '—') + (p.f ? '' : ' · sem ficha') + '</span>' +
          '</div>' +
          '<span style="font-size: 11.5px; color: #8b8f96; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">' + esc(parArea(p)) + '</span>' +
          '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 12.5px; color: #ecebe6; text-align: right;">' + p.u + '</span>' +
          '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 11.5px; color: #6d7178; text-align: right;">' + diaCurto(p.d) + '</span>' +
        '</div>' + corpo +
        '</div>';
    }).join('');

    var chipsOrdem = [
      { label: 'votos', valor: 'votos' }, { label: 'dia', valor: 'dia' }, { label: 'título', valor: 'titulo' }
    ].map(function (c) {
      var on = s.ordem === c.valor;
      var menor = ' font-size: 11.5px; padding: 6px 12px;';
      return '<div class="' + (on ? 'chip chip-on' : 'chip') + '"' + ev('c', function () { setState({ ordem: c.valor }); }) +
        ' style="' + (on ? pillOn : pill(false)) + menor + '">' + c.label + '</div>';
    }).join('');

    out.push(
      '<div class="card" style="overflow: hidden;">' +
        '<div style="display: flex; justify-content: space-between; align-items: flex-end; gap: 28px; padding: 22px 24px 18px;">' +
          '<div style="display: flex; flex-direction: column; gap: 5px;">' +
            '<div style="font-family: Newsreader, Georgia, serif; font-size: 26px; font-weight: 400; line-height: 1.1; color: #f5f3ee;">Aprovados, decisão e ficha</div>' +
            '<div style="font-size: 12.5px; color: #8b8f96;">Clique numa linha para abrir o porquê da decisão — e a ficha inteira, quando o Estágio B chegou a escrevê-la.</div>' +
          '</div>' +
          '<div style="display: flex; align-items: center; gap: 9px;">' +
            '<span style="font-size: 10px; font-weight: 600; letter-spacing: 0.14em; color: #8b8f96;">ORDENAR</span>' + chipsOrdem +
          '</div>' +
        '</div>' +
        '<div style="display: grid; grid-template-columns: 78px minmax(0, 1fr) 210px 66px 60px; gap: 14px; padding: 11px 24px; border-top: 1px solid #242a30; border-bottom: 1px solid #242a30; background: #131619; font-size: 10.5px; font-weight: 600; letter-spacing: 0.14em; color: #8b8f96;">' +
          '<span>CRITÉRIO</span><span>TÍTULO</span><span>ÁREA</span><span style="text-align: right;">VOTOS</span><span style="text-align: right;">DIA</span>' +
        '</div>' +
        linhasFicha +
        (linhasFicha ? '' : '<div style="padding: 54px 24px; text-align: center; font-size: 13px; color: #6d7178;">Nenhum paper aprovado dentro deste recorte.</div>') +
        '<div style="padding: 15px 24px; font-family: \'IBM Plex Mono\', monospace; font-size: 11px; color: #6d7178;">' +
          (aprovadosCard.length > limite
            ? 'Mostrando ' + limite + ' de ' + aprovadosCard.length + ' aprovados — refine o recorte para ver o resto.'
            : aprovadosCard.length + ' aprovado(s) neste recorte.') +
        '</div>' +
      '</div>'
    );

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
