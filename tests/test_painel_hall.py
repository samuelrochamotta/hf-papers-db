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
    NAO_CLASSIFICADO,
    PREFIXO_FALLBACK,
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
        {},          # par_primario
        {},          # vertentes_por_paper
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
    hall = montar([dentro, fora], {"dentro": triado("aprovado"), "fora": triado("aprovado")})

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
    triagem = {"saiu": triado("aprovado"), "ainda": triado("aprovado"), "desc": triado("fora")}

    hall = montar([saiu, ainda, descartado], triagem)
    assert (hall[0]["n"], hall[0]["na"], hall[0]["nd"]) == (3, 2, 1)
    assert len(hall[0]["ap"]) == 1        # mas so um saiu da janela


def test_trimestre_em_consolidacao_e_marcado():
    aberto = paper("a", dt.date(2026, 7, 15), 10)           # T3 termina 30/09 > corte 02/09
    fechado = paper("b", dt.date(2026, 5, 15), 10)          # T2 terminou 30/06 < corte
    hall = montar([aberto, fechado], {"a": triado("aprovado"), "b": triado("aprovado")})

    por_chave = {h["per"]: h for h in hall}
    assert por_chave["2026-T3"]["cons"] == 1
    assert por_chave["2026-T2"]["cons"] == 0


def test_trimestres_saem_do_mais_recente_para_o_mais_antigo():
    ps = [
        paper("t1", dt.date(2026, 2, 1), 1),
        paper("t3", dt.date(2026, 7, 1), 1),
        paper("t2", dt.date(2026, 5, 1), 1),
    ]
    triagem = {p["paper_id"]: triado("aprovado") for p in ps}
    assert [h["per"] for h in montar(ps, triagem)] == ["2026-T3", "2026-T2", "2026-T1"]


def test_cada_paper_cai_em_um_unico_periodo():
    """A deduplicacao e estrutural: `data_hf_daily` e imutavel.

    Os papers atravessam DUAS fronteiras de trimestre de proposito, e nenhuma
    lista chega ao teto: um teste que so gerasse um trimestre passaria por
    construcao (`ap` e truncado em dez), sem exercitar nada.
    """
    dias = [
        dt.date(2025, 12, 30), dt.date(2025, 12, 31),      # 2025-T4
        dt.date(2026, 1, 1), dt.date(2026, 3, 31),         # 2026-T1
        dt.date(2026, 4, 1), dt.date(2026, 6, 30),         # 2026-T2
    ]
    ps = [paper(f"p{i}", d, i) for i, d in enumerate(dias)]
    triagem = {p["paper_id"]: triado("aprovado" if i % 2 else "fora")
               for i, p in enumerate(ps)}

    hall = montar(ps, triagem)
    assert [h["per"] for h in hall] == ["2026-T2", "2026-T1", "2025-T4"]
    assert [h["n"] for h in hall] == [2, 2, 2]

    vistos = [e["id"] for h in hall for e in h["ap"] + h["de"]]
    assert sorted(vistos) == [p["paper_id"] for p in ps]     # cada um exatamente uma vez


def test_virada_de_ano_ordena_pelo_calendario_e_nao_pela_string():
    ps = [
        paper("velho", dt.date(2024, 11, 1), 1),
        paper("novo", dt.date(2026, 2, 1), 1),
        paper("meio", dt.date(2025, 11, 1), 1),
    ]
    triagem = {p["paper_id"]: triado("aprovado") for p in ps}
    assert [h["per"] for h in montar(ps, triagem)] == ["2026-T1", "2025-T4", "2024-T4"]


def test_o_corte_e_exclusivo_no_proprio_dia():
    """`d == corte` ainda esta na janela viva; `corte - 1` ja saiu."""
    no_corte = paper("no_corte", CORTE, 10)
    vespera = paper("vespera", CORTE - dt.timedelta(days=1), 10)
    triagem = {"no_corte": triado("aprovado"), "vespera": triado("aprovado")}

    hall = montar([no_corte, vespera], triagem)
    assert [p["id"] for p in hall[0]["ap"]] == ["vespera"]


