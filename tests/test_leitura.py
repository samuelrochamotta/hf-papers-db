"""Leitura do texto completo (painel v2, ADR 007): texto, extracao, contas."""

import collections
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from hfpapers import db
from hfpapers.config import Config
from hfpapers import leitura
from hfpapers.leitura import derivar, extrator, texto
from hfpapers.llm.cliente import Resposta, Uso

FIX = Path(__file__).parent / "fixtures" / "leitura"

HTML = """<html><body><div class="ltx_page_main"><article class="ltx_document">
<h1 class="ltx_title">Um Metodo</h1>
<div class="ltx_authors">Fulano, Beltrano</div>
<section><h2>1 Introduction</h2><p>We propose X. It reaches <math alttext="\\alpha=2">a</math> on the task.</p></section>
<section><h2>4 Results</h2>
<figure class="ltx_table"><figcaption>Table 2: Main results on LIBERO.</figcaption>
<table><tr><th>Method</th><th>SR</th></tr><tr><td>Ours</td><td>87.4</td></tr><tr><td>Baseline</td><td>85.1</td></tr></table></figure>
<p>Our method outperforms all baselines by 2.3 points.</p></section>
<section class="ltx_bibliography"><h2>References</h2><p>[1] Nao deve aparecer 99.9</p></section>
</article></div></body></html>"""


# ── texto ───────────────────────────────────────────────────────────────────


def test_html_vira_markdown_sem_referencias():
    tp = texto.html_para_texto("2611.00001", HTML)
    assert "## 1 Introduction" in tp.texto
    assert "$\\alpha=2$" in tp.texto
    assert "[Tabela 1] Table 2: Main results on LIBERO." in tp.texto
    assert "Ours | 87.4" in tp.texto
    assert "Nao deve aparecer" not in tp.texto
    assert "Fulano" not in tp.texto
    assert tp.tabelas == 1 and tp.secoes[:2] == ["Um Metodo", "1 Introduction"]


def test_teto_corta_no_ultimo_titulo_e_registra():
    tp = texto.html_para_texto("x", HTML)
    corte = tp.texto.index("## 4 Results") + 5
    tp = texto.aplicar_teto(tp, corte)
    assert "4 Results" not in tp.texto
    assert tp.cortado_em == "1 Introduction" and not tp.chegou_ao_fim


def test_sem_html_cai_para_o_abstract():
    http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404)))
    tp = texto.texto_do_paper("2611.00001", abstract="So o resumo.", cliente=http)
    assert tp.fonte == "abstract" and tp.texto == "So o resumo." and not tp.chegou_ao_fim


def test_conferidor_acha_trecho_e_numero():
    c = texto.Conferidor(texto.html_para_texto("x", HTML).texto)
    assert c.trecho("our method outperforms all baselines by 2.3 points") is True
    assert c.trecho("Our method … by 2.3 points.") is True
    assert c.trecho("Our method beats everything by a wide margin") is False
    assert c.numero(87.4) is True and c.numero(88.0) is False
    assert c.numero(99.9) is False  # so existia nas referencias


# ── esquema e extracao ──────────────────────────────────────────────────────


def _cfg():
    return Config(raiz=Path(__file__).resolve().parents[1])


def test_esquema_api_tira_o_que_a_saida_estruturada_recusa():
    sch = extrator.esquema_api(extrator.carregar_esquema(_cfg()))
    s = json.dumps(sch)
    for chave in ('"maxLength"', '"maxItems"', '"pattern"', '"$schema"'):
        assert chave not in s
    sec = sch["properties"]["entrega"]["properties"]["secundaria"]
    assert sec["anyOf"][1] == {"type": "null"} and None not in sec["anyOf"][0]["enum"]


class _Cliente:
    """Duble do ClienteLLM: devolve as respostas na ordem e guarda as chamadas."""

    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.chamadas = []

    def chamar(self, **kw):
        self.chamadas.append(kw)
        dados = self.respostas.pop(0)
        return Resposta(dados, Uso(40_000, 3_000, 0.0055, 1), kw["modelo"], 1, 1200)


def _extracao():
    return {
        "id": "errado", "titulo": "Um Metodo",
        "leitura": {"fonte_texto": "html", "cobertura": "parcial", "termina_em": None,
                    "tem_apendice": False, "secao_limitacoes": "ausente"},
        "entrega": {"primaria": "metodo", "secundaria": None, "trecho": "We propose X.", "secao": "1"},
        "alegacoes": [{"tipo": "superlativa", "trecho": "outperforms all baselines by 2.3 points", "numero": 2.3},
                      {"tipo": "tese", "trecho": "frase inventada que nao esta no paper", "numero": None}],
        "resultados": [{"tabela": "Tabela 2", "benchmark": "LIBERO", "arena": "robotica_acao", "metrica": "SR",
                        "direcao": "maior_melhor", "linhas": [
                            {"nome": "Ours", "papel": "nosso", "fechado": False, "valor": 87.4, "pm": None},
                            {"nome": "Baseline", "papel": "externo", "fechado": False, "valor": 85.1, "pm": None},
                            {"nome": "Fantasma", "papel": "externo", "fechado": False, "valor": 91.0, "pm": None}]}],
    }


