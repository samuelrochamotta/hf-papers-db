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


# A grade facetada minima usada pelos testes de hierarquia: duas areas raiz, a
# primeira com duas sub-areas irmas. As duas irmas existem para o par
# secundario de mesma area; a segunda raiz, para a sub-area de outra area.
GRADE_NOVA = {
    "areas": [
        {
            "rotulo": "Contexto & recuperação",
            "definicao": "o que entra na janela e de onde vem",
            "subareas": [
                {"rotulo": "Memória de longo prazo", "definicao": ""},
                {"rotulo": "RAG & recuperação", "definicao": ""},
            ],
        },
        {
            "rotulo": "Interface & modalidade",
            "definicao": "como humano e sistema trocam sinal",
            "subareas": [{"rotulo": "Fala & áudio", "definicao": ""}],
        },
    ],
    "topicos": [],
    # Tres vertentes porque os testes de ordem e de teto precisam de material:
    # duas para a dominante e a secundaria, a terceira para o teto recusar.
    # Em ordem alfabetica porque `exportar` devolve assim, e o teste de ida e
    # volta compara o dicionario inteiro.
    "vertentes": [
        {"rotulo": "Baratear", "definicao": "reduz custo, latência, memória ou tokens"},
        {"rotulo": "Escalar", "definicao": "faz funcionar maior: horizonte, contexto, número de agentes"},
        {"rotulo": "Medir", "definicao": "cria o instrumento: benchmark, protocolo, métrica, auditoria"},
    ],
}


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
def base_facetada(base):
    """`base` mais a grade facetada, que e a que o Estagio A oferece desde o
    ticket 02. Separada de `base` para que os testes de bootstrap continuem
    afirmando sobre uma grade pequena e legivel."""
    with db.transacao(base):
        taxonomia.carregar(base, GRADE_NOVA)
    return base


@pytest.fixture()
def conn2(tmp_path):
    """Segundo banco, vazio: o destino de `taxonomia carregar`."""
    c = db.conectar(tmp_path / "outro.db")
    yield c
    c.close()


def _pares(conn, paper_id="2608.00000") -> list[tuple]:
    return [
        tuple(r)
        for r in conn.execute(
            "SELECT area, subarea, is_primaria FROM ponte_paper_area "
            "WHERE paper_id = ? ORDER BY is_primaria DESC, subarea",
            (paper_id,),
        )
    ]


def test_par_primario_grava_a_area_e_a_sub_area(base_facetada):
    with db.transacao(base_facetada):
        taxonomia.aplicar_classificacao(
            base_facetada,
            "2608.00000",
            area_primaria="Contexto & recuperação",
            subarea_primaria="Memória de longo prazo",
        )
    assert _pares(base_facetada) == [("Contexto & recuperação", "Memória de longo prazo", 1)]


def test_par_secundario_de_mesma_area_com_sub_area_diferente_e_gravado(base_facetada):
    """User story 33: a chave primaria `(paper_id, area)` proibia este par, e e
    o caso raro do paper que atravessa duas sub-areas irmas."""
    with db.transacao(base_facetada):
        taxonomia.aplicar_classificacao(
            base_facetada,
            "2608.00000",
            area_primaria="Contexto & recuperação",
            subarea_primaria="Memória de longo prazo",
            area_secundaria="Contexto & recuperação",
            subarea_secundaria="RAG & recuperação",
        )
    assert _pares(base_facetada) == [
        ("Contexto & recuperação", "Memória de longo prazo", 1),
        ("Contexto & recuperação", "RAG & recuperação", 0),
    ]


def test_sub_area_de_outra_area_e_ignorada_sem_derrubar_o_paper(base_facetada):
    """O enum e plano - ele nao sabe de quem cada sub-area e filha -, entao o
    parentesco e cobrado aqui. Par invalido nao entra; o veredito fica de pe."""
    with db.transacao(base_facetada):
        taxonomia.aplicar_classificacao(
            base_facetada,
            "2608.00000",
            area_primaria="Contexto & recuperação",
            subarea_primaria="Fala & áudio",            # filha de Interface & modalidade
            area_secundaria="Interface & modalidade",
            subarea_secundaria="Fala & áudio",
        )
    assert _pares(base_facetada) == [("Interface & modalidade", "Fala & áudio", 0)]


