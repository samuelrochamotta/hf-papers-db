"""O que `gerar_painel.py` grava: a pasta do site, o arquivo unico e a
pre-agregacao dos votos.

O site publico e uma pasta (`index.html`, `dados.json`, `fichas.json` e o
ECharts); a previa e um `.html` com tudo embutido. A serie de snapshots nao
viaja mais: `atencao` a reduz por paper ao que o Panorama le.
"""

from __future__ import annotations

import datetime as dt
import json

import pytest

D = dt.date


# ══════════════ pre-agregacao dos votos ══════════════


def test_ganho_e_a_primeira_e_a_ultima_medicao_da_semana():
    import gerar_painel as g

    ms = [
        (D(2026, 9, 1), 3),
        (D(2026, 9, 5), 10),
        (D(2026, 9, 8), 14),
        (D(2026, 9, 10), 40),
    ]
    vg, _ = g.atencao(ms, D(2026, 9, 1), D(2026, 9, 10))
    # 01/09 esta fora da janela de 7 dias que termina em 10/09
    assert vg == ["2026-09-05", 10, "2026-09-10", 40]


@pytest.mark.parametrize(
    "ms",
    [
        [(D(2026, 9, 9), 10)],  # uma medicao so
        [(D(2026, 9, 8), 10), (D(2026, 9, 10), 10)],  # sem crescimento
        [(D(2026, 9, 8), 10), (D(2026, 9, 10), 7)],  # caiu
    ],
)
def test_sem_ganho_nao_inventa_numero(ms):
    import gerar_painel as g

    assert g.atencao(ms, D(2026, 9, 1), D(2026, 9, 10))[0] is None


def test_maturacao_e_plana_e_normalizada_pelo_ultimo_total():
    import gerar_painel as g

    base = D(2026, 8, 1)
    ms = [
        (base, 5),
        (base + dt.timedelta(days=1), 8),
        (base + dt.timedelta(days=20), 10),
        (base + dt.timedelta(days=40), 10),
    ]
    _, vm = g.atencao(ms, base, D(2026, 9, 30))
    # idade 40 passa do horizonte e fica de fora; 100% sai inteiro
    assert vm == [0, 50, 1, 80, 20, 100]


@pytest.mark.parametrize(
    "ms",
    [
        [(D(2026, 8, 3), 5), (D(2026, 8, 30), 10)],  # primeira medicao no dia 2
        [(D(2026, 8, 1), 5), (D(2026, 8, 10), 10)],  # ultima antes do dia 14
        [(D(2026, 8, 1), 0), (D(2026, 8, 30), 0)],  # total final zero
    ],
)
def test_maturacao_so_para_historico_elegivel(ms):
    import gerar_painel as g

    assert g.atencao(ms, D(2026, 8, 1), D(2026, 9, 30))[1] is None


# ══════════════ arquivos gravados ══════════════


def _dados_minimos(monkeypatch, tmp_path):
    import gerar_painel as g

    hoje = dt.date.today()
    (tmp_path / "_manifest.json").write_text(
        json.dumps({"run_id": "r1", "gerado_em": hoje.isoformat() + "T08:00:00"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(g, "DIR_MARTS", tmp_path)
    monkeypatch.setattr(g, "CONFIG", tmp_path / "sem-config.yaml")
    tabelas = {
        "dim_paper": [
            {
                "paper_id": "p1",
                "titulo": "Um </script> no título",
                "data_hf_daily": hoje,
                "upvotes_atual": 3,
                "url_hf": "https://x/p1",
            }
        ],
        "fato_triagem": [
            {
                "paper_id": "p1",
                "veredito": "aprovado",
                "justificativa": "m",
                "natureza": "proposta",
            }
        ],
        "dim_ficha": [{"paper_id": "p1", "achado": "achado longo"}],
        "fato_metrica": [
            {
                "paper_id": "p1",
                "data_snapshot": hoje - dt.timedelta(days=2),
                "upvotes": 1,
            },
            {"paper_id": "p1", "data_snapshot": hoje, "upvotes": 3},
        ],
    }
    monkeypatch.setattr(g, "ler", lambda nome: tabelas.get(nome, []))
    return g


def test_a_pasta_separa_dados_fichas_e_echarts(monkeypatch, tmp_path):
    g = _dados_minimos(monkeypatch, tmp_path)
    arquivos, _ = g.montar(90)
    assert set(arquivos) == {
        "index.html",
        "dados.json",
        "fichas.json",
        "echarts.painel.min.js",
    }
    dados = json.loads(arquivos["dados.json"])
    assert "fichas" not in dados and "serie" not in dados
    assert dados["papers"][0]["vg"][1::2] == [1, 3]
    assert json.loads(arquivos["fichas.json"])[0]["ach"] == "achado longo"
    pagina = arquivos["index.html"]
    # cada irmao com o hash do proprio conteudo no ?v=
    assert f"dados.json?v={g.versao(arquivos['dados.json'])}" in pagina
    assert f"fichas.json?v={g.versao(arquivos['fichas.json'])}" in pagina
    assert (
        f'src="echarts.painel.min.js?v={g.versao(arquivos["echarts.painel.min.js"])}"'
        in pagina
    )
    assert "var DADOS" not in pagina
    # o resumo em texto vai para a meta description, para buscador e previa de link
    assert '<meta name="description" content="1 papers do Hugging Face' in pagina

    total = g.escrever(arquivos, tmp_path / "site")
    assert sorted(p.name for p in (tmp_path / "site").iterdir()) == sorted(arquivos)
    assert total > 0


def test_o_html_unico_embute_tudo_sem_quebrar_a_tag(monkeypatch, tmp_path):
    g = _dados_minimos(monkeypatch, tmp_path)
    arquivos, _ = g.montar(90, embutido=True)
    assert list(arquivos) == ["index.html"]
    pagina = arquivos["index.html"]
    assert (
        "var DADOS=" in pagina
        and "var FICHAS=" in pagina
        and "var PAINEL_ARQUIVOS" not in pagina
    )
    # o titulo com </script> nao pode fechar a tag do JSON
    assert "Um \\u003c/script> no título" in pagina
    assert "Um </script>" not in pagina
    destino = tmp_path / "previa.html"
    g.escrever(arquivos, destino)
    assert destino.read_text(encoding="utf-8") == pagina


def test_escape_de_json_cobre_comentario_seguido_de_script():
    import gerar_painel as g

    texto = g._embutivel(g._json({"t": "<!--<script> e </script>"}))
    assert "<" not in texto
    assert json.loads(texto) == {"t": "<!--<script> e </script>"}


@pytest.mark.parametrize(
    "url,ok",
    [
        ("https://github.com/x/y", True),
        ("http://p.io", True),
        (" HTTPS://a", True),
        ("javascript:alert(1)", False),
        ("data:text/html,x", False),
        ("", False),
        (None, False),
    ],
)
def test_so_http_vira_link(url, ok):
    import gerar_painel as g

    assert g.url_segura(url) is ok
    extra = g.classificacao({}, {"github_repo": url, "project_page": url})
    assert ("gh" in extra) is ok and ("pg" in extra) is ok


def test_escape_de_codigo_nao_estraga_regex_literal():
    import gerar_painel as g

    assert (
        g._embutivel("s.replace(/</g, '&lt;')", codigo=True)
        == "s.replace(/</g, '&lt;')"
    )
    assert g._embutivel("x = '</SCRIPT>'", codigo=True) == "x = '<\\/SCRIPT>'"