def test_trimestre_que_termina_no_corte_ainda_consolida():
    """`fim >= corte` e a fronteira: no dia exato o trimestre nao fechou."""
    # CORTE = 2026-09-02, dentro do T3 (que termina em 30/09)
    dentro = montar([paper("a", dt.date(2026, 7, 1), 1)], {"a": triado("aprovado")},
                    corte=dt.date(2026, 9, 30))
    assert dentro[0]["cons"] == 1

    depois = montar([paper("a", dt.date(2026, 7, 1), 1)], {"a": triado("aprovado")},
                    corte=dt.date(2026, 10, 1))
    assert depois[0]["cons"] == 0


# ══════════════ as duas listas ══════════════

def test_lista_de_aprovados_e_limitada_e_ordenada_por_voto():
    ps = [paper(f"p{i:02}", dt.date(2026, 7, 1), i) for i in range(30)]
    triagem = {p["paper_id"]: triado("aprovado", prerequisito="implementar") for p in ps}
    fichas = {p["paper_id"]: ficha(p["paper_id"]) for p in ps}

    ap = montar(ps, triagem, fichas)[0]["ap"]
    assert len(ap) == TOPO_APROVADOS
    assert [p["u"] for p in ap] == list(range(29, 29 - TOPO_APROVADOS, -1))


def test_o_hall_embute_o_topo_de_cada_degrau():
    """O perfil e escolhido no navegador: o Python nao sabe que degraus vao
    ser pedidos, entao embute o topo de CADA um. O degrau menos votado nao pode
    sumir atras do mais votado - senao o perfil Treino/pesquisa abriria vazio."""
    dia = dt.date(2026, 7, 1)
    produto = [paper(f"i{i:02}", dia, 1000 + i) for i in range(20)]
    treino = [paper(f"t{i:02}", dia, i) for i in range(3)]
    triagem = {p["paper_id"]: triado("aprovado", prerequisito="implementar") for p in produto}
    triagem.update({p["paper_id"]: triado("aprovado", prerequisito="treino") for p in treino})

    h = montar(produto + treino, triagem)[0]
    ids = [p["id"] for p in h["ap"]]
    assert sum(1 for i in ids if i.startswith("i")) == TOPO_APROVADOS
    assert sorted(i for i in ids if i.startswith("t")) == ["t00", "t01", "t02"]
    assert h["nad"] == {"implementar": 20, "treino": 3}


def test_lista_de_descartados_e_limitada_e_separada_dos_aprovados():
    aprovados = [paper(f"a{i:02}", dt.date(2026, 7, 1), 500 + i) for i in range(20)]
    descartados = [paper(f"d{i:02}", dt.date(2026, 7, 1), i) for i in range(15)]
    triagem = {p["paper_id"]: triado("aprovado") for p in aprovados}
    triagem.update({p["paper_id"]: triado("fora") for p in descartados})

    h = montar(aprovados + descartados, triagem)[0]
    assert len(h["ap"]) == TOPO_APROVADOS
    assert len(h["de"]) == TOPO_DESCARTADOS
    assert {p["id"] for p in h["ap"]}.isdisjoint({p["id"] for p in h["de"]})
    assert all(p["id"].startswith("a") for p in h["ap"])


def test_aprovado_carrega_a_ficha_inteira():
    p = paper("p1", dt.date(2026, 7, 1), 10)
    entrada = montar([p], {"p1": triado("aprovado")}, {"p1": ficha("p1")})[0]["ap"][0]

    assert entrada["f"] == 1
    assert [entrada[k] for k in ("ach", "pn", "pm", "imp", "ex", "res")] == [
        "achado", "Padrao", "mecanismo", "implicacao", "exemplo", "ressalva"
    ]


def test_aprovado_carrega_justificativa_e_classificacao():
    """`entradas_aprov` traz `j`/`h` (cabecalho da decisao), degrau, natureza,
    os textos e os links - o mesmo contrato da aba viva."""
    p = paper("p1", dt.date(2026, 7, 1), 10, github_repo="https://github.com/x/y")
    triagem = {"p1": triado("aprovado", justificativa="motivo forte", prerequisito="treino",
                            natureza="achado_empirico", pratica_contradita="usar PPO assim",
                            artefato_aberto=True)}
    entrada = montar([p], triagem)[0]["ap"][0]

    assert (entrada["j"], entrada["h"]) == ("motivo forte", 0)
    assert (entrada["pr"], entrada["nt"]) == ("treino", "achado_empirico")
    assert entrada["pc"] == "usar PPO assim"
    assert entrada["ao"] == 1 and entrada["gh"] == "https://github.com/x/y"
    assert "fo" not in entrada and "fr" not in entrada and "cr" not in entrada