def test_aplicar_classificacao_ignora_rotulo_desconhecido(base_facetada):
    """User story 28: rotulo fora do vocabulario nao derruba a classificacao.

    A vertente inventada vem primeiro de proposito: a valida seguinte precisa
    virar a dominante, e nao a secundaria de uma vertente que nao existe."""
    with db.transacao(base_facetada):
        taxonomia.aplicar_classificacao(
            base_facetada,
            "2608.00000",
            area_primaria="Contexto & recuperação",
            subarea_primaria="Memória de longo prazo",
            area_secundaria="Área inventada",
            subarea_secundaria="Sub-área inventada",
            vertentes_paper=["Vertente inventada", "Medir"],
        )
    assert db.contar(base_facetada, "ponte_paper_area") == 1
    assert _vertentes(base_facetada) == [("Medir", 1)]


def _vertentes(conn, paper_id="2608.00000") -> list[tuple]:
    return [
        tuple(r)
        for r in conn.execute(
            "SELECT vertente, ordem FROM ponte_paper_vertente WHERE paper_id = ? "
            "ORDER BY ordem",
            (paper_id,),
        )
    ]


def test_uma_vertente_so_e_gravada_como_dominante(base_facetada):
    """O caminho comum: uma vertente basta, e ela e a de ordem 1."""
    with db.transacao(base_facetada):
        taxonomia.aplicar_classificacao(
            base_facetada,
            "2608.00000",
            area_primaria="Contexto & recuperação",
            subarea_primaria="Memória de longo prazo",
            vertentes_paper=["Baratear"],
        )
    assert _vertentes(base_facetada) == [("Baratear", 1)]


def test_duas_vertentes_saem_ordenadas_com_a_dominante_em_primeiro(base_facetada):
    """User story 10: a primeira da lista e a dominante, e e ela que a consulta
    por ordem 1 devolve quando o ranking precisa de uma resposta so."""
    with db.transacao(base_facetada):
        taxonomia.aplicar_classificacao(
            base_facetada,
            "2608.00000",
            area_primaria="Contexto & recuperação",
            subarea_primaria="Memória de longo prazo",
            vertentes_paper=["Baratear", "Escalar"],
        )
    assert _vertentes(base_facetada) == [("Baratear", 1), ("Escalar", 2)]
    assert taxonomia.vertente_dominante(base_facetada, "2608.00000") == "Baratear"


def test_teto_de_duas_vertentes_e_aplicado_na_persistencia(base_facetada):
    """User story 29: o teto vale mesmo quando o modelo desobedece o schema."""
    with db.transacao(base_facetada):
        taxonomia.aplicar_classificacao(
            base_facetada,
            "2608.00000",
            area_primaria="Contexto & recuperação",
            subarea_primaria="Memória de longo prazo",
            vertentes_paper=["Baratear", "Escalar", "Medir"],
        )
    assert _vertentes(base_facetada) == [("Baratear", 1), ("Escalar", 2)]


def test_reclassificar_troca_as_vertentes_em_vez_de_acumula_las(base_facetada):
    """A ponte e reescrita como a de area: a rodada de ontem nao sobrevive na
    de hoje, senao o paper acumularia vertente e a ordem 1 viraria duas."""
    for lista in (["Baratear", "Escalar"], ["Medir"]):
        with db.transacao(base_facetada):
            taxonomia.aplicar_classificacao(
                base_facetada,
                "2608.00000",
                area_primaria="Contexto & recuperação",
                subarea_primaria="Memória de longo prazo",
                vertentes_paper=lista,
            )
    assert _vertentes(base_facetada) == [("Medir", 1)]


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


def test_promover_false_registra_mas_nao_promove(base):
    """Vocabulario congelado da reclassificacao total: o candidato acumula
    papers, mas nenhum rotulo novo passa a valer no meio da rodada."""
    cfg = CfgTax()
    with db.transacao(base):
        for pid in ("2608.00000", "2608.00001"):
            r = taxonomia.registrar_candidato(
                base, rotulo="Séries temporais", tipo="topico", definicao="d",
                paper_id=pid, cfg=cfg, promover=False,
            )
    assert r.promovido is False
    assert r.papers == ["2608.00000", "2608.00001"]
    assert "Séries temporais" not in taxonomia.topicos(base)
    # o candidato ficou gravado, com os dois papers: a promocao manual e possivel
    assert db.contar(base, "tax_candidato", "rotulo = 'Séries temporais'") == 1


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


# ── promocao manual ─────────────────────────────────────────────────────────


