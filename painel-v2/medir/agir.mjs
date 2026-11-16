// Cliente da sessao de uso simulado (ver sessao.mjs).
const [porta, tipo, ...r] = process.argv.slice(2);
const corpo = { tipo };
if (tipo === 'iniciar') corpo.tarefa = r[0];
if (tipo === 'clicar' || tipo === 'passar') { corpo.x = r[0]; corpo.y = r[1]; }
if (tipo === 'rolar') corpo.dy = r[0];
if (tipo === 'tecla') corpo.k = r[0];
if (tipo === 'responder') { corpo.tarefa = r[0]; corpo.resposta = r.slice(1).join(' '); }
const res = await fetch(`http://127.0.0.1:${porta}/`, { method: 'POST', body: JSON.stringify(corpo) });
console.log(await res.text());
