"""Auditoria retomavel de toda a base, sem inferir v1 a partir de datas HF."""
from __future__ import annotations

import datetime as dt
import json
from collections import Counter
from pathlib import Path

from . import db
from .fontes.arxiv_client import ClienteArxiv, URL


def diferenca(fim, inicio):
    return (dt.date.fromisoformat(fim) - dt.date.fromisoformat(inicio)).days if fim and inicio else None


def auditar(conn, *, cache: Path, aplicar=False, revalidar=False, cliente=None, apenas_pendentes=False):
    cache.mkdir(parents=True, exist_ok=True)
    rows = [dict(r) for r in conn.execute('SELECT * FROM dim_paper ORDER BY paper_id')]
    if apenas_pendentes:
        rows = [r for r in rows if not r.get('data_arxiv_v1')]
    respostas, erros = {}, {}
    consultar = []
    for r in rows:
        pid = r['paper_id']
        if r.get('data_arxiv_v1') and r.get('arxiv_v1_verificado_em') and not revalidar:
            respostas[pid] = {'data': r['data_arxiv_v1'], 'verificado_em': r['arxiv_v1_verificado_em']}
            continue
        path = cache / (pid.replace('/', '_') + '.json')
        if path.exists() and not revalidar:
            try:
                valor = json.loads(path.read_text())
                dt.date.fromisoformat(valor['data'])
                dt.datetime.fromisoformat(valor['verificado_em'])
                if valor['paper_id'] != pid or valor['fonte'] != URL:
                    raise ValueError('cache incompatível')
                respostas[pid] = valor
                continue
            except (ValueError, KeyError, TypeError):
                pass
        consultar.append(pid)
    cli = cliente or ClienteArxiv()
    try:
        for inicio in range(0, len(consultar), 100):
            lote = consultar[inicio:inicio + 100]
            try:
                datas = cli.consultar(lote)
                for pid in lote:
                    if pid not in datas:
                        erros[pid] = 'id ausente ou published invalido na resposta arXiv'
                        continue
                    valor = {'paper_id': pid, 'data': datas[pid], 'verificado_em': db.agora(), 'fonte': URL}
                    respostas[pid] = valor
                    path = cache / (pid.replace('/', '_') + '.json')
                    tmp = path.with_suffix('.tmp')
                    tmp.write_text(json.dumps(valor))
                    tmp.replace(path)
            except RuntimeError as exc:
                erros.update({pid: str(exc) for pid in lote})
    finally:
        if cliente is None:
            cli.fechar()
    registros = []
    for r in rows:
        pid = r['paper_id']
        valor = respostas.get(pid)
        v1 = valor['data'] if valor else None
        hf = r.get('data_arxiv_informada_hf') or r.get('data_arxiv')
        anterior = diferenca(r['data_hf_daily'], hf)
        corrigida = diferenca(r['data_hf_daily'], v1)
        conflito = bool(v1 and r.get('data_arxiv_v1') and v1 != r['data_arxiv_v1'])
        if aplicar and v1 and not conflito:
            conflito = not db.registrar_arxiv_v1(conn, pid, v1, valor['verificado_em'])
        candidata = v1
        if conflito:
            atual = conn.execute('SELECT data_arxiv_v1 FROM dim_paper WHERE paper_id=?', (pid,)).fetchone()
            v1 = atual[0] if atual else None
            corrigida = diferenca(r['data_hf_daily'], v1)
        resultado = 'conflito_v1' if conflito else ('verificado' if v1 else 'pendente')
        registros.append({'paper_id': pid, 'data_hf_daily': r['data_hf_daily'],
            'data_arxiv_informada_hf': hf, 'data_arxiv_v1': v1, 'v1_candidata': candidata, 'v1_armazenada_antes': r.get('data_arxiv_v1'),
            'defasagem_anterior': anterior, 'defasagem_corrigida': corrigida,
            'diferenca_dias': corrigida - anterior if corrigida is not None and anterior is not None else None,
            'divergencia_metadados': bool(v1 and hf and v1 != hf),
            'resultado': resultado, 'motivo': 'v1 candidata diverge da armazenada; preservada a data existente' if conflito else erros.get(pid),
            'fonte': URL, 'verificado_em': r.get('arxiv_v1_verificado_em') if conflito else (valor['verificado_em'] if valor else None)})
    resumo = dict(Counter(r['resultado'] for r in registros))
    resumo.update(total=len(registros),
        negativos_resolvidos=sum(r['defasagem_anterior'] is not None and r['defasagem_anterior'] < 0 and r['defasagem_corrigida'] is not None and r['defasagem_corrigida'] >= 0 for r in registros),
        positivos_ou_zeros_alterados=sum(r['defasagem_anterior'] is not None and r['defasagem_anterior'] >= 0 and r['diferenca_dias'] not in (None, 0) for r in registros),
        inalterados=sum(r['diferenca_dias'] == 0 for r in registros),
        negativos_restantes=sum(r['defasagem_corrigida'] is not None and r['defasagem_corrigida'] < 0 for r in registros))
    return {'gerado_em': db.agora(), 'aplicado': aplicar, 'resumo': resumo, 'papers': registros}