def _candidato(base, rotulo="Séries temporais", papers=("2608.00000",), cfg=None):
    cfg = cfg or CfgTax(min_papers_novo_rotulo=99)   # alto: nao promove sozinho
    with db.transacao(base):
        for pid in papers:
            taxonomia.registrar_candidato(
                base, rotulo=rotulo, tipo="topico",
                definicao="Previsão sobre sequências indexadas no tempo.",
                paper_id=pid, cfg=cfg,
            )


def test_promover_candidato_usa_a_definicao_do_candidato(base):
    _candidato(base)
    r = taxonomia.promover_candidato(base, rotulo="Séries temporais", tipo="topico")

    assert "Séries temporais" in taxonomia.topicos(base)
    assert r["papers"] == 1
    definicoes = {t["rotulo"]: t["definicao"] for t in taxonomia.exportar(base)["topicos"]}
    assert definicoes["Séries temporais"].startswith("Previsão")
    # o candidato fica marcado como promovido, para `listar` nao repetir a oferta
    assert db.contar(base, "tax_candidato", "promovido = 1") == 1


def test_promover_candidato_recusa_rotulo_desconhecido(base):
    with pytest.raises(ValueError, match="candidato"):
        taxonomia.promover_candidato(base, rotulo="Nao existe", tipo="topico")


def test_promover_candidato_recusa_rotulo_que_ja_e_vocabulario(base):
    with pytest.raises(ValueError, match="ja"):
        taxonomia.promover_candidato(base, rotulo="Agentes de codificação", tipo="topico")


def test_promover_candidato_recusa_com_o_teto_batido(base):
    _candidato(base)
    with pytest.raises(ValueError, match="teto"):
        taxonomia.promover_candidato(
            base, rotulo="Séries temporais", tipo="topico", cfg=CfgTax(max_topicos=1)
        )
    assert "Séries temporais" not in taxonomia.topicos(base)


# ── bootstrap do vocabulario (exportar / carregar) ──────────────────────────


def test_exportar_traz_rotulo_e_definicao(base):
    dados = taxonomia.exportar(base)
    # area sem filha viaja com a lista de sub-areas vazia, e nao sem o campo:
    # quem le o arquivo tem um formato so
    assert dados["areas"] == [
        {"rotulo": "Agentes & automação", "definicao": "d", "subareas": []}
    ]
    assert dados["topicos"] == [{"rotulo": "Agentes de codificação", "definicao": "d"}]
    assert dados["vertentes"] == []


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
    assert r == {"areas": 1, "subareas": 0, "topicos": 1, "vertentes": 0, "ja_existiam": 0}
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

    assert r1 == {"areas": 0, "subareas": 0, "topicos": 1, "vertentes": 0, "ja_existiam": 1}
    assert r2 == {"areas": 0, "subareas": 0, "topicos": 0, "vertentes": 0, "ja_existiam": 2}
    assert db.contar(conn2, "dim_area") == 1
    areas = taxonomia.exportar(conn2)["areas"]
    assert areas[0]["definicao"] == "definicao viva"


def _arquivo_versionado() -> dict:
    caminho = Path(__file__).parents[1] / "config" / "taxonomia_inicial.json"
    return json.loads(caminho.read_text(encoding="utf-8"))


def test_arquivo_versionado_povoa_banco_vazio(conn2):
    """`config/taxonomia_inicial.json` e o unico bootstrap do vocabulario: se
    ele deixar de carregar, banco novo nao classifica paper nenhum."""
    dados = _arquivo_versionado()
    with db.transacao(conn2):
        r = taxonomia.carregar(conn2, dados)

    assert r["areas"] == len(dados["areas"]) and r["areas"] > 0
    assert r["topicos"] == len(dados["topicos"]) and r["topicos"] > 0
    assert r["subareas"] == sum(len(a["subareas"]) for a in dados["areas"]) > 0
    assert r["vertentes"] == len(dados["vertentes"]) > 0
    assert taxonomia.exportar(conn2) == dados


def test_carregar_ignora_entrada_sem_rotulo(conn2):
    with db.transacao(conn2):
        r = taxonomia.carregar(conn2, {"areas": [{"rotulo": "", "definicao": "d"}], "topicos": []})
    assert r["areas"] == 0
    assert db.contar(conn2, "dim_area") == 0


# ── grade facetada: area hierarquica e vertente ─────────────────────────────


