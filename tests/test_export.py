import datetime as dt
import json

import pyarrow.parquet as pq

from hfpapers import db
from hfpapers.estagios import export

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
    r = export.rodar(conn, cfg, run_id="run-teste")

    esperados = {
        "dim_paper", "fato_metrica", "fato_triagem", "dim_ficha",
        "dim_area", "dim_vertente",
        "ponte_paper_area", "ponte_paper_vertente",
        "dim_natureza",
    }
    assert set(r.arquivos) == esperados
    for nome in esperados:
        assert (cfg.dir_marts / f"{nome}.parquet").exists()

    manifest = json.loads((cfg.dir_marts / "_manifest.json").read_text(encoding="utf-8"))
    assert manifest["run_id"] == "run-teste"
    assert manifest["linhas"]["dim_paper"] == 1
    assert manifest["versao_schema"] == 4
    for morto in export.ARQUIVOS_MORTOS:
        assert morto not in manifest["linhas"]
        assert not (cfg.dir_marts / f"{morto}.parquet").exists()


def test_ponte_paper_area_leva_a_subarea_ao_parquet(conn, cfg):
    """O painel mostra o par area > sub-area, e a sub-area precisa chegar ate o
    Parquet que ele le."""
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
    export.rodar(conn, cfg)

    ponte = pq.read_table(cfg.dir_marts / "ponte_paper_area.parquet").to_pylist()
    assert ponte == [{
        "paper_id": "2608.00001",
        "area": "Contexto & recuperação",
        "subarea": "Memória de longo prazo",
        "is_primaria": True,
    }]


def test_dim_area_leva_o_pai_ao_parquet(conn, cfg):
    """Sem `area_pai` a dimensao chega ao painel como 74 rotulos planos: nao ha
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
    export.rodar(conn, cfg)

    areas = pq.read_table(cfg.dir_marts / "dim_area.parquet").to_pylist()
    assert {a["area"]: a["area_pai"] for a in areas} == {
        "Contexto & recuperação": None,
        "Memória de longo prazo": "Contexto & recuperação",
    }


def test_ponte_paper_vertente_leva_a_ordem_ao_parquet(conn, cfg):
    """Sem a ordem no Parquet o painel nao sabe qual vertente e a dominante,
    que o card exibe primeiro."""
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
    export.rodar(conn, cfg)

    ponte = pq.read_table(cfg.dir_marts / "ponte_paper_vertente.parquet").to_pylist()
    assert sorted(ponte, key=lambda r: r["ordem"]) == [
        {"paper_id": "2608.00001", "vertente": "Baratear", "ordem": 1},
        {"paper_id": "2608.00001", "vertente": "Escalar", "ordem": 2},
    ]


def test_fato_triagem_leva_a_classificacao_e_o_artefato_aberto(conn, cfg):
    """O artefato aberto sai pronto de `vw_artefato` (evidencia + `liberado`),
    para o painel nao reimplementar a regra."""
    _semear(conn)
    export.rodar(conn, cfg)
    linha = pq.read_table(cfg.dir_marts / "fato_triagem.parquet").to_pylist()[0]
    assert (linha["veredito"], linha["natureza"]) == ("aprovado", "proposta")
    assert linha["pratica_contradita"] == "usar a mesma temperatura no rollout e na avaliacao"
    assert linha["artefato_aberto"] is True


def test_o_painel_monta_a_partir_do_export(conn, cfg, monkeypatch):
    """O contrato de ponta a ponta: o painel le o que o export escreve. Os
    testes de `gerar_painel` escrevem os proprios Parquet; este e o unico que
    quebra se o export cortar uma coluna que o painel le com `[]`."""
    import gerar_painel

    _semear(conn)
    export.rodar(conn, cfg, run_id="run-teste")
    monkeypatch.setattr(gerar_painel, "DIR_MARTS", cfg.dir_marts)
    dados, _ = gerar_painel.montar_dados(janela=100_000, dias_hall=100_000)

    [p] = dados["papers"]
    assert (p["id"], p["v"], p["u"], p["oa"]) == ("2608.00001", "aprovado", 55, 1)
    assert p["pc"] == "usar a mesma temperatura no rollout e na avaliacao"
    assert p["gh"] == "https://github.com/x/y"
    assert p["ao"] == 1
    assert p["f"] == 1


def test_tabelas_sem_leitor_ficam_no_banco_mas_nao_no_parquet(conn, cfg):
    """ADRs 005 e 008: so o Parquet sai. Perfis, degraus, calendario, autores,
    keywords e o log de execucao continuam no banco."""
    _semear(conn)
    export.rodar(conn, cfg)
    assert [tuple(r) for r in conn.execute("SELECT paper_id, perfil FROM vw_paper_perfil")] == [
        ("2608.00001", "pesquisa_treino")
    ]
    for nome in export.ARQUIVOS_MORTOS:
        assert not (cfg.dir_marts / f"{nome}.parquet").exists()


def test_parquets_de_tabelas_mortas_sao_apagados(conn, cfg):
    """O export so escreve; sem a limpeza `marts/` continuaria carregando o
    arquivo das tabelas que sairam nos ADRs 004, 005 e 008."""
    cfg.dir_marts.mkdir(parents=True, exist_ok=True)
    mortos = [cfg.dir_marts / f"{n}.parquet" for n in export.ARQUIVOS_MORTOS]
    for m in mortos:
        m.write_bytes(b"velho")
    _semear(conn)
    export.rodar(conn, cfg)
    assert not any(m.exists() for m in mortos)


def test_datas_saem_como_date_nao_string(conn, cfg):
    _semear(conn)
    export.rodar(conn, cfg)
    t = pq.read_table(cfg.dir_marts / "dim_paper.parquet")
    assert str(t.schema.field("data_hf_daily").type) == "date32[day]"
    met = pq.read_table(cfg.dir_marts / "fato_metrica.parquet")
    assert str(met.schema.field("data_snapshot").type) == "date32[day]"


def test_dim_paper_leva_a_ultima_metrica(conn, cfg):
    _semear(conn)
    export.rodar(conn, cfg)
    r = pq.read_table(cfg.dir_marts / "dim_paper.parquet").to_pylist()[0]
    assert r["tem_project_page"] is False
    assert (r["upvotes_atual"], r["comentarios_atual"]) == (55, 4)


def test_export_sobrescreve_sem_duplicar(conn, cfg):
    _semear(conn)
    export.rodar(conn, cfg)
    export.rodar(conn, cfg)
    t = pq.read_table(cfg.dir_marts / "dim_paper.parquet")
    assert t.num_rows == 1
    assert not list(cfg.dir_marts.glob("*.tmp"))


def test_export_com_csv(conn, cfg):
    _semear(conn)
    cfg.export.csv = True
    export.rodar(conn, cfg)
    assert (cfg.dir_marts / "dim_paper.csv").exists()
