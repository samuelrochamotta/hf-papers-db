import json
from pathlib import Path

import pytest

from hfpapers import db, taxonomia
from hfpapers.config import Guardrails as CfgGuard
from hfpapers.config import Taxonomia as CfgTax
from hfpapers.guardrails import Contagens, avaliar


# ── guardrails (secao 6.5) ──────────────────────────────────────────────────


def test_faixa_normal_nao_gera_aviso():
    c = Contagens(coletados=30, fora=21, amplo=3, estrito=5)
    assert avaliar(c) == []


def test_criterio_frouxo():
    c = Contagens(coletados=30, fora=10, amplo=10, estrito=10)
    avisos = avaliar(c)
    assert any(a.startswith("criterio_frouxo") for a in avisos)


def test_volume_alto_e_atipico():
    c = Contagens(coletados=40, fora=25, amplo=7, estrito=8)
    avisos = avaliar(c)
    assert any(a.startswith("volume_atipico") for a in avisos)
    assert any(a.startswith("volume_alto") for a in avisos)


def test_dia_sem_aprovados_e_valido():
    avisos = avaliar(Contagens(coletados=25, fora=25))
    assert "dia_sem_aprovados" in avisos
    assert not any(a.startswith("criterio_frouxo") for a in avisos)


def test_coleta_suspeita_so_em_dia_util():
    assert any(a.startswith("coleta_suspeita") for a in avaliar(Contagens(coletados=9)))
    assert avaliar(Contagens(coletados=9, dia_util=False)) == []


def test_guardrail_nao_altera_veredito():
    """Contrato da secao 6.5: a funcao devolve strings, nunca vereditos."""
    avisos = avaliar(Contagens(coletados=30, fora=5, amplo=15, estrito=10))
    assert all(isinstance(a, str) for a in avisos)


# ── taxonomia ───────────────────────────────────────────────────────────────


@pytest.fixture()
def base(conn):
    with db.transacao(conn):
        for i in range(3):
            db.upsert_paper(
                conn,
                {"paper_id": f"2608.0000{i}", "titulo": f"P{i}", "primeiro_visto_em": db.agora()},
            )
        db.upsert_area(conn, {"area": "Agentes & automação", "definicao": "d"})
        db.upsert_topico(conn, {"topico": "Agentes de codificação", "definicao": "d"})
    return conn


@pytest.fixture()
def conn2(tmp_path):
    """Segundo banco, vazio: o destino de `taxonomia carregar`."""
    c = db.conectar(tmp_path / "outro.db")
    yield c
    c.close()


def test_aplicar_classificacao_ignora_rotulo_desconhecido(base):
    with db.transacao(base):
        taxonomia.aplicar_classificacao(
            base,
            "2608.00000",
            area_primaria="Agentes & automação",
            areas_secundarias=["Área inventada"],
            topicos_paper=["Agentes de codificação", "Tópico inventado"],
        )
    assert db.contar(base, "ponte_paper_area") == 1
    assert db.contar(base, "ponte_paper_topico") == 1


def test_teto_de_topicos_por_paper(base):
    with db.transacao(base):
        for i in range(8):
            db.upsert_topico(base, {"topico": f"T{i}", "definicao": "d"})
        taxonomia.aplicar_classificacao(
            base,
            "2608.00000",
            area_primaria="Agentes & automação",
            topicos_paper=[f"T{i}" for i in range(8)],
            cfg=CfgTax(),
        )
    assert db.contar(base, "ponte_paper_topico") == 5


def test_candidato_promove_com_dois_papers(base):
    cfg = CfgTax()
    with db.transacao(base):
        r1 = taxonomia.registrar_candidato(
            base, rotulo="Séries temporais", tipo="topico", definicao="d",
            paper_id="2608.00000", cfg=cfg,
        )
        r2 = taxonomia.registrar_candidato(
            base, rotulo="Séries temporais", tipo="topico", definicao="d",
            paper_id="2608.00001", cfg=cfg,
        )
    assert r1.promovido is False and r2.promovido is True
    assert "Séries temporais" in taxonomia.topicos(base)


def test_teto_de_vocabulario_bloqueia_promocao(base):
    cfg = CfgTax(max_topicos=1)
    with db.transacao(base):
        for pid in ("2608.00000", "2608.00001"):
            r = taxonomia.registrar_candidato(
                base, rotulo="Novo", tipo="topico", definicao="d", paper_id=pid, cfg=cfg
            )
    assert r.promovido is False
    assert r.aviso.startswith("teto_vocabulario")
    assert "Novo" not in taxonomia.topicos(base)


