// Injeta dados.json no HTML unico do modo previa: .previa/index.html -> .previa/painel-v2.html
import { readFileSync, writeFileSync } from 'node:fs';
const fonte = process.env.DADOS || '../relatorios/painel-v2/dados.json';
const dados = readFileSync(fonte, 'utf8').replace(/</g, '\\u003c');
const html = readFileSync('.previa/index.html', 'utf8')
  .replace('<!--DADOS-->', `<script>window.__DADOS__=${dados}</script>`);
writeFileSync('.previa/painel-v2.html', html);
console.log('.previa/painel-v2.html', Math.round(html.length / 1024), 'KB');