def test_carregar_aninha_a_subarea_sob_a_area_e_traz_a_vertente(conn2):
    with db.transacao(conn2):
        r = taxonomia.carregar(conn2, GRADE_NOVA)

    assert (r["areas"], r["subareas"], r["vertentes"]) == (2, 3, 3)
    assert dict(conn2.execute("SELECT area, area_pai FROM dim_area")) == {
        "Contexto & recuperação": None,
        "Memória de longo prazo": "Contexto & recuperação",
        "RAG & recuperação": "Contexto & recuperação",
        "Interface & modalidade": None,
        "Fala & áudio": "Interface & modalidade",
    }


def test_carregar_e_exportar_reproduzem_a_grade_hierarquica(conn2):
    """O pai precisa sobreviver ao ciclo: sem isso a grade volta plana."""
    with db.transacao(conn2):
        taxonomia.carregar(conn2, GRADE_NOVA)
    assert taxonomia.exportar(conn2) == GRADE_NOVA


def test_arquivo_versionado_traz_a_grade_facetada():
    """A grade v1 e o dado que este ticket entrega: dez areas com sub-areas
    aninhadas e nove vertentes, cada uma com o complemento que fixa o sentido
    do verbo. Ela convive com a grade antiga ate a contracao (ticket 05)."""
    dados = _arquivo_versionado()
    com_subarea = [a for a in dados["areas"] if a["subareas"]]
    subareas = [s for a in com_subarea for s in a["subareas"]]

    assert len(com_subarea) == 10
    assert all(a["definicao"] for a in com_subarea)
    assert len(subareas) >= 45
    # sub-area sem definicao nao separa a irma: o Estagio A escolheria pelo rotulo
    assert [s["rotulo"] for s in subareas if not s["definicao"]] == []
    assert len(dados["vertentes"]) == 9
    assert all(v["definicao"] for v in dados["vertentes"])


def test_a_hierarquia_carregada_tem_dois_niveis_e_um_pai_por_subarea(conn2):
    with db.transacao(conn2):
        taxonomia.carregar(conn2, _arquivo_versionado())

    raizes = {r["area"] for r in conn2.execute("SELECT area FROM dim_area WHERE area_pai IS NULL")}
    filhas = conn2.execute("SELECT area, area_pai FROM dim_area WHERE area_pai IS NOT NULL").fetchall()

    assert len(filhas) >= 45
    assert all(f["area_pai"] in raizes for f in filhas)   # nenhuma neta: a grade tem dois niveis


def test_rodada_grava_o_par_primario_para_todo_paper_inclusive_os_fora(cfg, conn):
    """O criterio do ticket 02, de ponta a ponta: com as duas grades no banco, a
    rodada grava o par (area > sub-area) da grade facetada em 100% dos papers
    classificados - e o `fora` nao e excecao, porque a faceta nao depende do
    veredito."""
    from conftest import AREA_TESTE, SUBAREA_TESTE, LLMDuble

    from hfpapers.estagios import classificacao

    with db.transacao(conn):
        for i in (1, 2):
            db.upsert_paper(
                conn,
                {"paper_id": f"2608.0000{i}", "titulo": f"P{i}", "primeiro_visto_em": db.agora()},
            )
        taxonomia.carregar(conn, _arquivo_versionado())

    papers = classificacao.selecionar(conn, force=True)
    # `um_a_cada=2` faz o dublê alternar: o primeiro paper sai `fora`, o segundo
    # segue para o Estagio B
    res = classificacao.rodar(
        conn, LLMDuble(conn, cfg, um_a_cada=2), papers, run_id="run-1", cfg=cfg
    )

    assert res.avisos == []
    assert (res.fora, res.estrito) == (1, 1)
    assert [tuple(r) for r in conn.execute(
        "SELECT t.paper_id, t.veredito, p.area, p.subarea, p.is_primaria "
        "FROM fato_triagem t JOIN ponte_paper_area p USING (paper_id) ORDER BY t.paper_id"
    )] == [
        ("2608.00001", "fora", AREA_TESTE, SUBAREA_TESTE, 1),
        ("2608.00002", "estrito", AREA_TESTE, SUBAREA_TESTE, 1),
    ]


