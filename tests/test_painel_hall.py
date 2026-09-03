"""Regra de ranqueamento da aba historica do painel.

O painel nao e o Power BI e nao tem teste de layout - mas o hall tem uma regra
de verdade (quem entra, em que trimestre, em que ordem) e ela vira registro
publicado todo dia. E o unico pedaco de `scripts/gerar_painel.py` que merece
teste: o resto e extracao de Parquet e concatenacao de string.
"""

from __future__ import annotations

import datetime as dt

import pytest

from gerar_painel import (
    MARCA_BACKFILL,
    TOPO_APROVADOS,
    TOPO_DESCARTADOS,
    montar_hall,
    periodo,
    por_voto,
)

HOJE = dt.date(2026, 12, 1)
CORTE = HOJE - dt.timedelta(days=90)      # 2026-09-02


def paper(pid: str, dia: dt.date, upvotes: int, **extra) -> dict:
    base = {
        "paper_id": pid,
        "titulo": f"Paper {pid}",
        "data_hf_daily": dia,
        "upvotes_atual": upvotes,
        "organizacao": "org",
        "url_hf": f"https://huggingface.co/papers/{pid}",
    }
    base.update(extra)
    return base


def triado(veredito: str, **extra) -> dict:
    base = {"veredito": veredito, "regra_fora": None, "justificativa": "porque sim"}
    base.update(extra)
    return base


def ficha(pid: str) -> dict:
    return {
        "paper_id": pid,
        "achado": "achado",
        "padrao_nome": "Padrao",
        "padrao_mecanismo": "mecanismo",
        "implicacao_pratica": "implicacao",
        "exemplo_concreto": "exemplo",
        "ressalva": "ressalva",
    }


def montar(papers, triagem, fichas=None, ultimo_voto=None, corte=CORTE):
    return montar_hall(
        papers,
        triagem,
        fichas or {},
        {},          # area_primaria
        {},          # topicos_por_paper
        ultimo_voto or {},
        corte=corte,
    )


# ══════════════ periodo ══════════════

@pytest.mark.parametrize(
    "dia, chave, ini, fim",
    [
        (dt.date(2026, 1, 1), "2026-T1", dt.date(2026, 1, 1), dt.date(2026, 3, 31)),
        (dt.date(2026, 3, 31), "2026-T1", dt.date(2026, 1, 1), dt.date(2026, 3, 31)),
        (dt.date(2026, 4, 1), "2026-T2", dt.date(2026, 4, 1), dt.date(2026, 6, 30)),
        (dt.date(2026, 8, 14), "2026-T3", dt.date(2026, 7, 1), dt.date(2026, 9, 30)),
        (dt.date(2026, 12, 31), "2026-T4", dt.date(2026, 10, 1), dt.date(2026, 12, 31)),
    ],
)
def test_periodo_cobre_o_trimestre_civil(dia, chave, ini, fim):
    achou_chave, _rotulo, achou_ini, achou_fim = periodo(dia)
    assert (achou_chave, achou_ini, achou_fim) == (chave, ini, fim)


def test_periodo_rotula_em_portugues():
    assert periodo(dt.date(2026, 8, 14))[1] == "3º trimestre de 2026"


# ══════════════ ordenacao ══════════════

def test_por_voto_ordena_decrescente_e_desempata_por_id():
    # o desempate por id e o que impede o commit diario de painel.html de ganhar
    # diff sem significado quando dois papers empatam em votos
    dia = dt.date(2026, 7, 1)
    ps = [paper("b", dia, 10), paper("c", dia, 50), paper("a", dia, 10)]
    assert [p["paper_id"] for p in por_voto(ps)] == ["c", "a", "b"]


def test_por_voto_trata_upvote_ausente_como_zero():
    dia = dt.date(2026, 7, 1)
    ps = [paper("a", dia, None), paper("b", dia, 1)]
    assert [p["paper_id"] for p in por_voto(ps)] == ["b", "a"]