def test_aprovado_do_regime_anterior_vira_nao_classificado():
    """Linha migrada de estrito/amplo, sem pre-requisito: nao some e nao ganha
    degrau inventado."""
    p = paper("p1", dt.date(2026, 7, 1), 10)
    entrada = montar([p], {"p1": triado("aprovado")})[0]["ap"][0]
    assert (entrada["pr"], entrada["nt"]) == (NAO_CLASSIFICADO, None)


def test_aprovado_com_justificativa_de_fallback_do_estagio_b_vira_aviso():
    """Linha legada com esse prefixo de fallback continua entrando no ranking dos
    aprovados, com aviso no lugar do texto."""
    p = paper("p1", dt.date(2026, 7, 1), 10)
    triagem = {"p1": triado("aprovado", justificativa=PREFIXO_FALLBACK + " timeout na chamada")}
    entrada = montar([p], triagem)[0]["ap"][0]

    assert entrada["j"] == ""
    assert entrada["h"] == 2


def test_aprovado_sem_justificativa_vira_codigo_tres():
    p = paper("p1", dt.date(2026, 7, 1), 10)
    triagem = {"p1": triado("aprovado", justificativa="")}
    entrada = montar([p], triagem)[0]["ap"][0]

    assert entrada["j"] == ""
    assert entrada["h"] == 3


def test_aprovado_sem_ficha_continua_no_ranking():
    """Tira-lo faria o top-10 mentir sobre quem foi mais votado."""
    p = paper("p1", dt.date(2026, 7, 1), 999)
    entrada = montar([p], {"p1": triado("aprovado")}, fichas={})[0]["ap"][0]

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


def test_descartado_com_justificativa_de_fallback_do_estagio_b_vira_aviso():
    """Uma justificativa que so registra a falha de infra nao pode se passar por raciocinio."""
    p = paper("p1", dt.date(2026, 7, 1), 300)
    triagem = {"p1": triado("fora", justificativa=PREFIXO_FALLBACK + " timeout na chamada")}
    entrada = montar([p], triagem)[0]["de"][0]

    assert entrada["h"] == 2
    assert entrada["j"] == ""


def test_descartado_sem_justificativa_vira_codigo_tres():
    """Linha do pipeline com `justificativa` vazia - o caso que `estagios/classificacao.py`
    produz de verdade quando o Estagio A roda mas nao escreve motivo nenhum."""
    p = paper("p1", dt.date(2026, 7, 1), 300)
    triagem = {"p1": triado("fora", justificativa="")}
    entrada = montar([p], triagem)[0]["de"][0]

    assert entrada["h"] == 3
    assert entrada["j"] == ""


def test_data_da_ultima_medicao_acompanha_o_paper():
    p = paper("p1", dt.date(2026, 7, 1), 300)
    entrada = montar([p], {"p1": triado("aprovado")},
                     ultimo_voto={"p1": "2026-09-29"})[0]["ap"][0]
    assert entrada["uq"] == "2026-09-29"


def test_paper_sem_triagem_nao_vira_descartado():
    """Nunca classificado nao e o mesmo que rejeitado.

    Se `veredito()` tratasse ausencia como `fora`, o paper entraria no podio dos
    descartados com `rf: None` e `justificativa_exibivel` tratando a ausencia de
    texto como codigo 3 - o mesmo aviso generico de "sem motivo registrado" que
    uma linha real de fato_triagem sem justificativa recebe. A secao promete "a
    regra e a justificativa que os tiraram", e um paper nunca julgado nao tem
    nem uma nem outra: ele tem de ficar fora das duas listas, nao entrar com um
    aviso que finge ter sido avaliado. Aconteceria: hoje a base tem papers sem
    linha em fato_triagem (falha do Estagio A).
    """
    orfao = paper("orfao", dt.date(2026, 7, 1), 999)      # o mais votado de longe
    ok = paper("ok", dt.date(2026, 7, 1), 5)
    hall = montar([orfao, ok], {"ok": triado("fora")})     # `orfao` nao esta na triagem

    h = hall[0]
    assert [p["id"] for p in h["de"]] == ["ok"]
    assert h["ap"] == []
    assert (h["n"], h["na"], h["nd"], h["nx"]) == (2, 0, 1, 1)


