"""Backfill: a uniao das tres fontes, as contagens e a idempotencia.

Sem rede: o cliente do HF e substituido por um dublê que devolve um paper
minimo para qualquer id.
"""

import datetime as dt

from hfpapers import backfill, db
from hfpapers.fontes.modelos import Paper

HOJE = dt.date(2026, 8, 26)


class HFDuble:
    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def paper(self, pid: str) -> Paper:
        self.chamadas.append(pid)
        return Paper.model_validate(
            {
                "id": pid,
                "title": f"Titulo de {pid}",
                "summary": "abstract",
                "authors": [{"name": "Autor", "status": "claimed_verified"}],
                "publishedAt": "2026-08-24T00:00:00.000Z",
                "submittedOnDailyAt": "2026-08-25T00:00:00.000Z",
                "upvotes": 7,
                "ai_keywords": ["kw"],
            }
        )

    def fechar(self) -> None:
        pass


def _rodar(cfg, seed_dir, hf=None):
    conn = db.abrir(cfg)
    try:
        return (
            backfill.rodar(
                seed_dir, cfg=cfg, conn=conn, cliente_hf=hf or HFDuble(),
                pular_llm=True, hoje=HOJE,
            ),
            conn,
        )
    finally:
        conn.close()


def test_lista_de_trabalho_e_a_uniao_das_tres_fontes(seed_dir):
    itens = backfill.montar_lista(seed_dir)
    assert len(itens) == 242                          # 241 do estado + o furo conhecido
    do_estado = [i for i in itens.values() if "estado" in i.fontes]
    assert len(do_estado) == 241
    so_no_digest = [i for i in itens.values() if "estado" not in i.fontes]
    assert [i.paper_id for i in so_no_digest] == ["2608.14577"]


def test_2608_14577_e_recuperado_pela_uniao(seed_dir):
    """O id que so existe fora do estado.json - o primeiro a sumir se a uniao falhar."""
    itens = backfill.montar_lista(seed_dir)
    assert "2608.14577" in itens
    it = itens["2608.14577"]
    assert "estado" not in it.fontes
    assert {"digest", "taxonomia"} <= it.fontes
    assert it.veredito == "amplo"        # secao `## 4.` do digest de 18/08
    assert it.upvotes_dia1 == 19


def test_backfill_popula_242_papers_e_83_aprovados(cfg, seed_dir):
    res, _ = _rodar(cfg, seed_dir)
    conn = db.abrir(cfg)
    try:
        assert db.contar(conn, "dim_paper") == 242
        assert db.contar(conn, "fato_triagem") == 242
        vereditos = {
            r["veredito"]: r["n"]
            for r in conn.execute(
                "SELECT veredito, COUNT(*) AS n FROM fato_triagem GROUP BY veredito"
            )
        }
        assert vereditos["fora"] == 159
        assert vereditos["estrito"] + vereditos["amplo"] == 83
        assert db.contar(conn, "dim_paper", "paper_id = '2608.14577'") == 1
        # taxa de FORA historica
        assert round(159 / 242, 2) == 0.66
    finally:
        conn.close()
    assert res.papers == 242


def test_classificacoes_curadas_sao_importadas(cfg, seed_dir):
    _rodar(cfg, seed_dir)
    conn = db.abrir(cfg)
    try:
        assert db.contar(conn, "dim_area") == 8
        assert db.contar(conn, "dim_topico") == 23
        # 83 papers classificados a mao, cada um com uma area primaria
        assert db.contar(conn, "ponte_paper_area", "is_primaria = 1") == 83
        assert db.contar(conn, "ponte_paper_topico") > 200
    finally:
        conn.close()


def test_dois_snapshots_por_paper_hidratado(cfg, seed_dir):
    _rodar(cfg, seed_dir)
    conn = db.abrir(cfg)
    try:
        r = conn.execute(
            "SELECT COUNT(*) AS n FROM fato_metrica WHERE paper_id = '2608.06867'"
        ).fetchone()
        assert r["n"] == 2      # hoje (metricas atuais) + dia 1 (upvotes historicos)
        dia1 = conn.execute(
            "SELECT upvotes FROM fato_metrica "
            "WHERE paper_id = '2608.06867' AND data_snapshot = '2026-08-25'"
        ).fetchone()
        assert dia1["upvotes"] == 103   # do estado.json
    finally:
        conn.close()


def test_segunda_execucao_nao_altera_contagem_nem_chama_hf(cfg, seed_dir):
    hf1 = HFDuble()
    _rodar(cfg, seed_dir, hf1)
    conn = db.abrir(cfg)
    antes = {
        t: db.contar(conn, t)
        for t in ("dim_paper", "fato_triagem", "fato_metrica", "ponte_paper_area")
    }
    conn.close()

    hf2 = HFDuble()
    _rodar(cfg, seed_dir, hf2)
    conn = db.abrir(cfg)
    depois = {t: db.contar(conn, t) for t in antes}
    conn.close()

    assert antes == depois
    assert len(hf1.chamadas) == 242
    assert hf2.chamadas == []          # nada a re-hidratar


