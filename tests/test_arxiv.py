import datetime as dt
import json
import sqlite3

import httpx
import pytest

from hfpapers import db
from hfpapers.auditoria_arxiv import auditar
from hfpapers.fontes.arxiv_client import ClienteArxiv


class Fonte:
    def __init__(self, datas):
        self.datas = datas
        self.chamadas = 0

    def consultar(self, ids):
        self.chamadas += 1
        return {p: self.datas[p] for p in ids if p in self.datas}


def banco():
    conn = db.conectar(':memory:')
    db.upsert_paper(conn, {'paper_id': '2608.19269', 'titulo': 'teste', 'primeiro_visto_em': '2026-08-28T00:00:00',
        'data_arxiv': '2026-08-29', 'data_hf_daily': '2026-08-28'})
    return conn


def test_migracao_legado_e_idempotencia():
    conn = sqlite3.connect(':memory:', isolation_level=None)
    conn.row_factory = sqlite3.Row
    schema = db.SCHEMA_SQL.read_text()
    schema = '\n'.join(line for line in schema.splitlines() if not any(k in line for k in ('data_arxiv_informada_hf', 'data_arxiv_v1', 'arxiv_v1_verificado_em')))
    conn.executescript(schema)
    conn.execute("INSERT INTO dim_paper (paper_id,titulo,data_arxiv,primeiro_visto_em) VALUES ('x','x','2026-08-29','2026-08-29')")
    db.migrar(conn)
    db.migrar(conn)
    r = conn.execute('SELECT * FROM dim_paper').fetchone()
    assert r['data_arxiv_informada_hf'] == '2026-08-29'
    assert r['data_arxiv_v1'] is None


def test_auditar_readonly_aplicar_cache_conflito(tmp_path):
    conn = banco()
    fonte = Fonte({'2608.19269': '2026-08-18'})
    r = auditar(conn, cache=tmp_path, cliente=fonte)
    assert r['papers'][0]['defasagem_corrigida'] == 10
    assert conn.execute('SELECT data_arxiv_v1 FROM dim_paper').fetchone()[0] is None
    r = auditar(conn, cache=tmp_path, cliente=fonte, aplicar=True)
    assert fonte.chamadas == 1
    assert r['resumo']['negativos_resolvidos'] == 1
    db.upsert_paper(conn, {'paper_id': '2608.19269', 'titulo': 'teste', 'primeiro_visto_em': '2026-08-28T00:00:00', 'data_arxiv': '2026-09-01'})
    assert conn.execute('SELECT data_arxiv_v1 FROM dim_paper').fetchone()[0] == '2026-08-18'
    fonte.datas['2608.19269'] = '2026-08-19'
    r = auditar(conn, cache=tmp_path, cliente=fonte, aplicar=True, revalidar=True)
    assert r['resumo']['conflito_v1'] == 1
    assert conn.execute('SELECT data_arxiv_v1 FROM dim_paper').fetchone()[0] == '2026-08-18'
    with pytest.raises(ValueError):
        db.upsert_paper(conn, {'paper_id': '2608.19269', 'data_arxiv_v1': '2026-09-01'})


@pytest.mark.parametrize('hf,antiga,v1,esperado', [
    ('2026-08-28','2026-08-25','2026-08-18',10),
    ('2026-08-28','2026-08-28','2026-08-18',10),
    ('2026-08-17','2026-08-25','2026-08-18',-1),
    (None,'2026-08-25','2026-08-18',None),
])
def test_sinais(tmp_path, hf, antiga, v1, esperado):
    conn = banco()
    conn.execute('UPDATE dim_paper SET data_hf_daily=?, data_arxiv_informada_hf=?', (hf, antiga))
    r = auditar(conn, cache=tmp_path, cliente=Fonte({'2608.19269':v1}))
    assert r['papers'][0]['defasagem_corrigida'] == esperado


def test_pendente_retentativa(tmp_path):
    conn = banco()
    r = auditar(conn, cache=tmp_path, cliente=Fonte({}), aplicar=True)
    assert r['resumo']['pendente'] == 1
    r = auditar(conn, cache=tmp_path, cliente=Fonte({'2608.19269':'2026-08-18'}), aplicar=True)
    assert r['resumo']['verificado'] == 1


def test_cliente_published_nao_updated():
    xml = '''<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/2608.19269v4</id><published>2026-08-18T10:00:00Z</published><updated>2026-08-29T10:00:00Z</updated></entry></feed>'''
    http = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, text=xml)))
    cli = ClienteArxiv(http)
    assert cli.consultar(['2608.19269']) == {'2608.19269':'2026-08-18'}


def test_cliente_retry(monkeypatch):
    import hfpapers.fontes.arxiv_client as m
    sleeps = []
    monkeypatch.setattr(m.time, 'sleep', sleeps.append)
    responses = iter([httpx.Response(429, headers={'Retry-After':'8'}), httpx.Response(200, text='<feed xmlns="http://www.w3.org/2005/Atom"/>')])
    cli = ClienteArxiv(httpx.Client(transport=httpx.MockTransport(lambda req: next(responses))))
    cli.limitador.esperar = lambda: None
    assert cli.consultar(['x']) == {}
    assert sleeps == [8]


