import datetime as dt
import json

import pyarrow.parquet as pq

from hfpapers import db
from hfpapers.estagios import export
from hfpapers.estagios.export import faixa_upvotes

HOJE = dt.date(2026, 8, 26)


def _semear(conn):
    with db.transacao(conn):
        db.upsert_paper(
            conn,
            {
                "paper_id": "2608.00001",
                "titulo": "Paper com repo",
                "data_arxiv": dt.date(2026, 8, 24),
                "data_hf_daily": dt.date(2026, 8, 25),
                "github_repo": "https://github.com/x/y",
                "project_page": None,
                "primeiro_visto_em": db.agora(),
            },
        )
        # dia 1: metrica vinda do enriquecimento (tem numTotal*)
        db.upsert_metrica(
            conn,
            {
                "paper_id": "2608.00001",
                "data_snapshot": dt.date(2026, 8, 25),
                "upvotes": 40,
                "comentarios": 2,
                "qtd_modelos": 3,
                "origem": "por_paper",
            },
        )
        # dia 2: refresh por data, sem numTotal*
        db.upsert_metrica(
            conn,
            {
                "paper_id": "2608.00001",
                "data_snapshot": HOJE,
                "upvotes": 55,
                "comentarios": 4,
                "origem": "daily",
            },
        )
        db.upsert_triagem(
            conn,
            {
                "paper_id": "2608.00001",
                "veredito": "aprovado",
                "justificativa": "j",
                "natureza": "proposta",
                "prerequisito": "treino",
                "pratica_contradita": "usar a mesma temperatura no rollout e na avaliacao",
                "artefato_status": "liberado",
                "classificado_em": db.agora(),
                "run_id": "t",
                "revisao": 1,
            },
        )
        db.upsert_ficha(
            conn,
            {
                "paper_id": "2608.00001",
                "achado": "a",
                "padrao_nome": "N",
                "padrao_mecanismo": "m",
                "implicacao_pratica": "i",
                "exemplo_concreto": "e",
                "ressalva": "r",
                "gerada_em": db.agora(),
                "modelo_usado": "modelo/teste-b",
                "run_id": "t",
            },
        )


def test_export_gera_todos_os_arquivos(conn, cfg):
    _semear(conn)
    r = export.rodar(conn, cfg, run_id="run-teste", hoje=HOJE)

    esperados = {
        "dim_paper", "fato_metrica", "fato_triagem", "dim_ficha",
        "dim_area", "dim_vertente",
        "ponte_paper_area", "ponte_paper_vertente",
        "ponte_paper_keyword", "ponte_paper_autor", "dim_calendario", "fato_execucao",
        "dim_natureza", "dim_prerequisito", "dim_perfil", "ponte_perfil_prerequisito",
        "ponte_paper_perfil",
    }
    assert esperados <= set(r.arquivos)
    for nome in esperados:
        assert (cfg.dir_marts / f"{nome}.parquet").exists()

    manifest = json.loads((cfg.dir_marts / "_manifest.json").read_text(encoding="utf-8"))
    assert manifest["run_id"] == "run-teste"
    assert manifest["linhas"]["dim_paper"] == 1
    assert manifest["versao_schema"] == 2
    assert manifest["linhas"]["ponte_paper_perfil"] == 1
    assert "ponte_paper_criterio" not in manifest["linhas"]


def test_ponte_paper_area_leva_a_subarea_ao_parquet(conn, cfg):
    """O analista corta o acervo pelos dois niveis da area, e a coluna precisa
    chegar ate o Power BI - o painel le o mesmo arquivo."""
    _semear(conn)
    with db.transacao(conn):
        db.upsert_area(conn, {"area": "Contexto & recuperação", "definicao": "d"})
        db.upsert_area(
            conn,
            {"area": "Memória de longo prazo", "definicao": "d",
             "area_pai": "Contexto & recuperação"},
        )
        db.inserir_ignorando(
            conn,
            "ponte_paper_area",
            {"paper_id": "2608.00001", "area": "Contexto & recuperação",
             "subarea": "Memória de longo prazo", "is_primaria": 1},
        )
    export.rodar(conn, cfg, hoje=HOJE)

    ponte = pq.read_table(cfg.dir_marts / "ponte_paper_area.parquet").to_pylist()
    assert ponte == [{
        "paper_id": "2608.00001",
        "area": "Contexto & recuperação",
        "subarea": "Memória de longo prazo",
        "is_primaria": True,
    }]


def test_dim_area_leva_o_pai_ao_parquet(conn, cfg):
    """Sem `area_pai` a dimensao chega ao Power BI como 74 rotulos planos: nao ha
    como saber qual e area raiz e qual e sub-area, nem de quem cada sub-area e
    filha. A hierarquia por auto-referencia so existe se a coluna atravessar."""
    _semear(conn)
    with db.transacao(conn):
        db.upsert_area(conn, {"area": "Contexto & recuperação", "definicao": "d"})
        db.upsert_area(
            conn,
            {"area": "Memória de longo prazo", "definicao": "d",
             "area_pai": "Contexto & recuperação"},
        )
    export.rodar(conn, cfg, hoje=HOJE)

    areas = pq.read_table(cfg.dir_marts / "dim_area.parquet").to_pylist()
    assert {a["area"]: a["area_pai"] for a in areas} == {
        "Contexto & recuperação": None,
        "Memória de longo prazo": "Contexto & recuperação",
    }


