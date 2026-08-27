"""Lista de trabalho do backfill: a uniao das tres fontes do seed."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from .. import digests as mod_digests
from ..fontes.modelos import id_base
from .tipos import ItemTrabalho


def montar_lista(seed: Path) -> dict[str, ItemTrabalho]:
    estado = json.loads((seed / "hf-digest-estado.json").read_text(encoding="utf-8"))
    tax = json.loads((seed / "taxonomia.json").read_text(encoding="utf-8"))
    digests = mod_digests.carregar_digests(seed / "digests")
    fichas = mod_digests.fichas_por_id(digests)

    itens: dict[str, ItemTrabalho] = {}

    def item(pid: str) -> ItemTrabalho:
        pid = id_base(pid)
        return itens.setdefault(pid, ItemTrabalho(paper_id=pid))

    for pid, dados in estado.get("ids_vistos", {}).items():
        it = item(pid)
        it.veredito = dados.get("veredito")
        it.upvotes_dia1 = dados.get("upvotes_dia1")
        pub = dados.get("publicado")
        it.data_publicado = dt.date.fromisoformat(pub) if pub else None
        it.fontes.add("estado")

    for pid in tax.get("classificacoes", {}):
        item(pid).fontes.add("taxonomia")

    for pid, f in fichas.items():
        it = item(pid)
        it.fontes.add("digest")
        it.titulo = it.titulo or f.titulo
        if it.upvotes_dia1 is None:
            it.upvotes_dia1 = f.upvotes_dia1
        if it.data_publicado is None:
            it.data_publicado = f.data
        # o veredito de um id que so existe no digest sai da secao onde a ficha
        # esta: `## 3.` => estrito, `## 4.` => amplo
        if it.veredito is None:
            it.veredito = f.veredito

    return itens