def test_rodada_grava_a_vertente_para_todo_paper_inclusive_os_fora(cfg, conn):
    """O criterio do ticket 03, de ponta a ponta: a vertente atravessa o schema
    novo, a validacao e a persistencia ate a ponte, em 100% dos papers
    classificados - e a de ordem 1 e recuperavel como dominante.

    O topico nao acompanha: ele saiu do contrato do Estagio A, e a ponte dele
    fica vazia ate o ticket 05 apagar a tabela."""
    from conftest import VERTENTE_TESTE, LLMDuble

    from hfpapers.estagios import classificacao

    with db.transacao(conn):
        for i in (1, 2):
            db.upsert_paper(
                conn,
                {"paper_id": f"2608.0000{i}", "titulo": f"P{i}", "primeiro_visto_em": db.agora()},
            )
        taxonomia.carregar(conn, _arquivo_versionado())

    papers = classificacao.selecionar(conn, force=True)
    res = classificacao.rodar(
        conn, LLMDuble(conn, cfg, um_a_cada=2), papers, run_id="run-1", cfg=cfg
    )

    assert (res.fora, res.estrito) == (1, 1)
    assert [tuple(r) for r in conn.execute(
        "SELECT t.paper_id, t.veredito, v.vertente, v.ordem "
        "FROM fato_triagem t JOIN ponte_paper_vertente v USING (paper_id) "
        "ORDER BY t.paper_id"
    )] == [
        ("2608.00001", "fora", VERTENTE_TESTE, 1),
        ("2608.00002", "estrito", VERTENTE_TESTE, 1),
    ]
    assert taxonomia.vertente_dominante(conn, "2608.00001") == VERTENTE_TESTE
    assert db.contar(conn, "ponte_paper_topico") == 0


def test_listar_aninha_a_subarea_sob_a_area_e_traz_as_vertentes(base_facetada):
    dados = taxonomia.listar(base_facetada)

    por_rotulo = {a["rotulo"]: a for a in dados["areas"]}
    assert [s["rotulo"] for s in por_rotulo["Contexto & recuperação"]["subareas"]] == [
        "Memória de longo prazo",
        "RAG & recuperação",
    ]
    # a area plana continua na lista, sem filhas - e nenhuma sub-area sobe a raiz
    assert por_rotulo["Agentes & automação"]["subareas"] == []
    assert "Memória de longo prazo" not in por_rotulo
    assert [v["rotulo"] for v in dados["vertentes"]] == ["Baratear", "Escalar", "Medir"]


def test_listar_conta_o_paper_por_vertente_e_separa_a_dominante(base_facetada):
    """A contagem que o ticket 08 le para decidir qual vertente sobrevive. A
    dominante vai a parte porque vertente que so aparece em segundo lugar tem
    massa sem definir paper nenhum."""
    with db.transacao(base_facetada):
        taxonomia.aplicar_classificacao(
            base_facetada,
            "2608.00000",
            area_primaria="Contexto & recuperação",
            subarea_primaria="Memória de longo prazo",
            vertentes_paper=["Baratear", "Escalar"],
        )
        taxonomia.aplicar_classificacao(
            base_facetada,
            "2608.00001",
            area_primaria="Contexto & recuperação",
            subarea_primaria="Memória de longo prazo",
            vertentes_paper=["Baratear"],
        )

    por_rotulo = {v["rotulo"]: v for v in taxonomia.listar(base_facetada)["vertentes"]}
    assert (por_rotulo["Baratear"]["papers"], por_rotulo["Baratear"]["dominantes"]) == (2, 2)
    assert (por_rotulo["Escalar"]["papers"], por_rotulo["Escalar"]["dominantes"]) == (1, 0)
    assert (por_rotulo["Medir"]["papers"], por_rotulo["Medir"]["dominantes"]) == (0, 0)


def test_listar_conta_o_paper_na_area_e_na_subarea(base_facetada):
    """A ponte guarda o rotulo da raiz numa coluna e o da filha noutra: contar
    so `area` deixaria toda sub-area em zero com a grade ja povoada. O paper com
    dois pares na mesma area conta uma vez la, e um em cada sub-area."""
    with db.transacao(base_facetada):
        taxonomia.aplicar_classificacao(
            base_facetada,
            "2608.00000",
            area_primaria="Contexto & recuperação",
            subarea_primaria="Memória de longo prazo",
            area_secundaria="Contexto & recuperação",
            subarea_secundaria="RAG & recuperação",
        )
    por_rotulo = {a["rotulo"]: a for a in taxonomia.listar(base_facetada)["areas"]}
    contexto = por_rotulo["Contexto & recuperação"]

    assert contexto["papers"] == 1
    assert {s["rotulo"]: s["papers"] for s in contexto["subareas"]} == {
        "Memória de longo prazo": 1,
        "RAG & recuperação": 1,
    }
