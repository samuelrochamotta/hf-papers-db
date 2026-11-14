import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import { viteSingleFile } from 'vite-plugin-singlefile';

// Build normal: relatorios/painel-v2/ (index.html + assets com nome fixo, para
// a rodada diaria so trocar dados.json sem acumular arquivos com hash).
// Modo "previa": um HTML unico com tudo dentro, em .previa/, para publicar
// como pagina avulsa; scripts/previa.mjs injeta os dados nele.
export default defineConfig(({ mode }) => {
  const previa = mode === 'previa';
  return {
    base: './',
    // public/ so serve o dados.json de exemplo no `npm run dev`; no build o
    // dados.json e do Python e nao pode ser sobrescrito.
    publicDir: mode === 'development' ? 'public' : false,
    plugins: [svelte(), ...(previa ? [viteSingleFile()] : [])],
    build: {
      outDir: previa ? '.previa' : '../relatorios/painel-v2',
      emptyOutDir: previa,
      chunkSizeWarningLimit: 900,
      rollupOptions: {
        output: previa ? {} : {
          entryFileNames: 'assets/painel.js',
          chunkFileNames: 'assets/[name].js',
          assetFileNames: 'assets/[name][extname]',
        },
      },
    },
  };
});
