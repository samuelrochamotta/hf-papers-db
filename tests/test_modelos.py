import datetime as dt

from hfpapers.fontes.modelos import (
    ItemDiario,
    Paper,
    id_base,
    paper_para_dim,
    paper_para_metrica,
)


def test_id_base_remove_sufixo_de_versao():
    assert id_base("2608.03451v2") == "2608.03451"
    assert id_base("2608.03451") == "2608.03451"
    assert id_base("2608.03451v12") == "2608.03451"
    # 'v' no meio nao e sufixo de versao
    assert id_base("2608.0345v1a") == "2608.0345v1a"


def test_paper_normaliza_id_e_datas(daily_bruto):
    cru = dict(daily_bruto[0]["paper"])
    cru["id"] = cru["id"] + "v3"
    p = Paper.model_validate(cru)
    assert "v3" not in p.paper_id
    assert isinstance(p.publishedAt, dt.date)
    assert isinstance(p.submittedOnDailyAt, dt.date)


def test_as_duas_datas_divergem_no_lote_real(daily_bruto):
    itens = [ItemDiario.model_validate(x) for x in daily_bruto]
    divergem = [
        i for i in itens if i.paper.publishedAt != i.paper.submittedOnDailyAt
    ]
    assert len(itens) == 35
    assert len(divergem) == 35   # a divergencia e a regra, nao a excecao


def test_campos_opcionais_ausentes_nao_quebram(daily_bruto):
    itens = [ItemDiario.model_validate(x) for x in daily_bruto]
    sem_repo = [i for i in itens if i.paper.githubRepo is None]
    assert sem_repo, "o lote real tem papers sem repo"
    for i in sem_repo:
        assert i.paper.githubStars is None or i.paper.githubStars == 0
        d = paper_para_dim(i.paper, item=i)
        assert d["github_repo"] is None


def test_paper_sem_campos_obrigatorios_extras():
    p = Paper.model_validate({"id": "2608.00001", "title": "T"})
    assert p.summary is None and p.ai_keywords == [] and p.upvotes is None


def test_dim_deriva_urls_e_flags(daily_bruto):
    item = ItemDiario.model_validate(daily_bruto[0])
    d = paper_para_dim(item.paper, item=item, primeiro_visto_em="2026-08-26T00:00:00")
    pid = item.paper.paper_id
    assert d["url_arxiv"] == f"https://arxiv.org/abs/{pid}"
    assert d["url_hf"] == f"https://huggingface.co/papers/{pid}"
    assert d["qtd_autores"] == len(item.paper.authors)


def test_numcomments_so_existe_no_envelope(daily_bruto):
    item = ItemDiario.model_validate(daily_bruto[0])
    assert item.numComments is not None
    m = paper_para_metrica(
        item.paper, data_snapshot=dt.date(2026, 8, 26), origem="daily",
        comentarios=item.numComments,
    )
    assert m["comentarios"] == item.numComments


def test_endpoint_por_paper_traz_numtotal_e_status(paper_bruto):
    p = Paper.model_validate(paper_bruto)
    assert p.numTotalModels is not None
    assert p.qtd_autores_verificados >= 1