def test_contagens_do_periodo_sempre_fecham():
    ps = [paper("a", dt.date(2026, 7, 1), 1), paper("b", dt.date(2026, 7, 2), 1),
          paper("c", dt.date(2026, 7, 3), 1), paper("d", dt.date(2026, 7, 4), 1)]
    triagem = {"a": triado("aprovado"), "b": triado("aprovado"), "c": triado("fora")}

    h = montar(ps, triagem)[0]
    assert h["n"] == h["na"] + h["nd"] + h["nx"] == 4


def test_paper_sem_data_hf_daily_e_ignorado():
    sem_data = paper("p1", None, 900)
    com_data = paper("p2", dt.date(2026, 7, 1), 10)
    hall = montar([sem_data, com_data], {"p1": triado("aprovado"), "p2": triado("aprovado")})

    assert len(hall) == 1
    assert [p["id"] for p in hall[0]["ap"]] == ["p2"]
    assert hall[0]["n"] == 1


def test_sem_paper_fora_da_janela_o_hall_fica_vazio():
    p = paper("p1", dt.date(2026, 11, 1), 900)
    assert montar([p], {"p1": triado("aprovado")}) == []


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


@pytest.mark.parametrize(
    "conteudo, esperado",
    [
        ("refresh:\n  janela_morna_dias: 45\n", 45),
        ("refresh:\n  janela_morna_dias: '60'\n", 60),      # string vira int
        ("refresh: {}\n", 90),                              # chave ausente -> padrao
        ("llm: {}\n", 90),                                  # secao ausente -> padrao
        ("refresh:\n  janela_morna_dias: nao-e-numero\n", 90),
        ("refresh:\n  janela_morna_dias: 0\n", 1),          # nunca zero: dividiria a base
        ("refresh:\n  janela_morna_dias: -5\n", 1),
    ],
)
def test_janela_hall_aguenta_config_torto(tmp_path, monkeypatch, conteudo, esperado):
    import gerar_painel

    caminho = tmp_path / "config.yaml"
    caminho.write_text(conteudo, encoding="utf-8")
    monkeypatch.setattr(gerar_painel, "CONFIG", caminho)
    assert gerar_painel.janela_hall() == esperado


def test_janela_hall_sem_arquivo_usa_o_padrao(tmp_path, monkeypatch):
    import gerar_painel

    monkeypatch.setattr(gerar_painel, "CONFIG", tmp_path / "nao-existe.yaml")
    assert gerar_painel.janela_hall() == gerar_painel.JANELA_HALL_PADRAO


def test_corte_negativo_chega_intacto_na_cli():
    """`--dias-hall=-30` e a unica inspecao do estado consolidado, e e fragil.

    Com valor positivo o corte nunca passa de hoje, entao `fim >= corte` mantem
    o trimestre corrente marcado como em consolidacao para sempre - e a aba no
    estado final fica sem nenhuma forma de ser vista antes de ela existir de
    verdade. Um `max(1, ...)` aqui, do tipo que `janela_hall()` faz de proposito
    para o config, apagaria essa inspecao em silencio: o painel continuaria
    gerando, so que sempre no estado errado.
    """
    from gerar_painel import _parser

    assert _parser().parse_args(["--dias-hall=-30"]).dias_hall == -30


def test_corte_adiantado_tira_o_selo_de_consolidacao():
    """O efeito que o corte negativo produz, medido no proprio hall."""
    p = paper("a", dt.date(2026, 7, 15), 10)                 # T3, termina 30/09
    triagem = {"a": triado("aprovado")}

    assert montar([p], triagem, corte=dt.date(2026, 9, 2))[0]["cons"] == 1
    assert montar([p], triagem, corte=dt.date(2026, 10, 1))[0]["cons"] == 0
