"""Vocabulario compartilhado pelos modulos do backfill.

Fica separado para que `lista`, `hidratacao`, `importacao`, `regeneracao` e
`validacao` nao precisem importar uns aos outros so para trocar dados.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .. import db
from ..llm.cliente import Uso

RUN_ID = db.RUN_ID_BACKFILL


@dataclass
class ResultadoBackfill:
    papers: int = 0
    hidratados: int = 0
    falhas_hidratacao: list[str] = field(default_factory=list)
    triagens: int = 0
    # `vereditos` e o retrato da tabela inteira depois do backfill (e o que o
    # console mostra como "triagens na base"); `vereditos_importados` e so o que
    # ESTA execucao gravou. Numa segunda rodada o primeiro nao muda e o segundo
    # zera - e a diferenca que impede `log_execucao` de dizer que o backfill
    # classificou 308 papers sem ter tocado em nenhum.
    vereditos: dict[str, int] = field(default_factory=dict)
    vereditos_importados: dict[str, int] = field(default_factory=dict)
    classificacoes_curadas: int = 0
    estagio_a: int = 0
    fichas_geradas: int = 0
    fichas_existentes: int = 0
    uso: Uso = field(default_factory=Uso)
    avisos: list[str] = field(default_factory=list)
    relatorio: Optional[Path] = None


@dataclass
class ItemTrabalho:
    paper_id: str
    veredito: Optional[str] = None
    upvotes_dia1: Optional[int] = None
    data_publicado: Optional[dt.date] = None
    titulo: Optional[str] = None
    fontes: set[str] = field(default_factory=set)
