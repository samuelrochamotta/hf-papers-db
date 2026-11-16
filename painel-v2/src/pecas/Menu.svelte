<script>
  // Menu de escolha unica: um botao que abre uma lista (listbox) na camada de
  // cima da pagina. Fica no lugar do <select> nativo para a lista ter a cara
  // do painel e mostrar a contagem de cada opcao. Com `busca`, a lista longa
  // ganha um campo que filtra enquanto se digita.
  // Com `varias`, `valor` e uma lista: cada opcao liga e desliga sem fechar o
  // menu, e a primeira (valor '') desliga todas.
  // Teclado: Enter, espaco ou seta abre; setas, Home, End e letras andam;
  // Enter ou espaco escolhe; Esc fecha e devolve o foco ao botao.
  import Icone from '../lib/Icone.svelte';
  // itens: [valor, texto, contagem?]
  let { nome, rotulo, descricao = '', valor = '', itens = [], aoEscolher, ligado = false, icone = '', classe = '', busca = false, prefixo = '', varias = false, aoTirar = null } = $props();
  const id = $props.id();
  let aberto = $state(false), ativo = $state(0), filtro = $state('');
  let botao = $state(null), caixa = $state(null), campo = $state(null);
  let digitado = '', relogio = 0;
  const norm = (s) => String(s).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const comBusca = $derived(busca && itens.length > 8);
  const vis = $derived(comBusca && filtro.trim() ? itens.filter((it) => norm(it[1]).includes(norm(filtro.trim()))) : itens);

  function antes(e) {
    if (e.newState !== 'open') return;
    filtro = '';
    const r = botao.getBoundingClientRect();
    caixa.style.left = `${r.left}px`; caixa.style.top = `${r.bottom + 4}px`; caixa.style.minWidth = `${Math.max(200, r.width)}px`;
  }
  function depois(e) {
    aberto = e.newState === 'open';
    if (!aberto) return;
    // cabe na tela: encosta na borda direita e abre para cima se faltar altura
    const r = botao.getBoundingClientRect(), w = caixa.offsetWidth;
    const abaixo = innerHeight - r.bottom - 12, acima = r.top - 12, sobe = caixa.scrollHeight > abaixo && acima > abaixo;
    caixa.style.maxHeight = `${Math.max(120, sobe ? acima : abaixo)}px`;
    caixa.style.left = `${Math.max(8, Math.min(r.left, innerWidth - w - 8))}px`;
    caixa.style.top = sobe ? `${Math.max(8, r.top - 4 - Math.min(caixa.scrollHeight + 10, acima))}px` : `${r.bottom + 4}px`;
    ativo = Math.max(0, itens.findIndex((i) => marcado(i[0])));
    if (comBusca) campo?.focus(); else focar();
  }
  const focar = () => caixa?.querySelector(`[data-i="${ativo}"]`)?.focus();
  const marcado = (v) => (varias ? (valor.length ? valor.includes(String(v)) : v === '') : String(v) === String(valor));
  function escolher(v) { aoEscolher(v); if (varias && v !== '') return; caixa.hidePopover(); botao.focus(); }
  function teclaBotao(e) {
    if ((e.key === 'ArrowDown' || e.key === 'ArrowUp') && !aberto) { e.preventDefault(); caixa.showPopover(); }
  }
  function teclaCampo(e) {
    if (e.key === 'ArrowDown' && vis.length) { e.preventDefault(); ativo = 0; focar(); }
    else if (e.key === 'Enter' && vis.length) { e.preventDefault(); escolher(vis[0][0]); }
  }
  function teclaLista(e) {
    const n = vis.length;
    if (e.key === 'ArrowDown') ativo = Math.min(n - 1, ativo + 1);
    else if (e.key === 'ArrowUp' && ativo === 0 && comBusca) { e.preventDefault(); campo?.focus(); return; }
    else if (e.key === 'ArrowUp') ativo = Math.max(0, ativo - 1);
    else if (e.key === 'Home') ativo = 0;
    else if (e.key === 'End') ativo = n - 1;
    else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); escolher(vis[ativo][0]); return; }
    else if (e.key === 'Tab') { caixa.hidePopover(); return; }
    else if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
      if (comBusca) { campo?.focus(); return; }     // a letra cai no campo de busca
      clearTimeout(relogio); digitado += e.key.toLowerCase(); relogio = setTimeout(() => (digitado = ''), 600);
      const i = itens.findIndex((it) => String(it[1]).toLowerCase().startsWith(digitado));
      if (i >= 0) ativo = i;
    } else return;
    e.preventDefault(); focar();
  }
</script>

