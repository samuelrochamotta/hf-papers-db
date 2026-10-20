"""Checagem de pendencias de triagem no `hfpapers doutor`.

O caso que motivou a checagem: em 2026-09-03 nove papers estavam sem veredito
porque o refresh (estagio 4) os descobriu depois da classificacao (estagio 3)
da mesma rodada. Isso e latencia normal e nao pode virar aviso; o que precisa
virar aviso e o pendente que ja atravessou uma rodada de classificacao.
"""

from __future__ import annotations

import sqlite3

import pytest

from hfpapers import db
from hfpapers.doutor import (
    AVISO,
    OK,
    checar_pendencias,
    checar_regime,
    checar_vocabulario,
    rodar,
)


def _paper(conn, paper_id: str, visto: str) -> None:
    db.upsert_paper(
        conn,
        {
            "paper_id": paper_id,
            "titulo": f"Paper {paper_id}",
            "data_hf_daily": "2026-09-02",
            "primeiro_visto_em": visto,
        },
    )


def _triagem(
    conn,
    paper_id: str,
    veredito: str = "fora",
    *,
    run_id: str = "run-teste",
    quando: str = "2026-09-03T07:00:00",
    regra_fora: str | None = "geracao_de_midia",
) -> None:
    db.upsert_triagem(
        conn,
        {
            "paper_id": paper_id,
            "veredito": veredito,
            "regra_fora": regra_fora if veredito == "fora" else None,
            "justificativa": "teste",
            "classificado_em": quando,
            "run_id": run_id,
        },
    )


def _execucao(conn, run_id: str, *, fim: str | None, classificou: int) -> None:
    db.upsert_execucao(
        conn,
        {
            "run_id": run_id,
            "iniciado_em": "2026-09-03T07:30:00",
            "finalizado_em": fim,
            "status": "ok" if fim else "parcial",
            "qtd_fora": classificou,
            "qtd_aprovados": 0,
        },
    )


@pytest.fixture()
def base(cfg):
    """Banco vazio da fixture `cfg`, ja migrado, aberto para escrita."""
    conn = db.abrir(cfg)
    yield conn
    conn.close()


# ── base sem pendencia ──────────────────────────────────────────────────────


def test_banco_vazio_nao_acusa_pendencia(cfg, base):
    item = checar_pendencias(cfg)
    assert item.estado == OK
    assert item.dados["pendentes"] == 0


def test_todos_com_veredito(cfg, base):
    for pid in ("2609.00001", "2609.00002"):
        _paper(base, pid, "2026-09-03T07:30:00")
        _triagem(base, pid)
    base.commit()

    item = checar_pendencias(cfg)
    assert item.estado == OK
    assert "2 papers, todos com veredito" in item.detalhe
    assert item.dados["pendentes"] == 0


# ── latencia normal do refresh: nao e aviso ─────────────────────────────────


def test_pendente_visto_depois_da_classificacao_fica_na_fila(cfg, base):
    _paper(base, "2609.00001", "2026-09-03T07:31:00")
    _triagem(base, "2609.00001")
    _execucao(base, "run-a", fim="2026-09-03T09:00:00", classificou=1)
    # descoberto pelo refresh, depois de a classificacao ja ter passado
    _paper(base, "2609.00002", "2026-09-03T09:23:23")
    base.commit()

    item = checar_pendencias(cfg)
    assert item.estado == OK
    assert item.dados == {"pendentes": 1, "atrasados": 0, "na_fila": 1}
    assert "proxima rodada" in item.detalhe


def test_nascido_no_instante_exato_do_fim_da_rodada_conta_como_fila(cfg, base):
    """A fronteira e o caso real: o refresh grava e a rodada fecha no mesmo
    timestamp, entao `primeiro_visto_em == finalizado_em`. Esse paper nasceu
    DEPOIS do estagio 3 e nao teve chance nenhuma."""
    _paper(base, "2609.00001", "2026-09-03T07:31:00")
    _triagem(base, "2609.00001")
    _execucao(base, "run-a", fim="2026-09-03T09:23:23", classificou=1)
    _paper(base, "2609.00002", "2026-09-03T09:23:23")
    base.commit()

    item = checar_pendencias(cfg)
    assert item.estado == OK
    assert item.dados["atrasados"] == 0


