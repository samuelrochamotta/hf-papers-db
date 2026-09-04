"""O que vem do historico pronto e entra sem passar por LLM.

Triagem (o veredito de cada paper) e as 83 classificacoes curadas a mao. As duas
sao autoritativas: o backfill nao as regenera nem as reabre.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .. import db, taxonomia
from ..config import Config
from ..fontes.modelos import id_base
from .tipos import RUN_ID, ItemTrabalho, ResultadoBackfill


def importar_triagem(
    conn: sqlite3.Connection, itens: dict[str, ItemTrabalho], res: ResultadoBackfill
) -> None:
    """Veredito historico -> `fato_triagem`, com `revisao = 0`.

    Os campos de portabilidade ficam NULL: nao foram registrados na epoca.
    `INSERT OR IGNORE` protege uma reclassificacao posterior de ser sobrescrita
    por um segundo backfill.

    Sao duas contagens diferentes, e confundi-las ja gerou dado falso em
    `log_execucao`: `res.vereditos` e o retrato da tabela inteira (a base tem
    papers que nao vieram do seed), `res.vereditos_importados` e o que este
    backfill de fato gravou - zero quando o IGNORE descarta tudo.
    """
    agora = db.agora()
    importados: dict[str, int] = {}
    with db.transacao(conn):
        for pid, it in itens.items():
            if not it.veredito:
                continue
            entrou = db.inserir_ignorando(
                conn,
                "fato_triagem",
                {
                    "paper_id": pid,
                    "veredito": it.veredito,
                    "regra_fora": None,
                    "justificativa": "Importado do historico (" + ", ".join(sorted(it.fontes)) + ")",
                    "decisao_fronteira": 0,
                    "classificado_em": agora,
                    "run_id": RUN_ID,
                    "revisao": 0,
                },
            )
            if entrou:
                importados[it.veredito] = importados.get(it.veredito, 0) + 1
    res.triagens = db.contar(conn, "fato_triagem")
    res.vereditos_importados = importados
    res.vereditos = {
        r["veredito"]: r["n"]
        for r in conn.execute(
            "SELECT veredito, COUNT(*) AS n FROM fato_triagem GROUP BY veredito"
        )
    }


def importar_classificacoes(
    conn: sqlite3.Connection, seed: Path, res: ResultadoBackfill, cfg: Config
) -> None:
    """As 83 classificacoes a mao sao autoritativas - nao sao regeneradas."""
    tax = json.loads((seed / "taxonomia.json").read_text(encoding="utf-8"))
    existentes = {r["paper_id"] for r in conn.execute("SELECT paper_id FROM dim_paper")}
    n = 0
    with db.transacao(conn):
        for pid, c in tax.get("classificacoes", {}).items():
            pid = id_base(pid)
            if pid not in existentes:
                continue
            taxonomia.aplicar_classificacao(
                conn,
                pid,
                area_primaria=c.get("area", ""),
                areas_secundarias=c.get("areas_secundarias", []),
                topicos_paper=c.get("topicos", []),
                cfg=cfg.taxonomia,
            )
            n += 1
    res.classificacoes_curadas = n