<!-- filtro ligado: o "×" ao lado tira so este filtro, com um gesto, como o da busca -->
<span class="par" class:tem={ligado && aoTirar}>
  <button bind:this={botao} class="sel {classe}" class:on={ligado} popovertarget={id} aria-haspopup="listbox" aria-expanded={aberto} aria-label={descricao || `${nome}: ${rotulo}`} onkeydown={teclaBotao}>
    {#if icone}<Icone nome={icone} tam={12} />{/if}<span>{#if prefixo}<span class="pre">{prefixo}</span>{/if}{rotulo}</span><Icone nome="baixo" tam={12} />
  </button>
  {#if ligado && aoTirar}<button class="sel on tirar" aria-label="Tirar o filtro de {nome.toLowerCase()}" title="Tirar o filtro" onclick={aoTirar}><Icone nome="x" tam={12} /></button>{/if}
</span>
<div bind:this={caixa} {id} popover="auto" class="menu" onbeforetoggle={antes} ontoggle={depois}>
  {#if comBusca}
    <label class="filtro"><Icone nome="busca" tam={14} /><span class="vh">Buscar em {nome}</span>
      <input bind:this={campo} type="search" placeholder="Buscar" bind:value={filtro} autocomplete="off" spellcheck="false" aria-controls="{id}-l" oninput={() => (ativo = 0)} onkeydown={teclaCampo} />
    </label>
  {/if}
  <div id="{id}-l" role="listbox" aria-label={nome} aria-multiselectable={varias || undefined} tabindex="-1" onkeydown={teclaLista}>
    {#each vis as [v, r, n], i (v)}
      {@const sel = marcado(v)}
      <!-- svelte-ignore a11y_click_events_have_key_events (o teclado e tratado na lista, em teclaLista) -->
      <div role="option" tabindex="-1" data-i={i} aria-selected={sel} onclick={() => escolher(v)} onmousemove={() => (ativo = i)}>
        <span class="ck">{#if sel}<Icone nome="check" tam={12} />{/if}</span><span class="r">{r}</span>{#if n != null}<span class="n num">{n}</span>{/if}
      </div>
    {/each}
  </div>
  {#if comBusca && !vis.length}<p class="nada" role="status">Nada com “{filtro}”.</p>{/if}
</div>

<style>
  button { cursor: pointer; font-family: inherit; }
  .par { display: contents; }
  .par.tem { display: inline-flex; align-items: stretch; gap: 1px; }
  .par.tem > .sel:first-child { border-radius: 999px 0 0 999px; padding-right: 6px; }
  .par.tem > .tirar { border-radius: 0 999px 999px 0; padding: 0 10px 0 6px; }
  @media (pointer: coarse) { .par.tem > .tirar { padding: 0 14px 0 10px; } .par.tem > .tirar::after { inset: -4px -4px; } }
  .menu { position: fixed; inset: auto; margin: 0; padding: var(--sp-1); border: 1px solid var(--line); border-radius: var(--r-2); background: var(--raise); color: var(--ink);
    box-shadow: var(--sombra-2); max-width: min(380px, calc(100vw - 16px)); overflow-y: auto; overscroll-behavior: contain; font-size: var(--fs-14); line-height: var(--lh-14); }
  .menu:popover-open { display: grid; align-content: start; animation: entra var(--dur-1) var(--sai); }
  @keyframes entra { from { opacity: 0; transform: translateY(-4px); } }
  .filtro { position: sticky; top: calc(-1 * var(--sp-1)); z-index: 1; display: flex; align-items: center; gap: var(--sp-2); min-height: var(--ctl); margin: calc(-1 * var(--sp-1)) calc(-1 * var(--sp-1)) var(--sp-1); padding: var(--sp-1) var(--sp-3);
    background: var(--raise); border-bottom: 1px solid var(--line); color: var(--muted); }
  .filtro:focus-within { color: var(--ink); box-shadow: inset 0 -2px 0 var(--focus); }
  .filtro input { flex: 1; min-width: 0; border: 0; background: none; font: inherit; font-size: 16px; color: var(--ink); outline: none; padding: 0; height: var(--ctl); }
  @media (min-width: 768px) { .filtro input { font-size: var(--fs-14); } }
  .filtro input::placeholder { color: var(--muted); opacity: 1; }
  [role="option"] { display: grid; grid-template-columns: 16px minmax(0, 1fr) auto; align-items: center; gap: var(--sp-2); min-height: var(--ctl); padding: 0 var(--sp-3) 0 var(--sp-2);
    border-radius: calc(var(--r-2) - 2px); cursor: pointer; user-select: none; }
  [role="option"]:hover { background: var(--hover); }
  [role="option"]:focus { outline: none; background: var(--sunk); }
  [role="option"]:focus-visible { box-shadow: inset 0 0 0 2px var(--focus); }
  [role="option"][aria-selected="true"] { font-weight: 600; }
  .ck { display: grid; place-items: center; }
  .r { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .n { font-size: var(--fs-12); color: var(--muted); font-weight: 400; }
  .nada { padding: var(--sp-3); color: var(--muted); }
</style>
