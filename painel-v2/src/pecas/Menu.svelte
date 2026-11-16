<script>
  // Menu de escolha unica: um botao que abre uma lista (listbox) na camada de
  // cima da pagina. Fica no lugar do <select> nativo para a lista ter a cara
  // do painel e mostrar a contagem de cada opcao.
  // Teclado: Enter, espaco ou seta abre; setas, Home, End e letras andam;
  // Enter ou espaco escolhe; Esc fecha e devolve o foco ao botao.
  import Icone from '../lib/Icone.svelte';
  // itens: [valor, texto, contagem?]
  let { nome, rotulo, descricao = '', valor = '', itens = [], aoEscolher, ligado = false, icone = '', classe = '' } = $props();
  const id = $props.id();
  let aberto = $state(false), ativo = $state(0);
  let botao = $state(null), lista = $state(null);
  let digitado = '', relogio = 0;

  function antes(e) {
    if (e.newState !== 'open') return;
    const r = botao.getBoundingClientRect();
    lista.style.left = `${r.left}px`; lista.style.top = `${r.bottom + 4}px`; lista.style.minWidth = `${Math.max(200, r.width)}px`;
  }
  function depois(e) {
    aberto = e.newState === 'open';
    if (!aberto) return;
    // cabe na tela: encosta na borda direita e abre para cima se faltar altura
    const r = botao.getBoundingClientRect(), w = lista.offsetWidth;
    const abaixo = innerHeight - r.bottom - 12, acima = r.top - 12, sobe = lista.scrollHeight > abaixo && acima > abaixo;
    lista.style.maxHeight = `${Math.max(120, sobe ? acima : abaixo)}px`;
    lista.style.left = `${Math.max(8, Math.min(r.left, innerWidth - w - 8))}px`;
    lista.style.top = sobe ? `${Math.max(8, r.top - 4 - Math.min(lista.scrollHeight + 10, acima))}px` : `${r.bottom + 4}px`;
    ativo = Math.max(0, itens.findIndex((i) => String(i[0]) === String(valor)));
    focar();
  }
  const focar = () => lista?.querySelector(`[data-i="${ativo}"]`)?.focus();
  function escolher(v) { aoEscolher(v); lista.hidePopover(); botao.focus(); }
  function teclaBotao(e) {
    if ((e.key === 'ArrowDown' || e.key === 'ArrowUp') && !aberto) { e.preventDefault(); lista.showPopover(); }
  }
  function teclaLista(e) {
    const n = itens.length;
    if (e.key === 'ArrowDown') ativo = Math.min(n - 1, ativo + 1);
    else if (e.key === 'ArrowUp') ativo = Math.max(0, ativo - 1);
    else if (e.key === 'Home') ativo = 0;
    else if (e.key === 'End') ativo = n - 1;
    else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); escolher(itens[ativo][0]); return; }
    else if (e.key === 'Tab') { lista.hidePopover(); return; }
    else if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
      clearTimeout(relogio); digitado += e.key.toLowerCase(); relogio = setTimeout(() => (digitado = ''), 600);
      const i = itens.findIndex((it) => String(it[1]).toLowerCase().startsWith(digitado));
      if (i >= 0) ativo = i;
    } else return;
    e.preventDefault(); focar();
  }
</script>

<button bind:this={botao} class="sel {classe}" class:on={ligado} popovertarget={id} aria-haspopup="listbox" aria-expanded={aberto} aria-label={descricao || `${nome}: ${rotulo}`} onkeydown={teclaBotao}>
  {#if icone}<Icone nome={icone} tam={12} />{/if}<span>{rotulo}</span><Icone nome="baixo" tam={12} />
</button>
<div bind:this={lista} {id} popover="auto" role="listbox" aria-label={nome} class="menu" tabindex="-1" onbeforetoggle={antes} ontoggle={depois} onkeydown={teclaLista}>
  {#each itens as [v, r, n], i (v)}
    {@const sel = String(v) === String(valor)}
    <div role="option" tabindex="-1" data-i={i} aria-selected={sel} onclick={() => escolher(v)} onmousemove={() => (ativo = i)}>
      <span class="ck">{#if sel}<Icone nome="check" tam={12} />{/if}</span><span class="r">{r}</span>{#if n != null}<span class="n num">{n}</span>{/if}
    </div>
  {/each}
</div>

<style>
  button { cursor: pointer; font-family: inherit; }
  .menu { position: fixed; inset: auto; margin: 0; padding: var(--sp-1); border: 1px solid var(--line); border-radius: var(--r-2); background: var(--raise); color: var(--ink);
    box-shadow: var(--sombra-2); max-width: min(380px, calc(100vw - 16px)); overflow-y: auto; overscroll-behavior: contain; font-size: var(--fs-14); line-height: var(--lh-14); }
  .menu:popover-open { display: grid; animation: entra var(--dur-1) var(--sai); }
  @keyframes entra { from { opacity: 0; transform: translateY(-4px); } }
  [role="option"] { display: grid; grid-template-columns: 16px minmax(0, 1fr) auto; align-items: center; gap: var(--sp-2); min-height: var(--ctl); padding: 0 var(--sp-3) 0 var(--sp-2);
    border-radius: calc(var(--r-2) - 2px); cursor: pointer; user-select: none; }
  [role="option"]:hover { background: var(--hover); }
  [role="option"]:focus { outline: none; background: var(--sunk); }
  [role="option"]:focus-visible { box-shadow: inset 0 0 0 2px var(--focus); }
  [role="option"][aria-selected="true"] { font-weight: 600; }
  .ck { display: grid; place-items: center; }
  .r { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .n { font-size: var(--fs-12); color: var(--muted); font-weight: 400; }
</style>