# ══════════════ recorte ══════════════

def test_so_entra_no_hall_quem_ja_saiu_da_janela():
    dentro = paper("dentro", dt.date(2026, 10, 1), 900)     # depois do corte
    fora = paper("fora", dt.date(2026, 7, 15), 10)
    hall = montar([dentro, fora], {"dentro": triado("estrito"), "fora": triado("estrito")})

    assert len(hall) == 1
    assert [p["id"] for p in hall[0]["ap"]] == ["fora"]


def test_contagem_do_periodo_inclui_quem_ainda_esta_na_janela():
    """`10 de 41 aprovados` tem de falar do trimestre inteiro.

    Se a contagem olhasse so quem ja saiu, ela mentiria durante os ~90 dias em
    que o trimestre esta saindo aos poucos.
    """
    saiu = paper("saiu", dt.date(2026, 7, 15), 10)
    ainda = paper("ainda", dt.date(2026, 9, 20), 10)        # mesmo trimestre, ainda na janela
    descartado = paper("desc", dt.date(2026, 9, 25), 5)
    triagem = {"saiu": triado("estrito"), "ainda": triado("amplo"), "desc": triado("fora")}

    hall = montar([saiu, ainda, descartado], triagem)
    assert (hall[0]["n"], hall[0]["na"], hall[0]["nd"]) == (3, 2, 1)
    assert len(hall[0]["ap"]) == 1        # mas so um saiu da janela


def test_trimestre_em_consolidacao_e_marcado():
    aberto = paper("a", dt.date(2026, 7, 15), 10)           # T3 termina 30/09 > corte 02/09
    fechado = paper("b", dt.date(2026, 5, 15), 10)          # T2 terminou 30/06 < corte
    hall = montar([aberto, fechado], {"a": triado("estrito"), "b": triado("estrito")})

    por_chave = {h["per"]: h for h in hall}
    assert por_chave["2026-T3"]["cons"] == 1
    assert por_chave["2026-T2"]["cons"] == 0


def test_trimestres_saem_do_mais_recente_para_o_mais_antigo():
    ps = [
        paper("t1", dt.date(2026, 2, 1), 1),
        paper("t3", dt.date(2026, 7, 1), 1),
        paper("t2", dt.date(2026, 5, 1), 1),
    ]
    triagem = {p["paper_id"]: triado("estrito") for p in ps}
    assert [h["per"] for h in montar(ps, triagem)] == ["2026-T3", "2026-T2", "2026-T1"]


def test_cada_paper_cai_em_um_unico_periodo():
    """A deduplicacao e estrutural: `data_hf_daily` e imutavel."""
    ps = [paper(f"p{i}", dt.date(2026, 7, 1) + dt.timedelta(days=i), i) for i in range(40)]
    triagem = {p["paper_id"]: triado("estrito") for p in ps}

    vistos = [p["id"] for h in montar(ps, triagem) for p in h["ap"] + h["de"]]
    assert len(vistos) == len(set(vistos))


# ══════════════ as duas listas ══════════════

def test_lista_de_aprovados_e_limitada_e_ordenada_por_voto():
    ps = [paper(f"p{i:02}", dt.date(2026, 7, 1), i) for i in range(30)]
    triagem = {p["paper_id"]: triado("estrito") for p in ps}
    fichas = {p["paper_id"]: ficha(p["paper_id"]) for p in ps}

    ap = montar(ps, triagem, fichas)[0]["ap"]
    assert len(ap) == TOPO_APROVADOS
    assert [p["u"] for p in ap] == list(range(29, 19, -1))