def test_regressao_13_papers(tmp_path):
    from pathlib import Path
    dados = json.loads((Path(__file__).parent / 'fixtures/arxiv_negativos_auditados.json').read_text())
    conn = db.conectar(':memory:')
    for r in dados:
        db.upsert_paper(conn, {k: r[k] for k in ['paper_id','data_arxiv','data_hf_daily']} |
            {'titulo':'regressao', 'primeiro_visto_em':'2026-09-08'})
    resultado = auditar(conn, cache=tmp_path, cliente=Fonte({r['paper_id']:r['arxiv_v1'] for r in dados}), aplicar=True)
    assert resultado['resumo']['negativos_resolvidos'] == 13
    esperado = {r['paper_id']:r['lag_v1'] for r in dados}
    assert {r['paper_id']:r['defasagem_corrigida'] for r in resultado['papers']} == esperado


def test_falha_externa_nao_bloqueia(tmp_path):
    class Indisponivel:
        def consultar(self, ids):
            raise RuntimeError('timeout')
    r = auditar(banco(), cache=tmp_path, cliente=Indisponivel(), aplicar=True)
    assert r['resumo']['pendente'] == 1
    assert r['papers'][0]['motivo'] == 'timeout'


def test_export_preserva_datas(cfg, tmp_path):
    import pyarrow.parquet as pq
    from hfpapers.estagios import export
    conn = banco()
    db.registrar_arxiv_v1(conn, '2608.19269', '2026-08-18', '2026-09-08T10:00:00')
    export.rodar(conn, cfg)
    row = pq.read_table(cfg.dir_marts / 'dim_paper.parquet').to_pylist()[0]
    assert row['data_arxiv_v1'] == dt.date(2026,8,18)
    assert row['data_arxiv_informada_hf'] == dt.date(2026,8,29)
    assert row['arxiv_v1_verificado_em'] == dt.datetime(2026,9,8,10)


def test_cli_readonly_nao_migra(tmp_path, monkeypatch):
    from typer.testing import CliRunner
    from hfpapers import __main__ as cli
    from hfpapers.config import Config
    from hfpapers.fontes.arxiv_client import ClienteArxiv
    cfg = Config()
    cfg.paths.banco = str(tmp_path / 'old.db')
    cfg.paths.logs = str(tmp_path / 'logs')
    conn = sqlite3.connect(cfg.caminho_banco)
    conn.execute('CREATE TABLE dim_paper (paper_id TEXT PRIMARY KEY, data_arxiv TEXT, data_hf_daily TEXT)')
    conn.execute("INSERT INTO dim_paper VALUES ('2608.19269','2026-08-29','2026-08-28')")
    conn.commit()
    conn.close()
    antes = cfg.caminho_banco.read_bytes()
    monkeypatch.setattr(cli, '_preparar', lambda: cfg)
    monkeypatch.setattr(ClienteArxiv, 'consultar', lambda self, ids: {'2608.19269':'2026-08-18'})
    out = CliRunner().invoke(cli.app, ['auditar-datas-arxiv','--relatorio',str(tmp_path/'audit.json')])
    assert out.exit_code == 0, out.output
    assert cfg.caminho_banco.read_bytes() == antes
    assert json.loads((tmp_path/'audit.json').read_text())['resumo']['negativos_resolvidos'] == 1


def test_pipeline_falha_arxiv_exporta(cfg, monkeypatch):
    from hfpapers import execucao
    from hfpapers.fontes.arxiv_client import ClienteArxiv
    conn = banco()
    def falha(self, ids):
        raise RuntimeError('indisponivel')
    monkeypatch.setattr(ClienteArxiv, 'consultar', falha)
    resultado = execucao.rodar(cfg=cfg, conn=conn, apenas=['datas_arxiv','export'])
    assert 'arxiv_pendente:2608.19269' in resultado.avisos
    assert (cfg.dir_marts / 'dim_paper.parquet').exists()


def test_conflito_relatorio_usa_v1_preservada(tmp_path):
    conn = banco()
    db.registrar_arxiv_v1(conn, '2608.19269', '2026-08-30', '2026-09-08T10:00:00')
    r = auditar(conn, cache=tmp_path, cliente=Fonte({'2608.19269':'2026-08-18'}), aplicar=True, revalidar=True)
    assert r['papers'][0]['v1_candidata'] == '2026-08-18'
    assert r['papers'][0]['data_arxiv_v1'] == '2026-08-30'
    assert r['papers'][0]['defasagem_corrigida'] == -2
    assert r['resumo']['negativos_resolvidos'] == 0
    assert r['resumo']['negativos_restantes'] == 1
