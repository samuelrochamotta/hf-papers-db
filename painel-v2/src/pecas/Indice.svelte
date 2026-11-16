<script>
  // Indice de papers. Cada linha e o radar do paper desenrolado: as colunas sao
  // os seis eixos, cada um na sua unidade (votos, nivel de prova, % de ganho,
  // degrau de esforco, artefatos, benchmarks). Ordenar por uma coluna responde
  // a maior parte das perguntas sem abrir nada; "nao lido" vai sempre para o
  // fim, separado, e nunca vira zero.
  // Teclado: a lista e uma grade (uma parada de Tab); setas andam, Enter abre,
  // seta para o lado alcanca o botao de comparar.
  import { tick } from 'svelte';
  import { flip } from 'svelte/animate';
  import MiniRadar from '../lib/MiniRadar.svelte';
  import Icone from '../lib/Icone.svelte';
  import Menu from './Menu.svelte';
  import Degraus from '../lib/Degraus.svelte';
  import { ordenar, realcar, ondeAchou, ORDENS, comDado, ganhoDe, median, sgn, SOL_ROT, SOL_FRASE, ESFORCO, ENTREGA, CAMADA, ART, liberados, intervalo, dataCurta, nBench } from '../lib/dados.js';
  import { corSolidez } from '../lib/tema.js';
  import { estado, abrir, alternaComparar, mov } from '../lib/estado.svelte.js';

  let { papers, faltam = [] } = $props();
  const PAGINA = 50;                 // linhas por vez; "Mostrar mais" traz outras 50
  let paginas = $state(1);
  let el = $state(null);

  const ord = $derived(ordenar(papers, estado.ordem));
  const nCom = $derived(comDado(papers, estado.ordem));
  // A fila entra na lista: paper coletado que a leitura ainda nao alcancou. Por
  // votos e por data ele fica na posicao dele; nas outras ordens nao ha dado
  // para ordenar e ele vai para o fim, num grupo com nome.
  const POSTO = { votos: (p) => p.u, recentes: (p) => Date.parse(p.d || '1970-01-01') };
  const linhas = $derived.by(() => {
    if (!faltam.length) return ord;
    const fila = faltam.map((f) => ({ ...f, fila: true })), k = POSTO[estado.ordem];
    return k ? [...ord, ...fila].sort((x, y) => k(y) - k(x) || y.u - x.u) : [...ord, ...fila.sort((x, y) => y.u - x.u)];
  });
  const visiveis = $derived(linhas.slice(0, PAGINA * paginas));
  // Marca da mediana: nas ordens em que "acima da mediana" e uma pergunta
  // (votos e ganho), uma regua separa as linhas de cima das de baixo.
  const MED = { votos: [(p) => p.u, (v) => `${Math.round(v).toLocaleString('pt-BR')} votos`], ganho: [ganhoDe, (v) => `${sgn(v)}%`] };
  const mediana = $derived.by(() => {
    const m = MED[estado.ordem]; if (!m || estado.busca) return null;
    const vs = papers.map(m[0]).filter((v) => v != null); if (vs.length < 4) return null;
    const med = median(vs), i = linhas.findIndex((p) => { const v = p.fila ? POSTO[estado.ordem]?.(p) : m[0](p); return v == null || v <= med; });
    return i > 0 ? { i, rot: m[1](med) } : null;
  });
  // paper aberto (por link, por Alt + setas ou por um grafico): a linha dele entra na tela
  $effect(() => { if (estado.sel) tick().then(() => el?.querySelector('.linha.ativa')?.scrollIntoView({ block: 'nearest' })); });
  const letra = (id) => 'ABC'[estado.comparar.indexOf(id)] || '';
  const bench = nBench;
  const sub = (p) => [ENTREGA[p.ent] || p.ent, p.cam ? CAMADA[p.cam] || p.cam : null].filter(Boolean).join(' · ');
  const aberto = (p) => liberados(p) || (p.prom ? 'prometido' : p.radar.abertura == null ? null : 'nada');
  // fora da tabela nao ha cabecalho de coluna: o fato leva o nome junto
  const abertoLongo = (p) => (liberados(p) ? `liberou ${liberados(p)}` : p.prom ? 'só prometido' : p.radar.abertura == null ? 'abertura não lida' : 'nada liberado');
  // no celular a coluna e curta: com dois ou mais artefatos, a contagem
  const nLib = (p) => Object.values(p.ab).filter((e) => e === 'liberado').length;
  const abertoEstreito = (p) => (nLib(p) > 1 ? `liberou ${nLib(p)} de ${Object.keys(ART).length}` : abertoLongo(p));
  const nomeLongo = (p) => [p.t, `${p.u} votos`, SOL_FRASE[p.sol].toLowerCase(), ganhoDe(p) != null ? `ganho ${sgn(ganhoDe(p))}%` : null,
    p.radar.facilidade != null ? `esforço: ${ESFORCO[p.esf].toLowerCase()}` : null, liberados(p) ? `liberou ${liberados(p)}` : null].filter(Boolean).join('. ');

  // colunas da tabela: [chave de ordem, rotulo, classe]
  const COLS = [['recentes', 'Data', 'c-d'], ['votos', 'Votos', 'c-n'], ['solidez', 'Prova', 'c-s'], ['ganho', 'Ganho', 'c-n'],
    ['facilidade', 'Adoção', 'c-a'], ['abertura', 'Abertura', 'c-l'], ['amplitude', 'Amplitude', 'c-n']];
  const ROT_ORDEM = { recentes: 'data', votos: 'votos', solidez: 'prova', ganho: 'ganho', facilidade: 'adoção, da mais fácil à mais difícil', abertura: 'abertura', amplitude: 'amplitude, em benchmarks' };
  const SEM = { solidez: 'Prova não lida', ganho: 'Sem rival externo ou ganho não lido', facilidade: 'Só informa: não há o que adotar', abertura: 'Abertura não lida', amplitude: 'Amplitude não lida' };

  // grade navegavel por setas (uma so parada de Tab)
  let foco = $state({ i: 0, c: 0 });
  $effect(() => { if (foco.i >= visiveis.length) foco = { i: Math.max(0, visiveis.length - 1), c: 0 }; });
  async function mover(e, i, c) {
    const n = visiveis.length; let ni = i, nc = c;
    if (e.key === 'ArrowDown') ni = Math.min(n - 1, i + 1);
    else if (e.key === 'ArrowUp' && i === 0 && el?.querySelector('.cab')?.offsetParent) {
      // da primeira linha, a seta para cima alcanca o cabecalho (ordenar por coluna)
      e.preventDefault(); const h = el.querySelector(`[data-h="${estado.ordem}"]`); (h?.offsetParent ? h : [...el.querySelectorAll('[data-h]')].find((b) => b.offsetParent))?.focus(); return;
    }
    else if (e.key === 'ArrowUp') ni = Math.max(0, i - 1);
    else if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') nc = c ? 0 : 1;
    else if (e.key === 'Home') ni = 0;
    else if (e.key === 'End') ni = n - 1;
    else if (e.key === 'PageDown') ni = Math.min(n - 1, i + 8);
    else if (e.key === 'PageUp') ni = Math.max(0, i - 8);
    else return;
    e.preventDefault();
    if (linhas[ni]?.fila) nc = 0;                 // a linha da fila so tem o link
    if (ni >= visiveis.length - 1 && visiveis.length < linhas.length && e.key !== 'ArrowUp') paginas++;
    foco = { i: ni, c: nc };
    await tick();
    el?.querySelector(`[data-i="${ni}"][data-c="${nc}"]`)?.focus();
  }
  const tab = (i, c) => (foco.i === i && foco.c === c ? 0 : -1);
  async function cabeca(e, k) {
    const ks = COLS.map((c) => c[0]), j = ks.indexOf(k);
    if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
      // pula as colunas que a largura escondeu
      e.preventDefault(); const d = e.key === 'ArrowRight' ? 1 : ks.length - 1, bt = (n) => el?.querySelector(`[data-h="${ks[n]}"]`);
      let n = j; do { n = (n + d) % ks.length; } while (n !== j && !bt(n)?.offsetParent);
      bt(n)?.focus();
    }
    else if (e.key === 'ArrowDown' || e.key === 'Escape') { e.preventDefault(); foco = { i: 0, c: 0 }; await tick(); el?.querySelector('[data-i="0"][data-c="0"]')?.focus(); }
  }