def test_candidato_repetido_nao_duplica_paper(base):
    cfg = CfgTax(min_papers_novo_rotulo=5)
    with db.transacao(base):
        for _ in range(3):
            r = taxonomia.registrar_candidato(
                base, rotulo="Novo", tipo="topico", definicao="d",
                paper_id="2608.00000", cfg=cfg,
            )
    assert r.papers == ["2608.00000"]


def test_fusao_reescreve_pontes(base):
    with db.transacao(base):
        db.upsert_topico(base, {"topico": "Antigo", "definicao": "d"})
        db.inserir_ignorando(base, "ponte_paper_topico", {"paper_id": "2608.00000", "topico": "Antigo"})
        db.inserir_ignorando(
            base, "ponte_paper_topico", {"paper_id": "2608.00001", "topico": "Agentes de codificação"}
        )
    taxonomia.fundir(base, de="Antigo", para="Agentes de codificação", tipo="topico")
    assert "Antigo" not in taxonomia.topicos(base)
    assert db.contar(base, "ponte_paper_topico", "topico = 'Agentes de codificação'") == 2


def test_fusao_recusa_rotulo_inexistente(base):
    with pytest.raises(ValueError):
        taxonomia.fundir(base, de="Nao existe", para="Agentes de codificação", tipo="topico")


# ── bootstrap do vocabulario (exportar / carregar) ──────────────────────────


def test_exportar_traz_rotulo_e_definicao(base):
    dados = taxonomia.exportar(base)
    assert dados["areas"] == [{"rotulo": "Agentes & automação", "definicao": "d"}]
    assert dados["topicos"] == [{"rotulo": "Agentes de codificação", "definicao": "d"}]


def test_exportar_nao_leva_candidatos(base):
    """O arquivo versionado e vocabulario vigente, nao fila de promocao."""
    with db.transacao(base):
        taxonomia.registrar_candidato(
            base, rotulo="Novo tópico", tipo="topico", definicao="d",
            paper_id="2608.00000", cfg=CfgTax(),
        )
    dados = taxonomia.exportar(base)
    assert "candidatos" not in dados
    assert [t["rotulo"] for t in dados["topicos"]] == ["Agentes de codificação"]


def test_carregar_e_o_inverso_de_exportar(base, conn2):
    dados = taxonomia.exportar(base)
    with db.transacao(conn2):
        r = taxonomia.carregar(conn2, dados)
    assert r == {"areas": 1, "topicos": 1, "ja_existiam": 0}
    assert taxonomia.exportar(conn2) == dados


def test_carregar_e_idempotente_e_nao_toca_rotulo_existente(base, conn2):
    """Segunda carga nao pode sobrescrever a definicao que o banco ja tem."""
    with db.transacao(conn2):
        db.upsert_area(conn2, {"area": "Agentes & automação", "definicao": "definicao viva"})
    dados = taxonomia.exportar(base)

    with db.transacao(conn2):
        r1 = taxonomia.carregar(conn2, dados)
    with db.transacao(conn2):
        r2 = taxonomia.carregar(conn2, dados)

    assert r1 == {"areas": 0, "topicos": 1, "ja_existiam": 1}
    assert r2 == {"areas": 0, "topicos": 0, "ja_existiam": 2}
    assert db.contar(conn2, "dim_area") == 1
    areas = taxonomia.exportar(conn2)["areas"]
    assert areas[0]["definicao"] == "definicao viva"


def test_arquivo_versionado_povoa_banco_vazio(conn2):
    """`config/taxonomia_inicial.json` e o unico bootstrap do vocabulario: se
    ele deixar de carregar, banco novo nao classifica paper nenhum."""
    caminho = Path(__file__).parents[1] / "config" / "taxonomia_inicial.json"
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    with db.transacao(conn2):
        r = taxonomia.carregar(conn2, dados)

    assert r["areas"] == len(dados["areas"]) and r["areas"] > 0
    assert r["topicos"] == len(dados["topicos"]) and r["topicos"] > 0
    assert taxonomia.exportar(conn2) == dados


def test_carregar_ignora_entrada_sem_rotulo(conn2):
    with db.transacao(conn2):
        r = taxonomia.carregar(conn2, {"areas": [{"rotulo": "", "definicao": "d"}], "topicos": []})
    assert r["areas"] == 0
    assert db.contar(conn2, "dim_area") == 0
