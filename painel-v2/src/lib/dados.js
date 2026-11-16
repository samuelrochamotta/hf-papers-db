// Rotulos, carga e contas leves de apresentacao. As contas de verdade
// (deltas, solidez, esforco, radar) chegam prontas do Python
// (src/hfpapers/leitura/derivar.py): aqui so se agrega para desenhar.

// Tudo que vem do paper (titulo, nomes, URLs) e texto de fora: escapa antes de
// entrar em HTML de tooltip e so aceita link http(s).
const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ESC[c]);
export const urlSegura = (u) => (typeof u === 'string' && /^\s*https?:\/\//i.test(u) ? u.trim() : null);

export const ARENA = {
  matematica_raciocinio: 'Matemática', codigo: 'Código', agentes_ferramentas: 'Agentes',
  conhecimento_linguagem: 'Linguagem', compreensao_multimodal: 'Multimodal',
  geracao_imagem: 'Imagem', geracao_video_mundo: 'Vídeo e mundo', fala_audio: 'Fala e áudio',
  robotica_acao: 'Robótica', '3d_graficos': '3D', ciencia_dominio: 'Ciência',
  seguranca_confiabilidade: 'Segurança', outra: 'Outras',
};
export const ENTREGA = {
  metodo: 'Método', sistema: 'Sistema', modelo: 'Modelo', dados: 'Dados', medida: 'Medida',
  estudo: 'Estudo', panorama_posicao: 'Panorama',
};
export const CAMADA = {
  dados: 'Dados', arquitetura_pretreino: 'Arquitetura e pré-treino', pos_treino: 'Pós-treino',
  inferencia_serving: 'Inferência', contexto_raciocinio: 'Contexto e raciocínio',
  agente_harness: 'Agentes e harness', avaliacao: 'Avaliação', seguranca_controle: 'Segurança',
};
export const SOLIDEZ = ['forte', 'firme', 'basico', 'fragil', 'sem_leitura'];
export const SOL_ROT = { forte: 'Forte', firme: 'Firme', basico: 'Básica', fragil: 'Frágil', sem_leitura: 'Não lida' };
export const ESFORCO = ['Só informa', 'Configurar', 'Integrar', 'Reimplementar', 'Treinar grande', 'Fora de alcance'];
// Um nome por conceito: o eixo do radar, a coluna do indice e a linha da
// comparacao usam a mesma palavra.
export const EIXOS = [
  ['ganho', 'Ganho'], ['solidez', 'Prova'], ['abertura', 'Abertura'],
  ['facilidade', 'Adoção'], ['amplitude', 'Amplitude'], ['atencao', 'Votos'],
];
export const EIXO_DICA = {
  ganho: 'mediana do ganho contra o melhor rival externo',
  solidez: 'sinais de prova lidos no texto',
  abertura: 'código, pesos, dados e demo liberados',
  facilidade: 'quanto custa adotar',
  amplitude: 'benchmarks com resultado próprio',
  atencao: 'percentil de votos no período',
};
export const SIG = [
  ['var', 'Variância reportada'], ['n', 'Repetições suficientes'], ['ext', 'Compara com rival externo'],
  ['vit', 'Vence em 70% ou mais'], ['evid', 'Evidência humana ou real'], ['man', 'Manchete confere'],
  ['ress', 'Admite limites'],
];
export const ART = { codigo: 'Código', pesos: 'Pesos', dados: 'Dados', demo: 'Demo' };
export const ART_EST = { liberado: 'liberado', prometido: 'prometido', so_pagina: 'só página', ausente: 'ausente', nao_lido: 'não lido' };
export const SOL_FRASE = { forte: 'Prova forte', firme: 'Prova firme', basico: 'Prova básica', fragil: 'Prova frágil', sem_leitura: 'Prova não lida' };

export const FAMILIAS = [
  [/qwen/i, 'Qwen'], [/deepseek/i, 'DeepSeek'], [/glm/i, 'GLM'], [/gpt|o3|o4/i, 'GPT'],
  [/claude|opus|sonnet|haiku|fable/i, 'Claude'], [/gemini|gemma/i, 'Gemini e Gemma'],
  [/llama/i, 'Llama'], [/π0|pi0|pi-0/i, 'π0'], [/kimi/i, 'Kimi'], [/mistral/i, 'Mistral'],
  [/libero/i, 'LIBERO'], [/robotwin/i, 'RoboTwin'], [/aime|amc|math-500|olympiad|gsm8k/i, 'Matemática'],
  [/livecodebench|mbpp|codecontests|humaneval|swe/i, 'Código'],
];
export const familia = (n) => { for (const [re, f] of FAMILIAS) if (re.test(n || '')) return f; return n; };

export async function carregar() {
  if (typeof window !== 'undefined' && window.__DADOS__) return window.__DADOS__;
  const r = await fetch('dados.json', { cache: 'no-cache' });
  if (!r.ok) throw new Error(`dados.json: HTTP ${r.status}`);
  return r.json();
}

// Eixo nao lido nao e zero. No radar, o vertice nao lido vai para o ponto em
// que a reta entre os vizinhos lidos cruza o eixo: o poligono passa reto por
// ele, como se o eixo nao existisse. Sem vizinhos que fechem menos de 180 graus,
// fica no centro.
export function radarValores(vals) {
  const n = vals.length, passo = (2 * Math.PI) / n;
  return vals.map((v, k) => {
    if (v != null) return v;
    let dl = 1; while (dl < n && vals[(k - dl + n) % n] == null) dl++;
    let dr = 1; while (dr < n && vals[(k + dr) % n] == null) dr++;
    if (dl >= n) return 0;
    const t1 = dl * passo, t2 = dr * passo;
    if (t1 + t2 >= Math.PI - 1e-9) return 0;
    const a = vals[(k - dl + n) % n], b = vals[(k + dr) % n];
    const den = a * Math.sin(t1) + b * Math.sin(t2);
    return den > 0 ? Math.round((a * b * Math.sin(t1 + t2)) / den * 10) / 10 : 0;
  });
}

export const median = (xs) => {
  const a = xs.filter((v) => v != null).sort((x, y) => x - y);
  if (!a.length) return null;
  const m = a.length >> 1;
  return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2;
};
export const fmt = (n, d = 1) => n == null ? '–'
  : Math.abs(n) >= 100 ? Math.round(n).toLocaleString('pt-BR')
  : n.toLocaleString('pt-BR', { maximumFractionDigits: d });
export const sgn = (n, d = 1) => n == null ? '–' : (n > 0 ? '+' : n < 0 ? '−' : '') + fmt(Math.abs(n), d);
// Nome curto do paper: o que vem antes de ":" ou travessao, cortado em
// palavra inteira, com reticencias quando corta.
export const curto = (t, max = 22) => {
  const s = String(t || '').split(/[:—–]| - /)[0].trim();
  if (s.length <= max) return s;
  let out = '';
  for (const w of s.split(/\s+/)) { if ((out + ' ' + w).trim().length > max) break; out = (out + ' ' + w).trim(); }
  return (out || s.slice(0, max)).replace(/[,;.]$/, '') + '…';
};
export const dataCurta = (d) => d ? `${+d.slice(8, 10)}/${+d.slice(5, 7)}` : '';

// Ordens do indice (e do anterior/proximo do paper). Em toda ordem, paper sem
// o dado vai para o fim: "nao lido" nunca disputa posicao com valor medido.
export const ORDENS = [
  ['votos', 'Votos'], ['recentes', 'Data'], ['solidez', 'Prova'], ['ganho', 'Ganho'],
  ['facilidade', 'Adoção'], ['abertura', 'Abertura'], ['amplitude', 'Amplitude'],
];
const RANK_SOL = { forte: 0, firme: 1, basico: 2, fragil: 3, sem_leitura: 4 };
// Ganho do paper: mediana do ganho relativo contra o melhor rival externo, a
// mesma conta do eixo "ganho" do radar. E o numero que aparece em toda parte.
const _ganho = new WeakMap();
export function ganhoDe(p) {
  if (_ganho.has(p)) return _ganho.get(p);
  const rx = p.res.map((r) => r.rext).filter((v) => v != null);
  const g = rx.length ? median(rx) : null;
  _ganho.set(p, g);
  return g;
}
const CHAVE = {
  votos: (p) => p.u,
  recentes: (p) => Date.parse(p.d || '1970-01-01'),
  solidez: (p) => (p.sol === 'sem_leitura' ? null : 100 - RANK_SOL[p.sol] * 25 + (p.radar.solidez ?? 0) / 100),
  ganho: ganhoDe,
  facilidade: (p) => p.radar.facilidade,
  abertura: (p) => p.radar.abertura,
  amplitude: (p) => p.radar.amplitude,
};
export function ordenar(papers, ordem) {
  const k = CHAVE[ordem] || CHAVE.votos;
  return [...papers].sort((x, y) => {
    const a = k(x), b = k(y);
    if (a == null || b == null) return (a == null) - (b == null) || y.u - x.u;
    return b - a || y.u - x.u;
  });
}
// quantos papers tem o dado da ordem escolhida (os demais ficam sob "nao lido")
export const comDado = (papers, ordem) => papers.filter((p) => (CHAVE[ordem] || CHAVE.votos)(p) != null).length;

// Periodos tirados dos dados: so entra a opcao que muda o recorte. Se "14 dias"
// mostra o mesmo que "Tudo", ela nao aparece.
export function periodos(dados) {
  if (!dados || !dados.dias.length) return [['tudo', 'Tudo', dados ? dados.papers.length : 0]];
  const ult = dados.dias[dados.dias.length - 1], total = dados.papers.length;
  const corte = (n) => { const d = new Date(ult); d.setDate(d.getDate() - (n - 1)); return d.toISOString().slice(0, 10); };
  const out = []; let antes = 0;
  for (const [n, rot] of [[1, 'Último dia'], [7, '7 dias'], [14, '14 dias'], [30, '30 dias']]) {
    const q = dados.papers.filter((p) => (p.d || '') >= corte(n)).length;
    if (q > antes && q < total) { out.push([String(n), rot, q]); antes = q; }
  }
  out.push(['tudo', 'Tudo', total]);
  return out;
}
export function noPeriodo(lista, dias, periodo) {
  if (periodo === 'tudo' || !dias.length) return lista;
  const lim = new Date(dias[dias.length - 1]); lim.setDate(lim.getDate() - (+periodo - 1));
  const corte = lim.toISOString().slice(0, 10);
  return lista.filter((p) => (p.d || '') >= corte);
}

// Busca simples: titulo, organizacao, arena, entrega, camada e entidades.
const norm = (s) => String(s || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
export function buscar(papers, q) {
  const termos = norm(q).split(/\s+/).filter(Boolean);
  if (!termos.length) return papers;
  return papers.filter((p) => {
    const alvo = norm([p.t, p.org, p.id, ENTREGA[p.ent], CAMADA[p.cam], ...p.ar.map((a) => ARENA[a]), ...p.ents.map((e) => e[0])].join(' '));
    return termos.every((t) => alvo.includes(t));
  });
}

// Cobertura da leitura do recorte: e o denominador de tudo o que o painel afirma.
export function cobertura(papers, faltam) {
  const inteira = papers.filter((p) => p.L?.c === 'completa').length;
  const insuf = papers.filter((p) => p.sol === 'sem_leitura').length;
  return { inteira, parcial: papers.length - inteira - insuf, insuf, fila: faltam.length, total: papers.length + faltam.length };
}
// Artefatos liberados, em palavras: "código e pesos"
export function liberados(p) {
  const ks = Object.entries(p.ab).filter(([, v]) => v === 'liberado').map(([k]) => ART[k].toLowerCase());
  return ks.length ? ks.join(ks.length === 2 ? ' e ' : ', ') : '';
}
export const HW = { nao_reportado: 'Não reportado', '1_gpu': '1 GPU', '1_no': '1 nó', cluster: 'Cluster' };

// Lente vinda do endereco: so chaves e valores conhecidos.
export function lenteValida(k, v) {
  if (k === 'ar' && v in ARENA) return { k, v };
  if (k === 'sol' && v in SOL_ROT) return { k, v };
  if (k === 'esf' && /^\d$/.test(v) && ESFORCO[+v]) return { k, v: +v };
  if (k === 'fam' && v) return { k, v };
  return null;
}

// Lentes: uma de cada vez, como no prototipo aprovado.
export function aplicaLente(papers, lente) {
  if (!lente) return papers;
  const { k, v } = lente;
  if (k === 'ar') return papers.filter((p) => p.ar.includes(v));
  if (k === 'sol') return papers.filter((p) => p.sol === v);
  if (k === 'esf') return papers.filter((p) => p.esf === v);
  if (k === 'fam') return papers.filter((p) => p.ents.some((e) => familia(e[0]) === v));
  return papers;
}
export function rotuloLente(l) {
  if (!l) return '';
  if (l.k === 'ar') return `Arena: ${ARENA[l.v] || l.v}`;
  if (l.k === 'sol') return `Prova: ${SOL_ROT[l.v]}`;
  if (l.k === 'esf') return `Adoção: ${ESFORCO[l.v]}`;
  if (l.k === 'fam') return `Família: ${l.v}`;
  return '';
}

export function linhaFixa(p) {
  const partes = [ENTREGA[p.ent] || p.ent];
  if (p.cam) partes.push(CAMADA[p.cam] || p.cam);
  if (p.best) partes.push(`${sgn(p.best.r)}% contra ${p.best.x}`);
  partes.push(p.rel ? 'algo liberado' : p.prom ? 'só prometido' : 'nada liberado');
  return partes.join(' · ');
}

const MESES = ['jan.', 'fev.', 'mar.', 'abr.', 'maio', 'jun.', 'jul.', 'ago.', 'set.', 'out.', 'nov.', 'dez.'];
// "2 a 13 de nov." ou "28 de out. a 13 de nov."
export function intervalo(a, b) {
  if (!a || !b) return '';
  const [da, ma] = [+a.slice(8, 10), +a.slice(5, 7) - 1], [db, mb] = [+b.slice(8, 10), +b.slice(5, 7) - 1];
  if (a === b) return `${db} de ${MESES[mb]}`;
  return ma === mb ? `${da} a ${db} de ${MESES[mb]}` : `${da} de ${MESES[ma]} a ${db} de ${MESES[mb]}`;
}
export const plural = (n, um, varios) => `${n.toLocaleString('pt-BR')} ${n === 1 ? um : varios}`;

// O valor de cada eixo na unidade dele (o radar usa a nota de 0 a 100; a
// tabela e a comparacao mostram o fato). null quando a leitura nao alcancou.
export const nBench = (p) => (p.radar.amplitude == null ? null : new Set(p.res.map((r) => r.b)).size);
export const FATO = {
  ganho: (p) => (ganhoDe(p) == null ? null : `${sgn(ganhoDe(p))}%`),
  solidez: (p) => (p.sol === 'sem_leitura' ? null : SOL_ROT[p.sol]),
  abertura: (p) => liberados(p) || (p.prom ? 'só prometido' : p.radar.abertura == null ? null : 'nada liberado'),
  facilidade: (p) => (p.radar.facilidade == null ? null : ESFORCO[p.esf]),
  amplitude: (p) => (nBench(p) == null ? null : plural(nBench(p), 'benchmark', 'benchmarks')),
  atencao: (p) => `${p.u.toLocaleString('pt-BR')} votos`,
};
export const SEM_FATO = { ganho: 'sem rival externo', solidez: 'não lida', abertura: 'não lida', facilidade: 'não medida', amplitude: 'sem benchmark próprio', atencao: '–' };