</script>

<div class="indice" bind:this={el}>
  <div class="ferr">
    <label class="busca"><Icone nome="busca" /><span class="vh">Buscar paper</span>
      <input type="search" placeholder="Buscar paper" bind:value={estado.busca} autocomplete="off" spellcheck="false" enterkeyhint="search" />
      {#if estado.busca}<button class="tira" type="button" aria-label="Limpar a busca" title="Limpar a busca" onclick={(e) => { estado.busca = ''; e.currentTarget.closest('label')?.querySelector('input')?.focus(); }}><Icone nome="x" tam={12} /></button>{/if}
    </label>
    <span class="ordem"><Menu nome="Ordem" rotulo="Ordem: {ORDENS.find(([k]) => k === estado.ordem)?.[1]}" descricao="Ordenar por: {ORDENS.find(([k]) => k === estado.ordem)?.[1]}" valor={estado.ordem} itens={ORDENS} aoEscolher={(v) => (estado.ordem = v)} /></span>
  </div>

  <div class="cab">
    <div class="cab-g" role="group" aria-label="Ordenar por coluna (seta para cima, a partir da primeira linha)">
      <span class="c-t rot">Paper</span>
      {#each COLS as [k, r, cl]}
        <button class="{cl}" tabindex="-1" data-h={k} aria-pressed={estado.ordem === k} aria-label="Ordenar por {ROT_ORDEM[k]}" onclick={() => (estado.ordem = k)} onkeydown={(e) => cabeca(e, k)}>{r}{#if estado.ordem === k}<Icone nome="desce" tam={12} />{/if}</button>
      {/each}
    </div>
    <span class="rot c-cmp">Comparar</span>
  </div>

  {#if !visiveis.length}
    <div class="vazio">{estado.busca ? `Nenhum paper com “${estado.busca}”.` : 'Nenhum paper neste recorte.'}
      {#if estado.busca}<button class="btn sec" onclick={() => (estado.busca = '')}>Limpar a busca</button>{/if}</div>
  {:else}
    <div class="lista" role="grid" aria-label="Papers do recorte" aria-rowcount={visiveis.length}>
      {#each visiveis as p, i (p.id)}
        {@const g = p.fila ? null : ganhoDe(p)}
        {@const st = p.fila ? [] : realcar(sub(p), estado.busca)}
        <div class="grupo" role="rowgroup" animate:flip={{ duration: mov(200) }}>
        {#if estado.ordem === 'recentes' && (i === 0 || visiveis[i - 1].d !== p.d)}
          <div class="div" role="row"><span role="gridcell">{intervalo(p.d, p.d)}</span></div>
        {:else if p.fila && !POSTO[estado.ordem] && !visiveis[i - 1]?.fila}
          <div class="div" role="row"><span role="gridcell">Na fila, ainda sem leitura · {faltam.length}</span></div>
        {:else if !p.fila && i === nCom && nCom > 0 && SEM[estado.ordem]}
          <div class="div" role="row"><span role="gridcell">{SEM[estado.ordem]} · {ord.length - nCom}</span></div>
        {:else if mediana && i === mediana.i}
          <div class="div med" role="row"><span role="gridcell">Mediana do recorte · {mediana.rot}</span></div>
        {/if}
        {#if p.fila}
          <!-- paper da fila: so ha titulo, data e votos; a linha leva ao arXiv -->
          <div class="linha fila" role="row">
            <div role="gridcell" class="g-abre">
              <a class="abre" href="https://arxiv.org/abs/{p.id}" target="_blank" rel="noopener" data-i={i} data-c="0" tabindex={tab(i, 0)}
                aria-label="{p.t}. {p.u} votos. Na fila, ainda sem leitura. Abre o arXiv em outra aba"
                onkeydown={(e) => mover(e, i, 0)} onfocus={() => (foco = { i, c: 0 })}>
                <span class="glifo"><MiniRadar radar={null} cor="var(--sol-nada)" tam={32} tracejado /></span>
                <span class="c-t">
                  <span class="t">{#each realcar(p.t, estado.busca) as [tx, casou]}{#if casou}<mark>{tx}</mark>{:else}{tx}{/if}{/each}</span>
                  <span class="s um">arXiv <span class="num">{p.id}</span></span>
                </span>
                <span class="fatos">
                  <span class="f-d num">{dataCurta(p.d)}</span>
                  <span class="f-v num">{p.u}<small> votos</small></span>
                  <span class="f-fila"><span class="um">Na fila, ainda sem leitura</span><Icone nome="fora" tam={12} /></span>
                </span>
              </a>
            </div>
            <div role="gridcell" class="g-cmp"></div>
          </div>
        {:else}
        <div class="linha" role="row" class:ativa={estado.sel === p.id} class:aceso={estado.hover === p.id}>
          <div role="gridcell" class="g-abre">
            <button class="abre" data-i={i} data-c="0" tabindex={tab(i, 0)} aria-label={nomeLongo(p)} aria-current={estado.sel === p.id ? 'true' : undefined}
              onclick={() => abrir(p.id)} onkeydown={(e) => mover(e, i, 0)} onfocus={() => (foco = { i, c: 0 })}
              onmouseenter={() => (estado.hover = p.id)} onmouseleave={() => (estado.hover = null)}>
              <span class="glifo"><MiniRadar radar={p.radar} cor={corSolidez(estado.tema, p.sol)} tam={32} tracejado={p.sol === 'sem_leitura'} /></span>
              <span class="c-t">
                <span class="t">{#each realcar(p.t, estado.busca) as [tx, casou]}{#if casou}<mark>{tx}</mark>{:else}{tx}{/if}{/each}</span>
                <span class="s um" class:tem={st.some((x) => x[1])}>{#each st as [tx, casou]}{#if casou}<mark>{tx}</mark>{:else}{tx}{/if}{/each}</span>
                {#if estado.busca && ondeAchou(p, estado.busca)}<span class="acha um">{ondeAchou(p, estado.busca)}</span>{/if}
              </span>
              <!-- nenhum traco no lugar de um fato: o que falta diz por que falta -->
              <span class="fatos">
                <span class="f-d num">{dataCurta(p.d)}</span>
                <span class="f-v num">{p.u}<small> votos</small></span>
                <span class="f-s"><i class="sol {p.sol}"></i><span class="um" class:mut={p.sol === 'sem_leitura'}>{p.sol === 'sem_leitura' ? 'Não lida' : SOL_ROT[p.sol]}</span></span>
                {#if g != null}<span class="f-g num" class:neg={g < 0}><small>ganho</small>{sgn(g)}%</span>
                {:else if p.res.length}<span class="f-g sem">sem rival</span>
                {:else}<span class="f-g sem"><small>ganho</small>não lido</span>{/if}
                <span class="f-a" class:mut={p.radar.facilidade == null}>{#if p.radar.facilidade != null}<Degraus esf={p.esf} />{/if}<span class="um">{ESFORCO[p.esf]}</span></span>
                <span class="f-l um" class:mut={aberto(p) == null}><span class="cur">{aberto(p) ?? 'não lida'}</span><span class="lon">{abertoLongo(p)}</span><span class="est">{abertoEstreito(p)}</span></span>
                {#if bench(p) != null}<span class="f-b num">{bench(p)}</span>{:else}<span class="f-b sem">não lida</span>{/if}
              </span>
            </button>
          </div>
          <div role="gridcell" class="g-cmp">
            <button class="cmp" data-i={i} data-c="1" tabindex={tab(i, 1)} aria-pressed={!!letra(p.id)} style:--c="var(--cmp-{estado.comparar.indexOf(p.id) + 1})"
              aria-label="{letra(p.id) ? 'Tirar da comparação' : 'Comparar'}: {p.t}" title={letra(p.id) ? 'Tirar da comparação' : 'Comparar'}
              onclick={() => alternaComparar(p.id)} onkeydown={(e) => mover(e, i, 1)} onfocus={() => (foco = { i, c: 1 })}>{#if letra(p.id)}{letra(p.id)}{:else}<Icone nome="mais" tam={12} />{/if}</button>
          </div>
        </div>
        {/if}
        </div>
      {/each}
    </div>
  {/if}

  {#if linhas.length > visiveis.length}
    <button class="btn sec mais" onclick={() => paginas++}>Mostrar mais {Math.min(PAGINA, linhas.length - visiveis.length)} de {linhas.length - visiveis.length}</button>
  {/if}
</div>

<style>
  .indice { container-type: inline-size; min-width: 0; }
  .ferr { display: flex; gap: var(--sp-2); align-items: center; margin-bottom: var(--sp-3); }
  .busca { flex: 1 1 120px; min-width: 0; max-width: 360px; display: flex; align-items: center; gap: var(--sp-2); min-height: var(--ctl); padding: 0 var(--sp-3); border-radius: var(--r-2);
    background: var(--surface); box-shadow: inset 0 0 0 1px var(--line-strong); color: var(--muted); transition: box-shadow var(--dur-1); }
  .busca:focus-within { box-shadow: inset 0 0 0 2px var(--focus); color: var(--ink); }
  .busca input { flex: 1; min-width: 0; border: 0; background: none; font: inherit; font-size: 16px; color: var(--ink); outline: none; padding: 0; height: calc(var(--ctl) - 4px); }
  @media (min-width: 768px) { .busca input { font-size: var(--fs-14); } }
  .busca input::placeholder { color: var(--muted); opacity: 1; }
  .busca input::-webkit-search-cancel-button { display: none; }
  .tira { flex: none; width: 24px; height: 24px; margin-right: -6px; border-radius: 50%; display: grid; place-items: center; color: var(--muted); position: relative; }
  .tira::after { content: ''; position: absolute; inset: -10px; }
  .tira:hover { background: var(--hover); color: var(--ink); }
  .ordem { display: inline-flex; flex: none; }
  .ordem :global(.sel) { min-height: var(--ctl); }
  @media (pointer: coarse) {
    .busca, .ordem :global(.sel) { min-height: 44px; }
    .ordem :global(.sel)::after { inset: 0; }
  }

  /* cabecalho da tabela (so na forma larga): preso logo abaixo do recorte */
  .cab { display: none; grid-template-columns: minmax(0, 1fr) 72px; column-gap: var(--sp-3); align-items: center; padding-block: var(--sp-2); border-bottom: 1px solid var(--line-strong);
    position: sticky; top: calc(var(--barra) + var(--recorte-alt, 53px)); z-index: 5; background: var(--bg); }
  .cab-g { display: grid; align-items: center; column-gap: var(--sp-4); grid-template-columns: var(--colunas); padding-left: var(--sp-3); }
  .cab .c-t { grid-column: 1 / 3; }
  .cab .c-cmp { text-align: center; }
  .cab button { font-size: var(--fs-12); line-height: var(--lh-12); font-weight: 500; color: var(--muted); display: inline-flex; align-items: center; gap: 2px; min-height: var(--alvo); border-radius: var(--r-1); justify-self: start; transition: color var(--dur-1); }
  .cab button.c-n, .cab button.c-d { justify-self: end; flex-direction: row-reverse; }
  .cab button.c-a { margin-left: var(--sp-3); }
  .cab button:hover { color: var(--ink); }
  .cab button[aria-pressed="true"] { color: var(--ink); font-weight: 600; }

  /* a adocao comeca 12 px depois da sua coluna: o numero do ganho, alinhado a direita, nao encosta nela */
  .indice { --colunas: 32px minmax(0, 1fr) 44px 48px 84px 64px 144px 108px 72px; }
  .lista { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-3); overflow: clip; }
  .linha { display: grid; grid-template-columns: minmax(0, 1fr) 44px; align-items: center; border-top: 1px solid var(--line); position: relative; background: var(--surface); }
  .grupo:first-child > :first-child { border-top: 0; }
  .linha:hover, .linha.aceso { background: var(--hover); }
  .linha.ativa { background: var(--sunk); }
  .linha.ativa::before { content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; background: var(--accent); }
  .abre:focus-visible { outline-offset: -2px; border-radius: var(--r-2); }
  .mut { color: var(--muted); }
  mark { background: color-mix(in srgb, var(--accent) 18%, transparent); color: var(--ink); border-radius: 2px; padding-block: 1px; }      /* tinta cheia: o termo marcado passa de 4,5:1 mesmo na linha cinza */

  /* estreito: titulo em ate duas linhas e, embaixo, os fatos em posicao fixa
     (votos, prova, ganho / adocao, abertura), para o olho descer por uma coluna */
  .abre { display: grid; width: 100%; min-height: 52px; text-align: left; border-radius: 0; align-items: center;
    grid-template-columns: minmax(0, 1fr); row-gap: var(--sp-1); padding: var(--sp-3) 0 var(--sp-3) var(--sp-3); }
  .glifo { display: none; place-items: center; }
  .c-t { display: grid; min-width: 0; }
  .t { font-weight: 500; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; overflow-wrap: anywhere; }
  .s { display: none; font-size: var(--fs-12); line-height: var(--lh-12); color: var(--muted); }
  .s.tem { display: block; }                       /* a busca casou no tipo ou na camada: a linha aparece */
  .acha { font-size: var(--fs-12); line-height: var(--lh-12); color: var(--muted); }
  /* tres colunas: a abertura cai embaixo do ganho, e a adocao ocupa as duas primeiras */
  .fatos { display: grid; grid-template-columns: 72px 68px minmax(0, 1fr); column-gap: var(--sp-3); row-gap: 2px; align-items: center;
    font-size: var(--fs-12); line-height: var(--lh-12); color: var(--ink2); }
  .fatos > * { min-width: 0; white-space: nowrap; }
  .f-d, .f-b { display: none; }
  .f-v { grid-column: 1; } .f-s { grid-column: 2; } .f-g { grid-column: 3; }
  .f-a { grid-column: 1 / 3; grid-row: 2; } .f-l { grid-column: 3; grid-row: 2; }
  /* o fato que falta e uma palavra, na fonte do texto: nao disputa com os numeros */
  .sem { color: var(--muted); }
  .f-g.neg { color: var(--alert); }
  .f-fila { grid-column: 2 / -1; display: inline-flex; align-items: center; gap: var(--sp-1); color: var(--muted); }
  a.abre { color: inherit; text-decoration: none; }
  .f-v small { font-family: var(--f-ui); letter-spacing: 0; font-size: inherit; margin-left: .3em; }
  .f-g small { font-family: var(--f-ui); letter-spacing: 0; font-size: inherit; margin-right: .4em; color: var(--muted); }
  .f-l .cur, .f-l .lon { display: none; }
  .f-s, .f-a { display: inline-flex; align-items: center; gap: 6px; }

  .cmp { width: 28px; height: 28px; border-radius: 50%; display: grid; place-items: center; color: var(--muted); box-shadow: inset 0 0 0 1px var(--line-strong); font-size: var(--fs-12); font-weight: 600;
    transition: background var(--dur-1), color var(--dur-1), box-shadow var(--dur-1); position: relative; }
  .cmp::after { content: ''; position: absolute; inset: -8px; }                 /* alvo de 44 px */
  .cmp:hover { color: var(--ink); background: var(--surface); box-shadow: inset 0 0 0 1.5px var(--ink); }
  .cmp[aria-pressed="true"] { background: var(--c); color: var(--surface); box-shadow: none; }
  .g-cmp { display: grid; place-items: center; }

  .div { padding: var(--sp-4) var(--sp-3) var(--sp-1); font-size: var(--fs-12); line-height: var(--lh-12); font-weight: 500; color: var(--muted); border-top: 1px solid var(--line); background: var(--bg); }
  .div.med { display: flex; align-items: center; gap: var(--sp-3); padding-block: var(--sp-2); }
  .div.med::after { content: ''; flex: 1; height: 1px; background: var(--line-strong); }

  @container (max-width: 319px) { .f-g small { display: none; } }             /* celular muito estreito: o ganho fica so com o numero */

  /* medio: os cinco fatos numa linha so, em colunas alinhadas, com a miniatura do radar */
  @container (min-width: 560px) {
    .abre { grid-template-columns: 32px minmax(0, 1fr); column-gap: var(--sp-3); }
    .glifo { display: grid; grid-row: 1 / 3; align-self: start; padding-top: 2px; }
    .fatos { grid-column: 2; grid-template-columns: 72px 96px 104px 140px minmax(0, 1fr); column-gap: var(--sp-4); }
    .f-v, .f-s, .f-g, .f-a, .f-l { grid-column: auto; grid-row: 1; }
    .f-l .lon { display: inline; } .f-l .est { display: none; }
    .f-fila { grid-column: 2 / -1; }
  }

  /* largo: tabela. So entra quando sobra pelo menos 300 px para o titulo */
  @container (min-width: 980px) {
    .cab { display: grid; }
    .lista { border-radius: 0 0 var(--r-3) var(--r-3); border-top: 0; }
    .linha { grid-template-columns: minmax(0, 1fr) 72px; column-gap: var(--sp-3); }
    .ordem { display: none; }
    .abre { grid-template-columns: var(--colunas); column-gap: var(--sp-4); row-gap: 0; padding-block: 6px; }
    .glifo { grid-row: auto; align-self: center; padding: 0; }
    .s { display: block; }
    .fatos { display: contents; }
    .f-d, .f-b { display: block; }
    .f-v, .f-s, .f-g, .f-a, .f-l { grid-row: auto; }
    .f-d, .f-v, .f-g, .f-b { text-align: right; justify-self: end; }
    .f-d { color: var(--muted); font-size: var(--fs-12); }
    .f-v small, .f-g small, .f-l .lon { display: none; }
    .f-l .cur { display: inline; }
    .f-fila { grid-column: 5 / -1; }
    .f-g.sem, .f-b.sem { text-align: right; justify-self: end; }
    .f-a { padding-left: var(--sp-3); }
  }
  /* tabela com pouco lugar (paper aberto ao lado, em tela larga): saem a data e a amplitude, ficam as colunas da decisao */
  @container (min-width: 980px) and (max-width: 1119.98px) {
    .cab-g, .abre { --colunas: 32px minmax(0, 1fr) 48px 84px 64px 144px 108px; }
    .f-d, .f-b, .cab [data-h="recentes"], .cab [data-h="amplitude"] { display: none; }
    .f-fila { grid-column: 4 / -1; }
  }

  .mais { margin-top: var(--sp-3); width: 100%; }
</style>