def test_ponte_paper_vertente_leva_a_ordem_ao_parquet(conn, cfg):
    """User story 27: sem a ordem no Parquet o analista nao separa a dominante
    da secundaria, e as duas viram a mesma medida."""
    _semear(conn)
    with db.transacao(conn):
        for v in ("Baratear", "Escalar"):
            db.upsert_vertente(conn, {"vertente": v, "definicao": "d"})
        for v, ordem in (("Baratear", 1), ("Escalar", 2)):
            db.inserir_ignorando(
                conn,
                "ponte_paper_vertente",
                {"paper_id": "2608.00001", "vertente": v, "ordem": ordem},
            )
    export.rodar(conn, cfg, hoje=HOJE)

    ponte = pq.read_table(cfg.dir_marts / "ponte_paper_vertente.parquet").to_pylist()
    assert sorted(ponte, key=lambda r: r["ordem"]) == [
        {"paper_id": "2608.00001", "vertente": "Baratear", "ordem": 1},
        {"paper_id": "2608.00001", "vertente": "Escalar", "ordem": 2},
    ]


def test_fato_triagem_leva_a_classificacao_e_os_booleanos_derivados(conn, cfg):
    """Os booleanos saem prontos para o Power BI nao reimplementar as regras:
    `contradiz_pratica` e `como_incompleto` derivam dos textos, e o artefato
    aberto vem de `vw_artefato` (evidencia + `liberado`)."""
    _semear(conn)
    export.rodar(conn, cfg, hoje=HOJE)
    linha = pq.read_table(cfg.dir_marts / "fato_triagem.parquet").to_pylist()[0]
    assert (linha["veredito"], linha["aprovado"]) == ("aprovado", True)
    assert (linha["natureza"], linha["prerequisito"]) == ("proposta", "treino")
    assert linha["contradiz_pratica"] is True
    assert linha["como_incompleto"] is False
    assert linha["evidencia_artefato"] is True
    assert linha["artefato_aberto"] is True


def test_perfis_e_vocabulario_saem_no_parquet(conn, cfg):
    _semear(conn)
    export.rodar(conn, cfg, hoje=HOJE)
    ponte = pq.read_table(cfg.dir_marts / "ponte_paper_perfil.parquet").to_pylist()
    assert ponte == [{"paper_id": "2608.00001", "perfil": "pesquisa_treino"}]
    degraus = pq.read_table(cfg.dir_marts / "dim_prerequisito.parquet").to_pylist()
    assert [d["prerequisito"] for d in sorted(degraus, key=lambda d: d["ordem"])] == [
        "nenhum", "implementar", "acesso_interno", "treino", "sem_acao",
    ]


def test_parquet_da_ponte_de_criterios_e_apagado(conn, cfg):
    """O export so escreve; sem a limpeza o Power BI continuaria lendo o
    arquivo da tabela que saiu no ADR 004."""
    cfg.dir_marts.mkdir(parents=True, exist_ok=True)
    morto = cfg.dir_marts / "ponte_paper_criterio.parquet"
    morto.write_bytes(b"velho")
    _semear(conn)
    export.rodar(conn, cfg, hoje=HOJE)
    assert not morto.exists()


def test_datas_saem_como_date_nao_string(conn, cfg):
    _semear(conn)
    export.rodar(conn, cfg, hoje=HOJE)
    t = pq.read_table(cfg.dir_marts / "dim_paper.parquet")
    assert str(t.schema.field("data_hf_daily").type) == "date32[day]"
    cal = pq.read_table(cfg.dir_marts / "dim_calendario.parquet")
    assert str(cal.schema.field("data").type) == "date32[day]"
    met = pq.read_table(cfg.dir_marts / "fato_metrica.parquet")
    assert str(met.schema.field("data_snapshot").type) == "date32[day]"


def test_numtotal_propaga_para_frente_e_delta_e_calculado(conn, cfg):
    _semear(conn)
    export.rodar(conn, cfg, hoje=HOJE)
    t = pq.read_table(cfg.dir_marts / "fato_metrica.parquet").to_pylist()
    t.sort(key=lambda r: r["data_snapshot"])
    assert t[0]["qtd_modelos"] == 3
    assert t[1]["qtd_modelos"] == 3          # snapshot 'daily' herda o ultimo nao nulo
    assert t[0]["upvotes_delta_dia"] is None
    assert t[1]["upvotes_delta_dia"] == 15


def test_colunas_derivadas_de_slicer(conn, cfg):
    _semear(conn)
    export.rodar(conn, cfg, hoje=HOJE)
    r = pq.read_table(cfg.dir_marts / "dim_paper.parquet").to_pylist()[0]
    assert r["tem_project_page"] is False
    assert r["dias_desde_publicacao"] == 1
    assert r["upvotes_atual"] == 55
    assert r["faixa_upvotes_atual"] == "50-99"


def test_faixa_upvotes():
    bordas = [1, 10, 50, 100]
    assert faixa_upvotes(0, bordas) == "0"
    assert faixa_upvotes(5, bordas) == "1-9"
    assert faixa_upvotes(10, bordas) == "10-49"
    assert faixa_upvotes(99, bordas) == "50-99"
    assert faixa_upvotes(1000, bordas) == "100+"
    assert faixa_upvotes(None, bordas) == "sem dado"


def test_export_sobrescreve_sem_duplicar(conn, cfg):
    _semear(conn)
    export.rodar(conn, cfg, hoje=HOJE)
    export.rodar(conn, cfg, hoje=HOJE)
    t = pq.read_table(cfg.dir_marts / "dim_paper.parquet")
    assert t.num_rows == 1
    assert not list(cfg.dir_marts.glob("*.tmp"))


def test_export_com_csv(conn, cfg):
    _semear(conn)
    cfg.export.csv = True
    export.rodar(conn, cfg, hoje=HOJE)
    assert (cfg.dir_marts / "dim_paper.csv").exists()