def test_lista_de_descartados_e_limitada_e_separada_dos_aprovados():
    aprovados = [paper(f"a{i:02}", dt.date(2026, 7, 1), 500 + i) for i in range(12)]
    descartados = [paper(f"d{i:02}", dt.date(2026, 7, 1), i) for i in range(15)]
    triagem = {p["paper_id"]: triado("amplo") for p in aprovados}
    triagem.update({p["paper_id"]: triado("fora") for p in descartados})

    h = montar(aprovados + descartados, triagem)[0]
    assert len(h["ap"]) == TOPO_APROVADOS
    assert len(h["de"]) == TOPO_DESCARTADOS
    assert {p["id"] for p in h["ap"]}.isdisjoint({p["id"] for p in h["de"]})
    assert all(p["id"].startswith("a") for p in h["ap"])


def test_aprovado_carrega_a_ficha_inteira():
    p = paper("p1", dt.date(2026, 7, 1), 10)
    entrada = montar([p], {"p1": triado("estrito")}, {"p1": ficha("p1")})[0]["ap"][0]

    assert entrada["f"] == 1
    assert [entrada[k] for k in ("ach", "pn", "pm", "imp", "ex", "res")] == [
        "achado", "Padrao", "mecanismo", "implicacao", "exemplo", "ressalva"
    ]


def test_aprovado_sem_ficha_continua_no_ranking():
    """Tira-lo faria o top-10 mentir sobre quem foi mais votado."""
    p = paper("p1", dt.date(2026, 7, 1), 999)
    entrada = montar([p], {"p1": triado("estrito")}, fichas={})[0]["ap"][0]

    assert entrada["id"] == "p1"
    assert entrada["f"] == 0
    assert entrada["ach"] == ""


def test_descartado_carrega_regra_e_justificativa():
    p = paper("p1", dt.date(2026, 7, 1), 300)
    triagem = {"p1": triado("fora", regra_fora="treino_ou_postreino",
                            justificativa="O payload principal e treino.")}
    entrada = montar([p], triagem)[0]["de"][0]

    assert entrada["rf"] == "treino_ou_postreino"
    assert entrada["j"] == "O payload principal e treino."
    assert entrada["h"] == 0
    # o descartado nao carrega ficha: e o que mantem a lista em ~0,7 KB por entrada
    assert "ach" not in entrada


def test_carimbo_do_backfill_nao_vira_justificativa():
    """`Importado do historico (...)` e marca de procedencia, nao motivo de descarte."""
    p = paper("p1", dt.date(2026, 7, 1), 300)
    triagem = {"p1": triado("fora", justificativa=MARCA_BACKFILL + "estado)")}
    entrada = montar([p], triagem)[0]["de"][0]

    assert entrada["h"] == 1
    assert entrada["j"] == ""


def test_data_da_ultima_medicao_acompanha_o_paper():
    p = paper("p1", dt.date(2026, 7, 1), 300)
    entrada = montar([p], {"p1": triado("estrito")},
                     ultimo_voto={"p1": "2026-09-29"})[0]["ap"][0]
    assert entrada["uq"] == "2026-09-29"


def test_paper_sem_data_hf_daily_e_ignorado():
    sem_data = paper("p1", None, 900)
    com_data = paper("p2", dt.date(2026, 7, 1), 10)
    hall = montar([sem_data, com_data], {"p1": triado("estrito"), "p2": triado("estrito")})

    assert len(hall) == 1
    assert [p["id"] for p in hall[0]["ap"]] == ["p2"]
    assert hall[0]["n"] == 1


def test_sem_paper_fora_da_janela_o_hall_fica_vazio():
    p = paper("p1", dt.date(2026, 11, 1), 900)
    assert montar([p], {"p1": triado("estrito")}) == []


def test_corte_do_hall_segue_a_janela_do_refresh():
    """O hall comeca onde os votos param de se mexer, e nao num numero solto.

    Se alguem mudar `refresh.janela_morna_dias` no config, o hall tem de seguir
    junto - senao ele passa a congelar ranking com voto ainda vivo (ou a esperar
    tempo demais para mostrar um periodo ja fechado).
    """
    import yaml

    from gerar_painel import CONFIG, janela_hall

    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assert janela_hall() == cfg["refresh"]["janela_morna_dias"]
