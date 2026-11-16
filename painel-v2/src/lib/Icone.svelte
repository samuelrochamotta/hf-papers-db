<script>
  // Icones de traco unico, 16 px, mesma espessura (1,6) em toda a interface.
  let { nome, tam = 16 } = $props();
  const P = {
    x: 'M4 4l8 8M12 4l-8 8',
    mais: 'M8 3.5v9M3.5 8h9',
    check: 'M3.5 8.5l3 3 6-7',
    esq: 'M10 3.5L5.5 8l4.5 4.5',
    dir: 'M6 3.5L10.5 8 6 12.5',
    baixo: 'M3.5 6l4.5 4.5L12.5 6',
    fora: 'M6.5 3.5H12.5V9.5M12.5 3.5L5 11M4 6v6.5h6.5',
    filtro: 'M2.5 4h11M4.5 8h7M6.5 12h3',
    sol: 'M8 2v1.5M8 12.5V14M2 8h1.5M12.5 8H14M3.8 3.8l1 1M11.2 11.2l1 1M3.8 12.2l1-1M11.2 4.8l1-1M8 5.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z',
    lua: 'M13 9.5A5.5 5.5 0 0 1 6.5 3a5.5 5.5 0 1 0 6.5 6.5z',
    radar: 'M8 2l5.2 3v6L8 14l-5.2-3V5zM8 2v12M2.8 5l10.4 6M13.2 5L2.8 11',
    busca: 'M7.2 12a4.8 4.8 0 1 0 0-9.6 4.8 4.8 0 0 0 0 9.6zM10.8 10.8L14 14',
    lista: 'M2.5 4h11M2.5 8h11M2.5 12h11',
    graficos: 'M2.5 13.5v-5M6.2 13.5v-9M9.9 13.5v-6.5M13.5 13.5V2.5',
    troca: 'M3 5.5h10M10.5 3L13 5.5 10.5 8M13 10.5H3M5.5 8L3 10.5 5.5 13',
    sobe: 'M8 12.5v-9M4 7l4-4 4 4', desce: 'M8 3.5v9M4 9l4 4 4-4',
  };
</script>

<svg width={tam} height={tam} viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"
  stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d={P[nome]} /></svg>
