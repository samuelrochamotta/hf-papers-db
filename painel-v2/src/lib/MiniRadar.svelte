<script>
  // Assinatura do paper: o radar de seis eixos em miniatura, desenhado em SVG
  // (trinta instancias de ECharts so para miniaturas seria peso demais).
  import { EIXOS } from './dados.js';
  let { radar, cor, tam = 44, tracejado = false, aceso = false } = $props();
  const n = EIXOS.length;
  const c = $derived(tam / 2);
  const r = $derived(tam / 2 - 3);
  const ponto = (i, v) => {
    const a = -Math.PI / 2 + (i * 2 * Math.PI) / n;
    const rr = (r * Math.max(6, v ?? 0)) / 100;
    return [c + rr * Math.cos(a), c + rr * Math.sin(a)];
  };
  const contorno = $derived(EIXOS.map((_, i) => ponto(i, 100).join(',')).join(' '));
  const forma = $derived(EIXOS.map(([k], i) => ponto(i, radar?.[k]).join(',')).join(' '));
</script>

<svg width={tam} height={tam} viewBox="0 0 {tam} {tam}" aria-hidden="true" class:aceso>
  <polygon points={contorno} class="grade" />
  {#each EIXOS as _, i}
    <line x1={c} y1={c} x2={ponto(i, 100)[0]} y2={ponto(i, 100)[1]} class="raio" />
  {/each}
  <polygon points={forma} fill={tracejado ? 'none' : cor} fill-opacity={tracejado ? 0 : 0.78}
    stroke={tracejado ? 'var(--s-nada)' : cor} stroke-width="1.4" stroke-dasharray={tracejado ? '2.5 2' : null}
    stroke-linejoin="round" class="forma" />
</svg>

<style>
  .grade { fill: var(--sunk); stroke: var(--line); stroke-width: 1; }
  .raio { stroke: var(--line); stroke-width: .7; }
  .forma { transition: transform .35s cubic-bezier(.2,.8,.2,1); transform-origin: center; transform-box: fill-box; }
  svg.aceso .forma { transform: scale(1.12); }
</style>
