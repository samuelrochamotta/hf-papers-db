"""Checagem de pendencias de triagem no `hfpapers doutor`.

O caso que motivou a checagem: em 2026-09-03 nove papers estavam sem veredito
porque o refresh (estagio 4) os descobriu depois da classificacao (estagio 3)
da mesma rodada. Isso e latencia normal e nao pode virar aviso; o que precisa
virar aviso e o pendente que ja atravessou uma rodada de classificacao.
"""

from __future__ import annotations

import pytest

from hfpapers import db
from hfpapers.doutor import AVISO, OK, checar_pendencias, rodar


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


def _triagem(conn, paper_id: str, veredito: str = "fora") -> None:
    db.upsert_triagem(
        conn,
        {
            "paper_id": paper_id,
            "veredito": veredito,
            "justificativa": "teste",
            "classificado_em": "2026-09-03T07:00:00",
            "run_id": "run-teste",
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
            "qtd_amplo": 0,
            "qtd_estrito": 0,
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


# ── integracao ──────────────────────────────────────────────────────────────


def test_rodar_inclui_a_checagem(cfg, base):
    _paper(base, "2609.00001", "2026-09-03T07:00:00")
    _execucao(base, "run-a", fim="2026-09-03T09:00:00", classificou=5)
    base.commit()

    itens = {i.nome: i for i in rodar(cfg, sem_rede=True)}
    assert itens["triagem"].estado == AVISO
    # a pendencia avisa, mas nao bloqueia: `erro` e so para o que impede rodar
    assert not [i for i in itens.values() if i.estado == "erro" and i.nome == "triagem"]