def test_relatorio_de_validacao_e_escrito(cfg, seed_dir):
    res, _ = _rodar(cfg, seed_dir)
    assert res.relatorio and res.relatorio.exists()
    texto = res.relatorio.read_text(encoding="utf-8")
    assert "Fichas históricas | 83" in texto
    assert "não corrige nada" in texto


def test_falha_de_hidratacao_ainda_cria_a_linha(cfg, seed_dir):
    from hfpapers.fontes.hf_client import ErroHF

    class HFQuebrado(HFDuble):
        def paper(self, pid):
            if pid == "2608.06867":
                raise ErroHF("404")
            return super().paper(pid)

    res, _ = _rodar(cfg, seed_dir, HFQuebrado())
    conn = db.abrir(cfg)
    try:
        assert db.contar(conn, "dim_paper") == 242
        assert db.contar(conn, "dim_paper", "paper_id = '2608.06867'") == 1
    finally:
        conn.close()
    assert res.falhas_hidratacao == ["2608.06867"]
    assert any(a.startswith("hidratacao_falhou") for a in res.avisos)


def test_relatorio_compara_veredito_regenerado_de_verdade(cfg, seed_dir):
    """O veredito histórico não é reaberto pelo backfill; sem registrar o que o
    Estágio B devolveu, o relatório compararia o histórico contra ele mesmo."""
    _rodar(cfg, seed_dir)
    backfill.registrar_veredito_regenerado(cfg, "2608.06867", "fora")
    backfill.registrar_veredito_regenerado(cfg, "2608.07545", "aprovado")

    conn = db.abrir(cfg)
    try:
        caminho = backfill.relatorio_validacao(
            conn, seed_dir, cfg, backfill.ResultadoBackfill()
        )
    finally:
        conn.close()

    texto = caminho.read_text(encoding="utf-8")
    assert "| Regeneradas | 2 |" in texto
    assert "| Aprovado antes, FORA agora | 1 |" in texto
    # 'aprovado' conta como concordância com estrito/amplo, não como divergência
    assert "| Mesmo veredito | 1 |" in texto
    assert "2608.06867 | estrito | fora" in texto


def test_vereditos_regenerados_persistem_entre_execucoes(cfg):
    assert backfill.vereditos_regenerados(cfg) == {}
    backfill.registrar_veredito_regenerado(cfg, "2608.00001", "amplo")
    backfill.registrar_veredito_regenerado(cfg, "2608.00002", "fora")
    backfill.registrar_veredito_regenerado(cfg, "2608.00001", "estrito")
    assert backfill.vereditos_regenerados(cfg) == {
        "2608.00001": "estrito",
        "2608.00002": "fora",
    }


def test_backfill_nao_classifica_papers_de_fora_da_lista(cfg, seed_dir):
    """Paper do dia corrente é trabalho do `run`; o backfill não pode pegá-lo
    de carona só porque ainda não tem área."""
    from hfpapers.llm.cliente import ClienteLLM, Preco, Resposta, Uso

    class LLMDuble(ClienteLLM):
        def __init__(self):
            self.cfg, self.conn, self.run_id = cfg, None, "t"
            self.uso, self._precos, self._parametros = Uso(), {}, {}
            self.openai = None
            self.vistos = []

        def chamar(self, *, etapa, modelo, prompt, paper_id=None, validar=None, **kw):
            self.vistos.append(paper_id)
            dados = {
                "veredito_preliminar": "fora",
                "regra_fora": "treino_ou_postreino",
                "justificativa": "j",
                "area_primaria": "Agentes & automação",
                "areas_secundarias": [],
                "topicos": ["Agentes de codificação"],
                "candidato_novo_rotulo": None,
            }
            return Resposta(dados, Uso(), modelo, 1, 1)

    conn = db.abrir(cfg)
    try:
        backfill.rodar(seed_dir, cfg=cfg, conn=conn, cliente_hf=HFDuble(),
                       pular_llm=True, hoje=HOJE)
        # um paper que nao esta no seed, sem classificacao
        with db.transacao(conn):
            db.upsert_paper(conn, {"paper_id": "2699.99999", "titulo": "De hoje",
                                   "primeiro_visto_em": db.agora()})
        llm = LLMDuble()
        res = backfill.ResultadoBackfill()
        backfill.classificar_sem_taxonomia(
            conn, llm, res, cfg, list(backfill.montar_lista(seed_dir))
        )
        assert "2699.99999" not in llm.vistos
        assert db.contar(conn, "ponte_paper_area", "paper_id = '2699.99999'") == 0
    finally:
        conn.close()
