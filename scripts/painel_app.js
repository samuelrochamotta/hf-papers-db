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

  var ACCENT = '#d9a441';
  var COMPACTA = false;

  var root = document.getElementById('painel');
  var elTip = document.getElementById('tip');

  var state = {
    aba: 'janela',
    diasSel: [], vereditos: [], areas: [], topicos: [], orgs: [],
    busca: '', ordem: 'votos', aberta: null,
    menu: null, buscaMenu: '',
    perSel: null, abertaH: null
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

  function setState(patch) {
    for (var k in patch) if (Object.prototype.hasOwnProperty.call(patch, k)) state[k] = patch[k];
    render();
  }

  /* ── cores das series (dataviz, coluna dark; hex literais) ─────────────── */
  function cor(v) { return v === 'estrito' ? '#3987e5' : v === 'amplo' ? '#d95926' : '#6b7480'; }
  function corTexto(v) { return v === 'estrito' ? '#6aa9ee' : v === 'amplo' ? '#e8794c' : '#8b8f96'; }

  /* `exceto` deixa uma dimensao de fora: e o que mantem as outras opcoes de um
     seletor visiveis depois que ele ja filtrou (senao marcar a 2a area pelo
     grafico ficaria impossivel - a 1a teria apagado as demais barras). */
  function filtrados(exceto) {
    var s = state;
    var q = (s.busca || '').trim().toLowerCase();
    return DADOS.papers.filter(function (p) {
      if (s.diasSel.length && s.diasSel.indexOf(p.d) < 0) return false;
      if (s.vereditos.length && s.vereditos.indexOf(p.v) < 0) return false;
      // dentro de cada dimensao a selecao e OR; entre dimensoes, AND
      if (exceto !== 'areas' && s.areas.length && s.areas.indexOf(p.a) < 0) return false;
      if (exceto !== 'topicos' && s.topicos.length && !s.topicos.some(function (t) { return p.tp.indexOf(t) >= 0; })) return false;
      if (exceto !== 'orgs' && s.orgs.length) {
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
    var novo = { aberta: null };
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

  function mediana(xs) {
    if (!xs.length) return 0;
    var o = xs.slice().sort(function (a, b) { return a - b; });
    var m = Math.floor(o.length / 2);
    return o.length % 2 ? o[m] : Math.round((o[m - 1] + o[m]) / 2);
  }
  function diaCurto(iso) {
    if (!iso) return '—';
    var p = iso.split('-');
    return p[2] + '/' + p[1];
  }
  function pct(n, total) { return total ? Math.round((n / total) * 100) : 0; }
  function escalaLog(v, max) {
    if (max <= 0) return 0;
    return (Math.log(1 + v) / Math.log(1 + max)) * 100;
  }

  /* pilula de filtro: arredondada, com estados legiveis no escuro */
  function pill(on, corOn) {
    var base = 'display: inline-flex; align-items: center; gap: 0; font-size: 12.5px; line-height: 1; padding: 8px 15px; border-radius: 100px; white-space: nowrap;';
    if (!on) return base + ' background: #1b1f23; border: 1px solid #2b3138; color: #a8a49b;';
    if (corOn) return base + ' background: ' + corOn + '26; border: 1px solid ' + corOn + '; color: ' + corOn + '; font-weight: 500;';
    return base + ' background: #d9a441; border: 1px solid #d9a441; color: #14161a; font-weight: 600;';
  }

  var SVG_CHEVRON = '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 9l7 7 7-7"></path></svg>';
  var SVG_CHECK = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12.5l5.5 5.5L20 7"></path></svg>';

  /* Menu suspenso de selecao multipla (dia, area, topico, organizacao).
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
    // senao marcar tres topicos exigiria reabrir o menu tres vezes
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
        var novo = { aberta: null };
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
      { valor: 'janela', label: 'Janela', nota: DADOS.papers.length + ' papers · ' + DADOS.janela + 'd' },
      { valor: 'historico', label: 'Registro histórico', nota: (DADOS.hall || []).length + ' trimestres' }
    ];
    return '<div style="display: flex; gap: 30px; margin-top: 26px; border-bottom: 1px solid #242a30;">' +
      itens.map(function (i) {
        var on = s.aba === i.valor;
        return '<div class="aba"' + ev('c', function () { setState({ aba: i.valor, menu: null, aberta: null, abertaH: null }); }) +
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
            DADOS.diasHall + ' dias — a mesma marca em que o pipeline para de reconsultar os votos dele. Até lá ele está na aba <em style="color: #a8a49b;">Janela</em>, com o número de votos ainda vivo.</div>' +
        '</div>');
      return out.join('');
    }

    var atual = null;
    hall.forEach(function (h) { if (h.per === s.perSel) atual = h; });
    if (!atual) atual = hall[0];

    /* ── nota de leitura ────────────────────────────────────────────────── */
    out.push(
      '<div class="card" style="margin: 26px 0 30px; padding: 20px 24px; display: flex; align-items: flex-start; gap: 16px;">' +
        '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="' + ACCENT + '" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" style="flex: none; margin-top: 2px;"><circle cx="12" cy="12" r="9"></circle><path d="M12 8v5"></path><path d="M12 16.5v.01"></path></svg>' +
        '<div style="font-size: 12.5px; line-height: 1.7; color: #a8a49b; max-width: 880px; text-wrap: pretty;">' +
          'A aba <em style="color: #ecebe6; font-style: normal;">Janela</em> mostra os últimos ' + DADOS.janela + ' dias. Aqui ficam, de cada trimestre já fora dela, os mais votados pela comunidade — ' +
          'os dez aprovados com a ficha inteira e os dez que o pipeline descartou. ' +
          '<span style="color: #6d7178;">Nada é apagado em lugar nenhum: a série completa continua no banco e nos Parquet. Os votos aqui estão congelados porque o refresh para de reconsultá-los aos ' + DADOS.diasHall + ' dias — medido, eles já haviam parado de se mexer no segundo dia.</span>' +
        '</div>' +
      '</div>'
    );

    /* ── seletor de trimestre ───────────────────────────────────────────── */
    var chipsPer = hall.map(function (h) {
      var on = h.per === atual.per;
      return '<div class="' + (on ? 'chip chip-on' : 'chip') + '"' +
        ev('c', function () { setState({ perSel: h.per, abertaH: null }); }) +
        ' style="' + (on ? pillOnGlobal() : pill(false)) + '">' +
        esc(h.rot) +
        '<span style="margin-left: 7px; font-family: \'IBM Plex Mono\', monospace; font-size: 11px; opacity: 0.62;">' + h.n + '</span>' +
        (h.cons ? '<span style="margin-left: 8px; font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; opacity: 0.7;">consolidando</span>' : '') +
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
          'em consolidação — parte do trimestre ainda está na janela</span>'
      : '<span style="font-size: 11.5px; color: #6d7178;">período fechado · ranking definitivo</span>';

    /* ── 01 · os dez aprovados mais votados ─────────────────────────────── */
    out.push(secao('01', 'Os mais votados entre os aprovados'));

    var linhasAp = atual.ap.map(function (p, i) {
      var aberta = s.abertaH === p.id;
      var badge = 'display: inline-flex; align-items: center; justify-content: center; font-size: 10.5px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; padding: 4px 0; border-radius: 100px; color: ' + cor(p.v) + '; background: ' + cor(p.v) + '1f; border: 1px solid ' + cor(p.v) + '4d;';

      var corpo = '';
      if (aberta) {
        corpo = '<div style="padding: 10px 24px 30px;">';
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
            '<span style="font-size: 11.5px; color: #6d7178;">' + esc(p.tp.join(' · ')) + '</span>' +
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
          '<span style="font-size: 11.5px; color: #8b8f96; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">' + esc(p.a || '—') + '</span>' +
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
            '<div style="font-size: 12.5px; color: #8b8f96;">' + atual.ap.length + ' de ' + atual.na + ' aprovados, ordenados por voto da comunidade. Clique para abrir a ficha inteira.</div>' +
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
              ? '<span style="font-size: 10.5px; font-family: \'IBM Plex Mono\', monospace; color: #8b8f96; background: #1d2226; border: 1px solid #2b3138; border-radius: 100px; padding: 3px 9px;">' + esc(p.rf) + '</span>'
              : '') +
            '<span style="font-size: 11.5px; color: #6d7178;">' + esc(p.org || '—') + ' · ' + diaCurto(p.d) + '</span>' +
          '</div>' +
          (p.h
            ? '<div style="font-size: 12.5px; font-style: italic; color: #6d7178;">Veredito herdado dos digests históricos — o backfill não registra justificativa por paper.</div>'
            : '<div style="font-family: Newsreader, Georgia, serif; font-size: 15px; font-weight: 300; line-height: 1.6; color: #a8a49b; text-wrap: pretty;">' + esc(p.j) + '</div>') +
        '</div>' +
        '</div>';
    }).join('');

    out.push(
      '<div class="card" style="overflow: hidden; margin-bottom: 34px;">' +
        '<div style="display: flex; justify-content: space-between; align-items: flex-end; gap: 28px; padding: 22px 24px 18px;">' +
          '<div style="display: flex; flex-direction: column; gap: 5px;">' +
            '<div style="font-family: Newsreader, Georgia, serif; font-size: 26px; font-weight: 400; line-height: 1.1; color: #f5f3ee;">O outro lado do voto</div>' +
            '<div style="font-size: 12.5px; color: #8b8f96;">Os ' + atual.de.length + ' mais votados entre os ' + atual.nd + ' descartados do trimestre, com a regra e a justificativa que os tiraram.</div>' +
          '</div>' +
          '<span style="font-size: 11.5px; color: #6d7178; text-align: right; max-width: 300px; line-height: 1.5;">Upvote não entra em decisão nenhuma do pipeline. Esta lista existe para medir a divergência, não para reabrir o veredito.</span>' +
        '</div>' +
        linhasDe +
        (linhasDe ? '' : '<div style="padding: 54px 24px; text-align: center; font-size: 13px; color: #6d7178;">Nenhum descarte neste trimestre.</div>') +
      '</div>'
    );

    var somaAp = 0, somaDe = 0;
    hall.forEach(function (h) { somaAp += h.ap.length; somaDe += h.de.length; });
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
    var chipsVeredito = ['estrito', 'amplo', 'fora'].map(function (v) {
      var on = s.vereditos.indexOf(v) >= 0;
      var n = todos.filter(function (p) { return p.v === v; }).length;
      return '<div class="' + (on ? 'chip chip-on' : 'chip') + '"' + ev('c', function () { alternaLista('vereditos', v); }) + ' style="' + pill(on, cor(v)) + '">' +
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

    var contaTop = {};
    todos.forEach(function (p) { p.tp.forEach(function (t) { contaTop[t] = (contaTop[t] || 0) + 1; }); });
    var itensTopico = DADOS.topicos.map(function (t) {
      return { valor: t.t, label: t.t, n: contaTop[t.t] || 0 };
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
    if (s.topicos.length) ativos.push(s.topicos.length === 1 ? s.topicos[0] : s.topicos.length + ' tópicos');
    if (s.orgs.length) ativos.push(s.orgs.length === 1 ? (s.orgs[0] === '__sem-org__' ? 'sem organização' : s.orgs[0]) : s.orgs.length + ' organizações');
    if (s.busca) ativos.push('"' + s.busca + '"');
    var resumoFiltro = ativos.length ? total + ' de ' + todos.length + ' · ' + ativos.join(' · ') : todos.length + ' papers, sem recorte';

    var estiloLimpar = 'display: inline-flex; align-items: center; gap: 7px; font-size: 12px; padding: 8px 14px; border-radius: 100px; background: ' +
      (ativos.length ? 'rgba(217,164,65,0.12)' : '#1b1f23') + '; border: 1px solid ' + (ativos.length ? 'rgba(217,164,65,0.5)' : '#2b3138') +
      '; color: ' + (ativos.length ? ACCENT : '#6d7178') + ';';

    // z-index 90 na linha do menu aberto: sem isso a cortina de fechar (80)
    // ficaria por cima do proprio menu e nenhum item seria clicavel.
    var zDia = s.menu === 'diasSel' ? 90 : 4;
    var zTema = (s.menu === 'areas' || s.menu === 'topicos') ? 90 : 2;
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
                ev('i', function (e) { setState({ busca: e.target.value, aberta: null }); }) +
                ' placeholder="buscar título ou organização" style="font-family: \'Instrument Sans\', sans-serif; font-size: 13px; padding: 9px 14px 9px 36px; width: 268px; border: 1px solid #2b3138; border-radius: 100px; background: #1b1f23; color: #ecebe6; outline: none;">' +
            '</div>' +
            '<div class="chip"' + ev('c', function () { setState({ diasSel: [], vereditos: [], areas: [], topicos: [], orgs: [], busca: '', aberta: null, menu: null, buscaMenu: '' }); }) + ' style="' + estiloLimpar + '">' +
              '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"></path></svg><span>limpar</span>' +
            '</div>' +
          '</div>' +
        '</div>' +
        '<div style="height: 1px; background: #242a30;"></div>' +
        linhaFiltro('DIA', zDia, montaMenu('DIA', 'diasSel', itensDia, { todos: 'todos os dias' })) +
        '<div style="display: grid; grid-template-columns: 74px minmax(0, 1fr); gap: 16px; align-items: start; position: relative; z-index: 3;">' +
          '<div style="font-size: 10px; font-weight: 600; letter-spacing: 0.14em; color: #8b8f96; padding-top: 9px;">VEREDITO</div>' +
          '<div style="display: flex; gap: 7px; flex-wrap: wrap;">' + chipsVeredito + '</div>' +
        '</div>' +
        linhaFiltro('TEMA', zTema,
          montaMenu('ÁREA', 'areas', itensArea, { todos: 'todas' }) +
          montaMenu('TÓPICO', 'topicos', itensTopico, { todos: 'todos' })) +
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
      { rotulo: 'aprovados', valor: aprovados, sufixo: pct(aprovados, total) + '%', cor: '#6aa9ee', marca: marca('#3987e5'), nota: conta.estrito + ' estrito · ' + conta.amplo + ' amplo' },
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

    /* ══════════════ 01 · VOLUME ══════════════ */
    out.push(secao('01', 'Volume e corte'));

    var porDia = {};
    dias.forEach(function (d) { porDia[d] = { fora: 0, amplo: 0, estrito: 0, total: 0 }; });
    sel.forEach(function (p) { if (porDia[p.d]) { porDia[p.d][p.v]++; porDia[p.d].total++; } });
    var maxDia = Math.max.apply(null, dias.map(function (d) { return porDia[d].total; }).concat([1]));

    var legenda = ['estrito', 'amplo', 'fora'].map(function (v) {
      return '<div style="display: flex; align-items: center; gap: 6px; font-size: 11.5px; color: #a8a49b; white-space: nowrap;">' +
        '<span style="display: inline-block; width: 8px; height: 8px; border-radius: 2px; background: ' + cor(v) + ';"></span>' + v + '</div>';
    }).join('');

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
          ' style="width: 100%; height: ' + ((c.total / maxDia) * 100) + '%; display: flex; flex-direction: column-reverse; gap: 2px; min-height: 4px;">' + segs + '</div>' +
        '</div>';
    }).join('');
    var rotulosDia = dias.map(function (d) {
      return '<span style="flex: 1; text-align: center; font-family: \'IBM Plex Mono\', monospace; font-size: 11px; color: #6d7178;">' + diaCurto(d) + '</span>';
    }).join('');

    /* ── perfil do aprovado ─────────────────────────────────────────────── */
    var grupoAprov = sel.filter(function (p) { return p.v !== 'fora'; });
    var grupoFora = sel.filter(function (p) { return p.v === 'fora'; });
    /* Aqui "aprovados" e estrito + amplo, nao uma das duas categorias - por isso
       nao pode usar nem o azul do estrito nem o laranja do amplo. Aqua e o slot
       seguinte do catalogo e separa dos dois e do cinza (validado all-pairs). */
    var corAprov = '#1baf7a';
    var corAprovTexto = '#4ecfa2';
    var perfilLegenda = [
      { label: 'aprovados', n: grupoAprov.length, cor: corAprov },
      { label: 'descartados', n: grupoFora.length, cor: '#6b7480' }
    ].map(function (g) {
      return '<div style="display: flex; align-items: center; gap: 7px; font-size: 11.5px; color: #a8a49b; white-space: nowrap;">' +
        '<span style="display: inline-block; width: 8px; height: 8px; border-radius: 2px; background: ' + g.cor + ';"></span>' + g.label +
        '<span style="font-family: \'IBM Plex Mono\', monospace; color: #6d7178;">' + g.n + '</span></div>';
    }).join('');

    var metricas = [
      { rotulo: 'repositório aberto', fn: function (p) { return p.oa === 1; } },
      { rotulo: 'página do projeto', fn: function (p) { return p.pp === 1; } },
      { rotulo: 'organização identificada', fn: function (p) { return !!p.org; } },
      { rotulo: 'autor verificado no HF', fn: function (p) { return p.nv > 0; } },
      { rotulo: 'time pequeno (1–2 autores)', fn: function (p) { return p.na > 0 && p.na <= 2; } }
    ];

    var perfil = metricas.map(function (m) {
      var pa = grupoAprov.length ? Math.round((grupoAprov.filter(m.fn).length / grupoAprov.length) * 100) : 0;
      var pf = grupoFora.length ? Math.round((grupoFora.filter(m.fn).length / grupoFora.length) * 100) : 0;
      /* `corPct` e o passo de texto da mesma serie da barra: le como a cor da
         barra, mas com contraste suficiente a 11.5px sobre o fundo do card. */
      function barra(pctv, c, corPct, rotulo, n, base) {
        return '<div' +
          ev('e', mostraTip(rotulo + ' · ' + m.rotulo, base ? pctv + '% de ' + n + ' papers' : 'nenhum paper neste grupo')) +
          ev('l', escondeTip()) +
          ' style="display: grid; grid-template-columns: minmax(0, 1fr) 40px; gap: 10px; align-items: center; cursor: pointer;">' +
          '<div style="height: 9px; background: #1d2226; border-radius: 2px; overflow: hidden;">' +
            '<div class="bar" style="height: 100%; width: ' + (base ? pctv : 0) + '%; background: ' + c + '; border-radius: 2px;"></div>' +
          '</div>' +
          '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 11.5px; font-weight: 500; color: ' + (base ? corPct : '#4a5058') + '; text-align: right;">' + (base ? pctv + '%' : '—') + '</span>' +
          '</div>';
      }
      return '<div style="display: flex; flex-direction: column; gap: 7px;">' +
        '<div style="font-size: 12.5px; color: #ecebe6;">' + esc(m.rotulo) + '</div>' +
        barra(pa, corAprov, corAprovTexto, 'aprovados', grupoAprov.length, grupoAprov.length > 0) +
        barra(pf, '#6b7480', '#9aa1a9', 'descartados', grupoFora.length, grupoFora.length > 0) +
        '</div>';
    }).join('');

    out.push(
      '<div style="display: grid; grid-template-columns: minmax(0, 1.65fr) minmax(0, 1fr); gap: 14px; margin-bottom: 34px;">' +
        '<div class="card" style="padding: 22px 24px 20px; display: flex; flex-direction: column; gap: 20px;">' +
          '<div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 18px;">' +
            '<div style="display: flex; flex-direction: column; gap: 5px;">' +
              '<div style="font-family: Newsreader, Georgia, serif; font-size: 26px; font-weight: 400; line-height: 1.1; color: #f5f3ee;">O lote diário e o que sobrou dele</div>' +
              '<div style="font-size: 12.5px; color: #8b8f96;">Papers por dia de publicação no HF, empilhados por veredito.</div>' +
            '</div>' +
            '<div style="display: flex; gap: 15px; padding-top: 5px;">' + legenda + '</div>' +
          '</div>' +
          '<div style="display: flex; align-items: flex-end; gap: 12px; height: 214px; border-bottom: 1px solid #333a41;">' + barrasDia + '</div>' +
          '<div style="display: flex; gap: 12px;">' + rotulosDia + '</div>' +
        '</div>' +
        '<div class="card" style="padding: 22px 24px 20px; display: flex; flex-direction: column; gap: 18px;">' +
          '<div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 16px;">' +
            '<div style="display: flex; flex-direction: column; gap: 5px;">' +
              '<div style="font-family: Newsreader, Georgia, serif; font-size: 26px; font-weight: 400; line-height: 1.1; color: #f5f3ee;">Perfil do aprovado</div>' +
              '<div style="font-size: 12.5px; color: #8b8f96;">Quanto de cada grupo carrega o atributo, em % do próprio grupo.</div>' +
            '</div>' +
            '<div style="display: flex; flex-direction: column; gap: 7px; padding-top: 3px;">' + perfilLegenda + '</div>' +
          '</div>' +
          '<div style="display: flex; flex-direction: column; gap: 15px;">' + perfil + '</div>' +
        '</div>' +
      '</div>'
    );

    /* ══════════════ 02 · VOCABULÁRIO ══════════════ */
    out.push(secao('02', 'Vocabulário controlado'));

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

    // empilhado por veredito, como as areas: uma barra de cor unica esconderia
    // que a composicao muda muito de um topico para outro
    var topMap = {};
    filtrados('topicos').forEach(function (p) {
      p.tp.forEach(function (t) {
        if (!topMap[t]) topMap[t] = { fora: 0, amplo: 0, estrito: 0, total: 0 };
        topMap[t][p.v]++; topMap[t].total++;
      });
    });
    var topsOrd = Object.keys(topMap).sort(function (x, y) { return topMap[y].total - topMap[x].total; }).slice(0, 10);
    var maxTop = Math.max.apply(null, topsOrd.map(function (t) { return topMap[t].total; }).concat([1]));
    var barrasTopico = topsOrd.map(function (t) {
      var c = topMap[t];
      var on = s.topicos.indexOf(t) >= 0;
      var segs = ['estrito', 'amplo', 'fora'].filter(function (v) { return c[v] > 0; }).map(function (v) {
        return '<div class="bar" style="flex: ' + c[v] + '; background: ' + cor(v) + ';"></div>';
      }).join('');
      return '<div' + ev('c', function () { alternaLista('topicos', t); }) +
        ev('e', mostraTip(t, c.estrito + ' estrito · ' + c.amplo + ' amplo · ' + c.fora + ' fora')) +
        ev('l', escondeTip()) +
        ' style="display: grid; grid-template-columns: 182px minmax(0, 1fr) 36px; gap: 12px; align-items: center; cursor: pointer;">' +
        '<span style="font-size: 12.5px; color: ' + (on ? ACCENT : '#a8a49b') + '; font-weight: ' + (on ? '600' : '400') + '; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">' + esc(t) + '</span>' +
        '<div style="height: 12px; background: #1d2226; border-radius: 2px; overflow: hidden;">' +
          '<div style="display: flex; height: 100%; width: ' + ((c.total / maxTop) * 100) + '%; gap: 2px; min-width: 3px;">' + segs + '</div>' +
        '</div>' +
        '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 11.5px; color: #8b8f96; text-align: right;">' + c.total + '</span>' +
        '</div>';
    }).join('');

    out.push(
      '<div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; margin-bottom: 34px;">' +
        '<div class="card" style="padding: 22px 24px 20px; display: flex; flex-direction: column; gap: 18px;">' +
          '<div style="display: flex; flex-direction: column; gap: 5px;">' +
            '<div style="font-family: Newsreader, Georgia, serif; font-size: 26px; font-weight: 400; line-height: 1.1; color: #f5f3ee;">Área primária</div>' +
            '<div style="font-size: 12.5px; color: #8b8f96;">A LLM escolhe de uma lista fechada — nunca inventa rótulo. Clique para filtrar.</div>' +
          '</div>' +
          '<div style="display: flex; flex-direction: column; gap: 13px;">' + barrasArea + '</div>' +
        '</div>' +
        '<div class="card" style="padding: 22px 24px 20px; display: flex; flex-direction: column; gap: 18px;">' +
          '<div style="display: flex; flex-direction: column; gap: 5px;">' +
            '<div style="font-family: Newsreader, Georgia, serif; font-size: 26px; font-weight: 400; line-height: 1.1; color: #f5f3ee;">Tópicos mais atribuídos</div>' +
            '<div style="font-size: 12.5px; color: #8b8f96;">Até cinco por paper. Clique para filtrar o painel inteiro.</div>' +
          '</div>' +
          '<div style="display: flex; flex-direction: column; gap: 11px;">' + barrasTopico + '</div>' +
        '</div>' +
      '</div>'
    );

    /* ══════════════ 03 · A REGRA DO UPVOTE ══════════════ */
    out.push(secao('03', 'Distribuição de votos'));

    var maxUp = Math.max.apply(null, sel.map(function (p) { return p.u; }).concat([1]));
    var faixas = ['estrito', 'amplo', 'fora'].map(function (v) {
      var grupo = sel.filter(function (p) { return p.v === v; });
      var med = mediana(grupo.map(function (p) { return p.u; }));
      var pontos = grupo.map(function (p, i) {
        return '<div class="mark"' +
          ev('e', mostraTip(p.t, p.u + ' votos · ' + p.v + ' · ' + diaCurto(p.d))) +
          ev('l', escondeTip()) +
          ' style="position: absolute; left: ' + escalaLog(p.u, maxUp) + '%; top: ' + (12 + ((i * 37) % 34)) + '%; width: 7px; height: 7px; margin-left: -3.5px; border-radius: 50%; background: ' + cor(v) + '; opacity: 0.62;"></div>';
      }).join('');
      return '<div style="display: grid; grid-template-columns: 96px minmax(0, 1fr); gap: 16px; align-items: center;">' +
        '<div style="display: flex; align-items: center; gap: 8px; font-size: 12.5px; color: #ecebe6;">' +
          '<span style="display: inline-block; width: 8px; height: 8px; border-radius: 2px; background: ' + cor(v) + ';"></span>' + v + '</div>' +
        '<div style="position: relative; height: 62px; border-left: 1px solid #333a41; border-bottom: 1px solid #1d2226;">' + pontos +
          '<div style="position: absolute; left: ' + escalaLog(med, maxUp) + '%; top: -2px; bottom: -2px; width: 2px; background: ' + cor(v) + ';"></div>' +
        '</div>' +
        '</div>';
    }).join('');

    // ticks derivados de maxUp: fixa-los faria o rotulo sair do container assim
    // que um recorte baixasse o maximo (escalaLog(160, 50) = 129%)
    var ticks = [0];
    [5, 20, 60, 160, 400].forEach(function (v) { if (v < maxUp * 0.82) ticks.push(v); });
    ticks.push(maxUp);
    var eixoUpvotes = ticks.map(function (v) {
      return '<span style="position: absolute; left: ' + escalaLog(v, maxUp) + '%; transform: translateX(-50%); font-family: \'IBM Plex Mono\', monospace; font-size: 11px; color: #6d7178;">' + v + '</span>';
    }).join('');
    var medianas = ['estrito', 'amplo', 'fora'].map(function (v) {
      var g = sel.filter(function (p) { return p.v === v; });
      return '<div style="display: flex; flex-direction: column; gap: 4px;">' +
        '<span style="font-size: 10.5px; letter-spacing: 0.14em; color: #8b8f96;">MEDIANA ' + v + '</span>' +
        '<span style="font-family: Newsreader, Georgia, serif; font-size: 30px; font-weight: 400; line-height: 1; color: ' + corTexto(v) + ';">' + mediana(g.map(function (p) { return p.u; })) + '</span>' +
        '</div>';
    }).join('');

    out.push(
      '<div class="card" style="padding: 24px 26px 24px; margin-bottom: 34px; display: flex; flex-direction: column; gap: 22px;">' +
        '<div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 32px;">' +
          '<div style="display: flex; flex-direction: column; gap: 7px; max-width: 700px;">' +
            '<div style="font-family: Newsreader, Georgia, serif; font-size: 30px; font-weight: 400; line-height: 1.12; color: #f5f3ee;">Votos por veredito</div>' +
            '<div style="font-size: 12.5px; color: #8b8f96;">Um ponto por paper, na escala logarítmica de votos. A linha vertical marca a mediana da faixa.</div>' +
          '</div>' +
          '<div style="display: flex; gap: 26px; text-align: right;">' + medianas + '</div>' +
        '</div>' +
        '<div style="display: flex; flex-direction: column; gap: 4px;">' + faixas +
          '<div style="display: grid; grid-template-columns: 96px minmax(0, 1fr); gap: 16px;"><div></div>' +
            '<div style="position: relative; height: 20px;">' + eixoUpvotes + '</div>' +
          '</div>' +
        '</div>' +
      '</div>'
    );

    /* ══════════════ 04 · ADOÇÃO ══════════════ */
    out.push(secao('04', 'Sinais de adoção'));

    var maxCom = Math.max.apply(null, sel.map(function (p) { return p.c; }).concat([1]));
    var dispersao = sel.map(function (p) {
      var d = p.oa ? 9 : 7;
      return '<div class="mark"' +
        ev('e', mostraTip(p.t, p.u + ' votos · ' + p.c + ' comentários · ' + p.v)) +
        ev('l', escondeTip()) +
        ' style="position: absolute; left: ' + escalaLog(p.u, maxUp) + '%; bottom: ' + escalaLog(p.c, maxCom) + '%; width: ' + d + 'px; height: ' + d + 'px; margin-left: -' + (d / 2) + 'px; margin-bottom: -' + (d / 2) + 'px; border-radius: 50%; ' +
        (p.oa ? 'background: ' + cor(p.v) + '; opacity: 0.72;' : 'background: transparent; border: 1.5px solid ' + cor(p.v) + '; opacity: 0.8;') + '"></div>';
    }).join('');
    var gradeDispersao = [25, 50, 75].map(function (g) {
      return '<div style="position: absolute; left: 0; right: 0; bottom: ' + g + '%; height: 1px; background: #1d2226;"></div>';
    }).join('');

    var bruta = [];
    sel.forEach(function (p) {
      var serie = DADOS.serie[p.id];
      if (!serie || serie.length < 2) return;
      var ini = serie[0][1], fim = serie[serie.length - 1][1];
      if (ini === null || fim === null || fim <= ini) return;
      bruta.push({ p: p, ini: ini, fim: fim, delta: fim - ini });
    });
    bruta.sort(function (a, b) { return b.delta - a.delta; });
    var topo = bruta.slice(0, COMPACTA ? 6 : 9);
    var maxFim = Math.max.apply(null, topo.map(function (t) { return t.fim; }).concat([1]));
    var tracao = topo.map(function (t) {
      var x1 = (t.ini / maxFim) * 100, x2 = (t.fim / maxFim) * 100;
      return '<div' +
        ev('e', mostraTip(t.p.t, t.ini + ' → ' + t.fim + ' votos (+' + t.delta + ') · ' + t.p.v)) +
        ev('l', escondeTip()) +
        ' style="display: grid; grid-template-columns: minmax(0, 1fr) 66px; gap: 14px; align-items: center; cursor: pointer;">' +
        '<div style="display: flex; flex-direction: column; gap: 5px;">' +
          '<span style="font-size: 12.5px; color: #ecebe6; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: block;">' + esc(t.p.t) + '</span>' +
          '<div style="position: relative; height: 12px;">' +
            '<div style="position: absolute; left: ' + x1 + '%; width: ' + (x2 - x1) + '%; top: 5px; height: 2px; background: ' + cor(t.p.v) + '; opacity: 0.45;"></div>' +
            '<div style="position: absolute; left: ' + x1 + '%; top: 2px; width: 8px; height: 8px; margin-left: -4px; border-radius: 50%; background: #16191c; border: 1.5px solid ' + cor(t.p.v) + ';"></div>' +
            '<div style="position: absolute; left: ' + x2 + '%; top: 1px; width: 10px; height: 10px; margin-left: -5px; border-radius: 50%; background: ' + cor(t.p.v) + ';"></div>' +
          '</div>' +
        '</div>' +
        '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 12px; color: #4ec07a; text-align: right;">+' + t.delta + '</span>' +
        '</div>';
    }).join('') || '<div style="font-size: 12.5px; color: #6d7178; padding: 34px 0; text-align: center;">Nenhum paper com dois snapshots dentro deste recorte.</div>';

    out.push(
      '<div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; margin-bottom: 34px;">' +
        '<div class="card" style="padding: 22px 24px 20px; display: flex; flex-direction: column; gap: 16px;">' +
          '<div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 14px;">' +
            '<div style="display: flex; flex-direction: column; gap: 5px;">' +
              '<div style="font-family: Newsreader, Georgia, serif; font-size: 26px; font-weight: 400; line-height: 1.1; color: #f5f3ee;">Votos &amp; comentários</div>' +
              '<div style="font-size: 12.5px; color: #8b8f96;">Cada ponto é um paper. Preenchido = tem repositório aberto.</div>' +
            '</div>' +
          '</div>' +
          '<div style="position: relative; height: 254px; border-left: 1px solid #333a41; border-bottom: 1px solid #333a41;">' + gradeDispersao + dispersao +
            '<span style="position: absolute; left: 10px; top: 7px; font-size: 10.5px; letter-spacing: 0.14em; color: #8b8f96;">COMENTÁRIOS ↑</span>' +
          '</div>' +
          '<div style="display: flex; justify-content: space-between; font-family: \'IBM Plex Mono\', monospace; font-size: 11px; color: #6d7178;">' +
            '<span>0</span><span style="letter-spacing: 0.14em; font-family: \'Instrument Sans\', sans-serif; font-size: 10.5px;">UPVOTES →</span><span>' + maxUp + '</span>' +
          '</div>' +
        '</div>' +
        '<div class="card" style="padding: 22px 24px 20px; display: flex; flex-direction: column; gap: 16px;">' +
          '<div style="display: flex; flex-direction: column; gap: 5px;">' +
            '<div style="font-family: Newsreader, Georgia, serif; font-size: 26px; font-weight: 400; line-height: 1.1; color: #f5f3ee;">Quem pegou tração</div>' +
            '<div style="font-size: 12.5px; color: #8b8f96;">Votos no dia da publicação <span style="font-family: \'IBM Plex Mono\', monospace; color: #a8a49b;">→</span> hoje. Só quem cresceu.</div>' +
          '</div>' +
          '<div style="display: flex; flex-direction: column; gap: 11px;">' + tracao + '</div>' +
        '</div>' +
      '</div>'
    );

    /* ══════════════ 05 · FICHAS ══════════════ */
    out.push(secao('05', 'Fichas dos aprovados'));

    var fichaPorId = {};
    DADOS.fichas.forEach(function (f) { fichaPorId[f.p] = f; });
    var comFichas = sel.filter(function (p) { return p.f && fichaPorId[p.id]; });
    if (s.ordem === 'votos') comFichas.sort(function (a, b) { return b.u - a.u; });
    else if (s.ordem === 'dia') comFichas.sort(function (a, b) { return (b.d || '').localeCompare(a.d || ''); });
    else comFichas.sort(function (a, b) { return a.t.localeCompare(b.t); });

    var limite = COMPACTA ? 10 : 16;
    var linhasFicha = comFichas.slice(0, limite).map(function (p) {
      var f = fichaPorId[p.id];
      var aberta = s.aberta === p.id;
      var badge = 'display: inline-flex; align-items: center; justify-content: center; font-size: 10.5px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; padding: 4px 0; border-radius: 100px; color: ' + cor(p.v) + '; background: ' + cor(p.v) + '1f; border: 1px solid ' + cor(p.v) + '4d;';

      var corpo = '';
      if (aberta) {
        // ordem normativa da ficha: Achado, Padrao Extraido, Implicacao,
        // Exemplo, Ressalva. O Padrao some quando o achado e puramente empirico.
        corpo = '<div style="padding: 10px 24px 30px;">' +
          '<div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 24px 40px;">' +
          camposFicha(f).map(function (c) {
            return '<div style="' + c.wrap + '">' +
              '<div style="' + c.regua + '"></div>' +
              '<div style="' + c.rotuloStyle + '">' + c.rotulo + '</div>' +
              '<div style="' + c.nomeStyle + '">' + esc(c.nome) + '</div>' +
              '<div style="font-family: Newsreader, Georgia, serif; font-size: 16px; font-weight: 300; line-height: 1.68; color: #d5d1c8; text-wrap: pretty;">' + esc(c.texto) + '</div>' +
              '</div>';
          }).join('') +
          '</div>' +
          '<div style="display: flex; gap: 20px; align-items: center; margin-top: 24px; padding-top: 16px; border-top: 1px solid #242a30;">' +
            '<a href="' + esc(p.url) + '" target="_blank" rel="noopener" style="font-family: \'IBM Plex Mono\', monospace; font-size: 12px;">' + esc(p.id) + ' ↗</a>' +
            '<span style="font-size: 11.5px; color: #6d7178;">' + esc(p.tp.join(' · ')) + '</span>' +
          '</div>' +
          '</div>';
      }

      return '<div style="border-bottom: 1px solid #1d2226;">' +
        '<div class="row"' + ev('c', function () { setState({ aberta: aberta ? null : p.id }); }) + ' style="display: grid; grid-template-columns: 78px minmax(0, 1fr) 210px 66px 60px; gap: 14px; padding: 14px 24px; align-items: center;">' +
          '<span style="' + badge + '">' + esc(p.v) + '</span>' +
          '<div style="display: flex; flex-direction: column; gap: 3px; min-width: 0;">' +
            '<span style="font-size: 13.5px; color: #ecebe6; line-height: 1.3; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">' + esc(p.t) + '</span>' +
            '<span style="font-size: 11.5px; color: #6d7178; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">' + esc(p.org || '—') + '</span>' +
          '</div>' +
          '<span style="font-size: 11.5px; color: #8b8f96; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">' + esc(p.a || '—') + '</span>' +
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
            '<div style="font-family: Newsreader, Georgia, serif; font-size: 26px; font-weight: 400; line-height: 1.1; color: #f5f3ee;">Cinco campos, cinco trabalhos distintos</div>' +
            '<div style="font-size: 12.5px; color: #8b8f96;">Clique numa linha para abrir a ficha inteira.</div>' +
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
          (comFichas.length > limite
            ? 'Mostrando ' + limite + ' de ' + comFichas.length + ' fichas — refine o recorte para ver o resto.'
            : comFichas.length + ' ficha(s) neste recorte.') +
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