def test_extrair_confere_e_fixa_a_cobertura():
    tp = texto.html_para_texto("2611.00001", HTML)
    cli = _Cliente([_extracao()])
    lt = extrator.extrair(tp, {"titulo": "Um Metodo"}, cliente=cli, cfg=_cfg())
    kw = cli.chamadas[0]
    assert kw["modelo"] == "anthropic/claude-haiku-5.5" and kw["etapa"] == "leitura"
    assert kw["response_format"]["type"] == "json_schema" and kw["response_format"]["json_schema"]["strict"]
    assert kw["esforco_raciocinio"] == "low" and kw["paper_id"] == "2611.00001"
    assert lt.dados["id"] == "2611.00001"
    assert lt.dados["leitura"]["cobertura"] == "completa"  # o codigo decide, nao o modelo
    assert lt.conferencia == {"trechos": 3, "trechos_ok": 2, "numeros": 3, "numeros_ok": 2}
    assert lt.custo_usd == pytest.approx(0.0055) and lt.tokens_entrada == 40_000


def test_link_de_artefato_so_aceita_http():
    o = {"artefatos": [{"tipo": "codigo", "estado": "liberado", "url": "javascript:alert(1)"},
                       {"tipo": "pesos", "estado": "liberado", "url": " https://huggingface.co/x "},
                       {"tipo": "dados", "estado": "prometido", "url": None}],
         "leitura": {"cobertura": "completa"}}
    assert [a[2] for a in derivar.derivar(o, {})["art"]] == [None, "https://huggingface.co/x", None]


def test_leitura_tem_prazo_proprio():
    cfg = extrator.config_leitura(_cfg())
    assert cfg.llm.prazo_total_s == 300 and cfg.llm.timeout_s >= 300
    assert _cfg().llm.prazo_total_s == 90  # os estagios A e B nao mudam


def test_numero_nao_conferido_nao_vira_rival():
    tp = texto.html_para_texto("2611.00001", HTML)
    lt = extrator.extrair(tp, {}, cliente=_Cliente([_extracao()]), cfg=_cfg())
    p = derivar.derivar(lt.dados, {"u": 10, "d": "2026-11-10"})
    r = p["res"][0]
    assert r["ext"][0] == "Baseline"  # a linha de numero nao conferido nao vira rival
    assert r["dext"] == pytest.approx(2.3) and r["e"] == "ganha"
    assert [a[0] for a in p["aleg"]] == ["superlativa"]  # trecho nao achado fica fora


# ── contas ──────────────────────────────────────────────────────────────────


def _amostra():
    from gerar_painel_v2 import de_arquivos
    return de_arquivos(FIX / "extracoes", FIX / "amostra.json")


def test_derivar_reproduz_o_prototipo_v3():
    d = _amostra()
    assert len(d["papers"]) == 28 and len(d["faltam"]) == 2
    sol = collections.Counter(p["sol"] for p in d["papers"])
    assert sol == {"sem_leitura": 9, "firme": 9, "forte": 5, "basico": 3, "fragil": 2}
    estados = collections.Counter(r["e"] for p in d["papers"] for r in p["res"])
    assert estados["ganha"] == 40 and estados["perde"] == 16


def test_radar_fica_entre_0_e_100_ou_nao_lido():
    d = _amostra()
    for p in d["papers"]:
        assert set(p["radar"]) == set(derivar.EIXOS)
        for v in p["radar"].values():
            assert v is None or 0 <= v <= 100
        assert p["radar"]["atencao"] is not None
    topo = max(d["papers"], key=lambda p: p["u"])
    assert topo["radar"]["atencao"] >= 95


def test_esforco_zero_nao_vira_facilidade_maxima():
    p = derivar.derivar({"entrega": {"primaria": "panorama_posicao"}, "leitura": {"cobertura": "completa"}}, {})
    assert p["esf"] == 0 and p["radar"]["facilidade"] is None


# ── banco e orquestracao ────────────────────────────────────────────────────


def test_rodar_le_grava_e_nao_repete(tmp_path):
    conn = db.conectar(tmp_path / "t.db")
    db.upsert_paper(conn, {"paper_id": "2611.00001", "titulo": "Um Metodo", "data_hf_daily": "2026-11-10",
                           "primeiro_visto_em": "2026-11-10T09:00:00"})
    http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, text=HTML)))
    cfg = _cfg()
    cli = _Cliente([_extracao()])
    import datetime as dt
    hoje = dt.date(2026, 11, 14)
    assert [c["paper_id"] for c in leitura.candidatos(conn, cfg, dias=7, min_votos=0, hoje=hoje)] == ["2611.00001"]
    r = leitura.rodar(conn, cfg, ids=["2611.00001"], cliente=cli, http=http)
    assert r.lidos == ["2611.00001"] and not r.falhas
    linha = dict(conn.execute("SELECT * FROM leitura_texto").fetchone())
    assert linha["cobertura"] == "completa" and linha["numeros_ok"] == 2
    assert json.loads(linha["extracao"])["resultados"][0]["linhas"][2]["_ok"] is False
    assert leitura.candidatos(conn, cfg, dias=7, min_votos=0, hoje=hoje) == []
    conn.close()
