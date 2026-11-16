<script>
  // Quadro de um grafico: a pergunta, o numero que responde e o grafico.
  // Sem frase de instrucao: o que e clicavel se mostra no proprio desenho.
  // Sem dado no recorte (`vazio`), fica so a pergunta e a frase que diz isso:
  // nem zero grande nem legenda de um desenho que nao existe.
  import { Tween } from 'svelte/motion';
  import { cubicOut } from 'svelte/easing';
  import { mov } from '../lib/estado.svelte.js';
  let { pergunta, valor = undefined, casas = 0, prefixo = '', sufixo = '', resposta = '', palavra = '', extra = null, children, legenda = null, id = '', vazio = false } = $props();
  const t = new Tween(0, { duration: mov(320), easing: cubicOut });
  $effect(() => { t.target = valor ?? 0; });
  const mostra = $derived((prefixo && t.current >= 0.05 ? prefixo : t.current <= -0.05 ? '−' : '')
    + Math.abs(t.current).toLocaleString('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas }));
</script>

<section class="quadro" class:oco={vazio} aria-labelledby="q-{id}" data-regiao={id}>
  <header>
    <h3 id="q-{id}">{pergunta}</h3>
  </header>
  <!-- `palavra` responde com uma palavra quando um numero mudaria de unidade (rodada 13: "Nenhuma" arena com disputa) -->
  {#if palavra && !vazio}
    <p class="resp"><b class="titulo">{palavra}</b><span>{resposta}</span></p>
  {:else if valor !== undefined && !vazio}
    <p class="resp"><b class="titulo">{valor == null ? '–' : mostra}{#if sufixo && valor != null}<small>{sufixo}</small>{/if}</b><span>{resposta}</span></p>
  {/if}
  <!-- o controle do desenho fica junto do desenho: o numero de cada quadro da fileira comeca na mesma altura -->
  {#if extra}<div class="extra">{@render extra()}</div>{/if}
  <div class="g">{@render children()}</div>
  {#if legenda && !vazio}<footer>{@render legenda()}</footer>{/if}
</section>

<style>
  .quadro { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-3); padding: var(--sp-4); display: flex; flex-direction: column; min-width: 0; container-type: inline-size; }
  @media (min-width: 768px) { .quadro { padding: var(--sp-5) var(--sp-6); } }
  /* sem dado no recorte, o quadro fica do tamanho da frase: nao estica ate o vizinho para mostrar um vazio */
  .quadro.oco { align-self: start; }
  header { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--sp-3); flex-wrap: wrap; }
  h3 { font-size: var(--fs-14); line-height: var(--lh-14); font-weight: 600; color: var(--ink2); text-wrap: balance; }
  /* o numero fica sozinho na linha e a frase vem embaixo: o mesmo arranjo em todo quadro e em toda largura */
  .resp { display: grid; gap: var(--sp-1); margin: var(--sp-1) 0 var(--sp-4); }
  .resp b { font-size: var(--fs-35); line-height: var(--lh-35); }
  .resp b small { font-size: .5em; letter-spacing: 0; margin-left: 2px; color: var(--ink2); }
  .resp span { font-size: var(--fs-14); line-height: var(--lh-14); color: var(--ink2); max-width: 52ch; text-wrap: balance; }
  .extra { margin-bottom: var(--sp-3); display: flex; }
  /* o miolo fica com a altura que sobra no quadro, e o desenho cresce dentro dele */
  .g { min-width: 0; display: flex; flex-direction: column; flex: 1 1 auto; margin-bottom: var(--sp-3); }
  /* os quadros de uma fileira terminam juntos: a legenda fica no pe */
  footer { margin-top: auto; padding-top: var(--sp-3); border-top: 1px solid var(--line); }
</style>