def test_nascido_durante_o_refresh_conta_como_fila(cfg, base):
    """O corte e o fim do estagio 3, nao o fim da rodada. O refresh (estagio 4)
    grava paper novo entre os dois instantes; se o refresh demora, esse paper
    fica com `primeiro_visto_em < finalizado_em` sem nunca ter tido chance."""
    _paper(base, "2609.00001", "2026-09-04T07:31:00")
    _triagem(base, "2609.00001", run_id="run-a", quando="2026-09-04T07:33:07")
    _execucao(base, "run-a", fim="2026-09-04T07:33:40", classificou=1)
    # descoberto pelo refresh, 4 s depois da ultima triagem e 29 s antes do fim
    _paper(base, "2609.00002", "2026-09-04T07:33:11")
    base.commit()

    item = checar_pendencias(cfg)
    assert item.estado == OK
    assert item.dados == {"pendentes": 1, "atrasados": 0, "na_fila": 1}


def test_corte_e_a_ultima_triagem_da_rodada_nao_o_fim_dela(cfg, base):
    """Quem nasceu antes do fim do estagio 3 continua sendo acusado, e o
    instante reportado e o da ultima triagem, nao o do fim da rodada."""
    _paper(base, "2609.00001", "2026-09-04T07:31:00")
    _triagem(base, "2609.00001", run_id="run-a", quando="2026-09-04T07:33:07")
    _execucao(base, "run-a", fim="2026-09-04T07:33:40", classificou=1)
    _paper(base, "2609.00002", "2026-09-04T07:33:00")
    base.commit()

    item = checar_pendencias(cfg)
    assert item.estado == AVISO
    assert item.dados["corte"] == "2026-09-04T07:33:07"
    assert item.dados["ids"] == ["2609.00002"]


def test_execucao_sem_triagem_propria_cai_no_fim_da_rodada(cfg, base):
    """Se todas as triagens da rodada foram reclassificadas depois (o `run_id`
    da linha troca), sobra so `finalizado_em` como reserva."""
    _paper(base, "2609.00001", "2026-09-04T07:31:00")
    _triagem(base, "2609.00001", run_id="run-reclassificacao", quando="2026-09-04T10:00:00")
    _execucao(base, "run-a", fim="2026-09-04T07:33:40", classificou=1)
    _paper(base, "2609.00002", "2026-09-04T07:33:00")
    base.commit()

    item = checar_pendencias(cfg)
    assert item.estado == AVISO
    assert item.dados["corte"] == "2026-09-04T07:33:40"


def test_sem_execucao_que_classificou_tudo_e_fila(cfg, base):
    """Base recem-criada: sem corte, nada pode ser chamado de atrasado."""
    _paper(base, "2609.00001", "2026-01-01T00:00:00")
    base.commit()

    item = checar_pendencias(cfg)
    assert item.estado == OK
    assert item.dados["na_fila"] == 1


def test_execucao_sem_classificar_nao_serve_de_corte(cfg, base):
    """`run --only export` fecha uma execucao sem rodar o estagio 3: ela nao
    prova que o pendente teve chance."""
    _paper(base, "2609.00001", "2026-09-03T07:00:00")
    _execucao(base, "run-export", fim="2026-09-03T09:00:00", classificou=0)
    base.commit()

    item = checar_pendencias(cfg)
    assert item.estado == OK
    assert item.dados["atrasados"] == 0


def test_execucao_morta_no_meio_nao_serve_de_corte(cfg, base):
    """Foi o que aconteceu em 02/09: SIGTERM, `finalizado_em` NULL."""
    _paper(base, "2609.00001", "2026-09-03T07:00:00")
    _execucao(base, "run-morta", fim=None, classificou=3)
    base.commit()

    item = checar_pendencias(cfg)
    assert item.estado == OK
    assert item.dados["atrasados"] == 0


# ── repescagem falhou: e aviso ──────────────────────────────────────────────


def test_pendente_que_atravessou_uma_rodada_vira_aviso(cfg, base):
    _paper(base, "2609.00001", "2026-09-03T07:00:00")
    _execucao(base, "run-a", fim="2026-09-03T09:00:00", classificou=5)
    base.commit()

    item = checar_pendencias(cfg)
    assert item.estado == AVISO
    assert item.dados["atrasados"] == 1
    assert item.dados["ids"] == ["2609.00001"]
    assert "2609.00001" in item.detalhe
    assert "--only classificacao,export" in item.detalhe


