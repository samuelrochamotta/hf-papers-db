# Confere as respostas do teste de leitura (medir/leitura/perguntas.md).
#   python3 medir/leitura/pontuar.py <pasta com linhas-por-tela.json e r/*.json>
# Cada resposta e um JSON por leitor (X-1.json, O-2.json...); o gabarito e uma
# lista de expressoes que precisam aparecer todas. Grava leitura.json na pasta.
import glob
import json
import os
import re
import sys

S = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
linhas = json.load(open(f'{S}/linhas-por-tela.json'))
NAO = r'n[ãa]o d[áa] para saber'
# gabarito: lista de regex que precisam casar todas
G = {
 'Q1': [r'integrar', r'c[óo]digo'],
 'Q2': [r'\+?4[.,]2'],
 'Q3': [r'SLA|Few-Step'],
 'Q5': [r'rob[óo]tica', r'\b7\b|sete'],
 'Q6': [r'limpar|rob[óo]tica|arena'],
 'Q7': [r'\b5\b|cinco'],
 'Q8': [r'CoworkOS', r'Route Anything', r'SO-Arena'],
 'Q9': [r'\b(6[5-9]|7[0-5])\b'],
 'Q10': [r'DreamX'],
 'Q11': [r'\b3\b|tr[êe]s'],
 'Q12': [r'12[.,]7'],
 'Q13': [r'\b9\b|nove'],
 'Q14': [r'integrar'],
 'Q15': [r'\b4\b|quatro'],
 'Q16': [r'SLA'],
 'Q17': [r'SLA'],
 'Q18': [r'ganho', r'prova|solidez'],
 'Q19': [r'Confucius', r'\b93\b'],
 'Q20': [r'Confucius', r'4[.,]2'],
 'Q21': [r'abaixo'],
}
EXTRA_ERRADO = { 'Q18': r'abertura|ado[çc][ãa]o|facilidade|amplitude|votos|aten[çc][ãa]o' }   # eixo a mais invalida
GRUPOS = { 'indice (Q1-Q3)': ['Q1','Q2','Q3'], 'filtro (Q5-Q6)': ['Q5','Q6'], 'prova (Q7-Q9)': ['Q7','Q8','Q9'], 'ganho (Q10-Q12)': ['Q10','Q11','Q12'],
           'adocao (Q13-Q15)': ['Q13','Q14','Q15'], 'comparar (Q16-Q19)': ['Q16','Q17','Q18','Q19'], 'comparar celular (Q20-Q21)': ['Q20','Q21'] }
res = {}
for f in sorted(glob.glob(f'{S}/r/*.json')):
    nome = os.path.basename(f)[:-5]; cj = nome[0]
    try: r = json.load(open(f))
    except Exception as e: print(nome, 'JSON invalido', e); continue
    linha = {}
    for q, regs in G.items():
        a = str(r.get(q, ''))
        ok = all(re.search(x, a, re.I) for x in regs) and not re.search(NAO, a, re.I)
        if ok and q in EXTRA_ERRADO and re.search(EXTRA_ERRADO[q], a, re.I): ok = False
        linha[q] = 'certo' if ok else ('nao sabe' if re.search(NAO, a, re.I) else 'errado')
    q4 = re.search(r'\d+', str(r.get('Q4', '')))
    linha['Q4'] = int(q4.group()) if q4 else None
    res[nome] = { 'q': linha, 'conf': r.get('confianca', {}), 'dif': r.get('dificuldades', {}), 'resp': {k: r.get(k) for k in G} }
json.dump(res, open(f'{S}/leitura.json', 'w'), ensure_ascii=False, indent=1)
for cj in 'XYZO':
    ns = [n for n in res if n[0] == cj]
    print(f'== conjunto {cj} ({len(ns)} leitores; linhas por tela: {linhas.get(cj)}; Q4 respondido: {[res[n]["q"]["Q4"] for n in ns]})')
    tot = 0; n_q = 0
    for g, qs in GRUPOS.items():
        c = sum(res[n]['q'][q] == 'certo' for n in ns for q in qs); t = len(ns) * len(qs); tot += c; n_q += t
        err = [f'{n}:{q}={res[n]["q"][q]} ({str(res[n]["resp"][q])[:70]})' for n in ns for q in qs if res[n]['q'][q] != 'certo']
        conf = [res[n]['conf'].get(str(list(GRUPOS).index(g) + 1)) for n in ns]
        print(f'  {g}: {c}/{t}  confianca {conf}' + (''.join('\n      ' + e for e in err)))
    print(f'  TOTAL {tot}/{n_q}')
