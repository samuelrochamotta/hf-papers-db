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
export const SOL_ROT = { forte: 'Forte', firme: 'Firme', basico: 'Básico', fragil: 'Frágil', sem_leitura: 'Sem leitura' };
export const ESFORCO = ['Só informa', 'Configurar', 'Integrar', 'Reimplementar', 'Treinar grande', 'Fora de alcance'];
export const EIXOS = [
  ['ganho', 'Ganho'], ['solidez', 'Solidez'], ['abertura', 'Abertura'],
  ['facilidade', 'Facilidade'], ['amplitude', 'Amplitude'], ['atencao', 'Atenção'],
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
export const curto = (t) => {
  let s = String(t || '').split(/[:—–]/)[0].trim();
  if (s.length > 22) s = s.split(/\s+/).slice(0, 3).join(' ');
  return s.length > 24 ? s.slice(0, 22) + '…' : s;
};
export const dataCurta = (d) => d ? `${+d.slice(8, 10)}/${+d.slice(5, 7)}` : '';

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
  if (l.k === 'sol') return `Solidez: ${SOL_ROT[l.v]}`;
  if (l.k === 'esf') return `Esforço: ${ESFORCO[l.v]}`;
  if (l.k === 'fam') return `Constrói ou mede: ${l.v}`;
  return '';
}

export function linhaFixa(p) {
  const partes = [ENTREGA[p.ent] || p.ent];
  if (p.cam) partes.push(CAMADA[p.cam] || p.cam);
  if (p.best) partes.push(`${sgn(p.best.r)}% contra ${p.best.x}`);
  partes.push(p.rel ? 'algo liberado' : p.prom ? 'só prometido' : 'nada liberado');
  return partes.join(' · ');
}