def test_aviso_soma_a_fila_sem_confundir_com_atrasado(cfg, base):
    _paper(base, "2609.00001", "2026-09-03T07:00:00")   # atrasado
    _execucao(base, "run-a", fim="2026-09-03T09:00:00", classificou=5)
    _paper(base, "2609.00002", "2026-09-03T09:23:23")   # na fila
    base.commit()

    item = checar_pendencias(cfg)
    assert item.estado == AVISO
    assert item.dados["atrasados"] == 1
    assert item.dados["na_fila"] == 1
    assert "+1 na fila" in item.detalhe


def test_amostra_do_aviso_para_em_tres_ids(cfg, base):
    for i in range(5):
        _paper(base, f"2609.0000{i}", "2026-09-03T07:00:00")
    _execucao(base, "run-a", fim="2026-09-03T09:00:00", classificou=5)
    base.commit()

    item = checar_pendencias(cfg)
    assert item.estado == AVISO
    assert item.dados["atrasados"] == 5
    assert item.detalhe.count("2609.") == 3
    assert "..." in item.detalhe


def test_corte_e_a_execucao_mais_recente_que_classificou(cfg, base):
    """Uma rodada antiga nao pode acusar paper que nasceu depois dela."""
    _execucao(base, "run-velha", fim="2026-09-01T09:00:00", classificou=5)
    _execucao(base, "run-nova", fim="2026-09-03T09:00:00", classificou=5)
    _paper(base, "2609.00001", "2026-09-02T07:00:00")
    base.commit()

    item = checar_pendencias(cfg)
    assert item.estado == AVISO
    assert item.dados["corte"] == "2026-09-03T09:00:00"


# ── toda execucao que classificou serve de corte ────────────────────────────


def test_execucao_dirigida_tambem_e_corte(cfg, base):
    """Nao ha mais recorte fixo: `reclassificar` varre o que mandarem varrer e
    a linha dele em `log_execucao` conta como qualquer outra."""
    _paper(base, "2609.00001", "2026-09-04T07:33:00")
    _execucao(base, "run-a", fim="2026-09-03T09:00:00", classificou=5)
    _execucao(base, "run-total", fim="2026-09-04T08:55:00", classificou=308)
    base.commit()

    item = checar_pendencias(cfg)
    assert item.estado == AVISO
    assert item.dados["corte"] == "2026-09-04T08:55:00"
    assert item.dados["ids"] == ["2609.00001"]


# ── vocabulario ─────────────────────────────────────────────────────────────


def test_vocabulario_vazio_e_aviso(cfg, base):
    item = checar_vocabulario(cfg)
    assert item.estado == AVISO
    assert "taxonomia carregar" in item.detalhe
    assert item.dados == {"areas": 0, "subareas": 0, "vertentes": 0}


def test_so_areas_ainda_e_aviso(cfg, base):
    """Os dois enums do Estagio A precisam existir; um so nao basta."""
    from conftest import AREA_TESTE, SUBAREA_TESTE

    db.upsert_area(base, {"area": AREA_TESTE, "definicao": "d"})
    db.upsert_area(base, {"area": SUBAREA_TESTE, "definicao": "d", "area_pai": AREA_TESTE})
    base.commit()

    item = checar_vocabulario(cfg)
    assert item.estado == AVISO
    assert "dim_vertente" in item.detalhe and "dim_area" not in item.detalhe


def test_raiz_sem_subarea_e_aviso(cfg, base):
    """Raiz sem sub-area nao oferece celula nenhuma: contar `dim_area` inteira
    faria o diagnostico dizer OK onde o Estagio A cai com "vocabulario
    vazio"."""
    db.upsert_area(base, {"area": "Agentes & automação", "definicao": "d"})
    db.upsert_vertente(base, {"vertente": "Medir", "definicao": "d"})
    base.commit()

    item = checar_vocabulario(cfg)
    assert item.estado == AVISO
    assert item.dados == {"areas": 0, "subareas": 0, "vertentes": 1}


def test_vocabulario_povoado_e_ok(cfg, base):
    from conftest import povoar_vocabulario

    with db.transacao(base):
        povoar_vocabulario(base)
    base.commit()

    item = checar_vocabulario(cfg)
    assert item.estado == OK
    assert item.dados == {"areas": 1, "subareas": 2, "vertentes": 1}


# ── `fora` sem regra de descarte ────────────────────────────────────────────


def _item(itens, nome):
    return {i.nome: i for i in itens}[nome]


def _classificar(conn, paper_id, natureza, prerequisito):
    conn.execute(
        "UPDATE fato_triagem SET natureza = ?, prerequisito = ? WHERE paper_id = ?",
        (natureza, prerequisito, paper_id),
    )


def test_regime_mede_o_que_e_do_regime_anterior(cfg, base):
    """Antes da reclassificacao total: `fora` com regra que saiu e aprovado
    sem natureza. Aviso, nunca erro - nada disso impede a rodada."""
    _paper(base, "2609.00001", "2026-09-03T07:00:00")
    _paper(base, "2609.00002", "2026-09-03T07:00:00")
    _triagem(base, "2609.00001", regra_fora="treino_ou_postreino")
    _triagem(base, "2609.00002", "aprovado")
    base.commit()

    item = _item([checar_regime(cfg)], "regime")
    assert item.estado == AVISO
    assert item.dados["fora_regra_antiga"] == 1
    assert item.dados["aprovado_sem_natureza"] == 1
    assert "reclassificar --tudo" in item.detalhe


def test_regime_acusa_natureza_incoerente(cfg, base):
    _paper(base, "2609.00001", "2026-09-03T07:00:00")
    _triagem(base, "2609.00001", "aprovado")
    _classificar(base, "2609.00001", "teoria", "implementar")
    base.commit()

    item = _item([checar_regime(cfg)], "regime")
    assert item.estado == AVISO and item.dados["incoerentes"] == 1


def test_regime_coerente_e_ok(cfg, base):
    _paper(base, "2609.00001", "2026-09-03T07:00:00")
    _paper(base, "2609.00002", "2026-09-03T07:00:00")
    _triagem(base, "2609.00001", "aprovado")
    _classificar(base, "2609.00001", "proposta", "implementar")
    _triagem(base, "2609.00002", regra_fora="fora_de_escopo")
    base.commit()

    item = _item([checar_regime(cfg)], "regime")
    assert item.estado == OK


def test_fora_sem_regra_e_impossivel_no_banco(base):
    """O `doutor` checava `fora` sem regra; desde o ADR 004 o CHECK de
    `fato_triagem` o recusa na escrita, e a checagem saiu."""
    _paper(base, "2609.00001", "2026-09-03T07:00:00")
    with pytest.raises(sqlite3.IntegrityError):
        _triagem(base, "2609.00001", regra_fora=None)


# ── integracao ──────────────────────────────────────────────────────────────


def test_reclassificar_dirigido_vira_corte_de_pendencia(cfg, base):
    """A rodada de `reclassificar` entra em `log_execucao` (spec, secao 2) e,
    por isso, passa a valer como prova de que o pendente teve chance."""
    from conftest import LLMDuble, povoar_vocabulario

    from hfpapers import execucao

    with db.transacao(base):
        povoar_vocabulario(base)
    _paper(base, "2609.00001", "2026-09-03T07:00:00")
    _triagem(base, "2609.00001")
    _paper(base, "2609.00002", "2026-09-03T07:00:00")    # pendente, e antigo
    base.commit()

    assert checar_pendencias(cfg).estado == OK           # sem rodada, sem corte

    r = execucao.reclassificar(
        cfg=cfg, conn=base, ids=["2609.00001"], cliente_llm=LLMDuble(base, cfg)
    )
    base.commit()

    item = checar_pendencias(cfg)
    assert item.estado == AVISO
    assert item.dados["ids"] == ["2609.00002"]
    assert item.dados["corte"] == base.execute(
        "SELECT classificado_em AS c FROM fato_triagem WHERE run_id = ?", (r.run_id,)
    ).fetchone()["c"]


def test_rodar_inclui_a_checagem(cfg, base):
    _paper(base, "2609.00001", "2026-09-03T07:00:00")
    _execucao(base, "run-a", fim="2026-09-03T09:00:00", classificou=5)
    base.commit()

    itens = {i.nome: i for i in rodar(cfg, sem_rede=True)}
    assert itens["triagem"].estado == AVISO
    # a pendencia avisa, mas nao bloqueia: `erro` e so para o que impede rodar
    assert not [i for i in itens.values() if i.estado == "erro" and i.nome == "triagem"]
    # a fiacao dos outros checks tambem passa por aqui: sem esta linha,
    # apagar a chamada de `checar_vocabulario` em `rodar` nao quebraria nada
    assert itens["vocabulario"].estado == AVISO      # base de teste sem vocabulario
    assert itens["regime"].estado == OK              # e sem triagem do regime anterior
