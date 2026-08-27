"""Diagnostico: chave ok? API ok? banco integro?

Nao corrige nada - so responde. Sai com codigo != 0 se algum item for `erro`.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Optional

from . import db
from .config import Config, ambiente, config

OK, AVISO, ERRO = "ok", "aviso", "erro"


@dataclass
class Item:
    nome: str
    estado: str
    detalhe: str
    dados: dict[str, Any] = field(default_factory=dict)


def _ultimo_dia_util(hoje: Optional[dt.date] = None) -> dt.date:
    d = (hoje or dt.date.today()) - dt.timedelta(days=1)
    while d.isoweekday() > 5:
        d -= dt.timedelta(days=1)
    return d


def checar_config(cfg: Config) -> list[Item]:
    itens = [Item("config", OK, f"config.yaml lido; banco em {cfg.caminho_banco}")]
    for nome, est in (("estagio_a", cfg.llm.estagio_a), ("estagio_b", cfg.llm.estagio_b)):
        if est.configurado:
            itens.append(Item(f"modelo.{nome}", OK, est.modelo))
        else:
            itens.append(
                Item(
                    f"modelo.{nome}",
                    AVISO,
                    "ainda PREENCHER - rode `hfpapers modelos listar` e escreva o id no config.yaml",
                )
            )
    return itens


def checar_chave() -> Item:
    chave = ambiente().chave_openrouter()
    if not chave:
        return Item("chave", ERRO, "OPENROUTER_API_KEY ausente (.env ou ambiente)")
    return Item("chave", OK, f"presente ({len(chave)} caracteres, valor nao exibido)")


def checar_hf(cfg: Config, timeout: float = 15.0) -> Item:
    import httpx

    data = _ultimo_dia_util()
    url = f"{cfg.hf.base_url}/api/daily_papers"
    try:
        r = httpx.get(url, params={"date": data.isoformat()}, timeout=timeout)
        r.raise_for_status()
        itens = r.json()
    except Exception as e:  # noqa: BLE001 - o diagnostico reporta, nao propaga
        return Item("api_hf", ERRO, f"{type(e).__name__}: {e}")
    n = len(itens) if isinstance(itens, list) else 0
    estado = OK if n >= 15 else AVISO
    return Item(
        "api_hf",
        estado,
        f"{n} papers em {data.isoformat()}" + ("" if estado == OK else " (volume baixo para dia util)"),
        {"data": data.isoformat(), "qtd": n},
    )


def checar_openrouter(cfg: Config, timeout: float = 20.0) -> Item:
    import httpx

    chave = ambiente().chave_openrouter()
    if not chave:
        return Item("api_openrouter", AVISO, "sem chave - checagem pulada")
    try:
        r = httpx.get(
            f"{cfg.llm.base_url}/models",
            headers={"Authorization": f"Bearer {chave}"},
            timeout=timeout,
        )
        r.raise_for_status()
        modelos = r.json().get("data", [])
    except Exception as e:  # noqa: BLE001
        return Item("api_openrouter", ERRO, f"{type(e).__name__}: {e}")

    ids = {m.get("id") for m in modelos}
    itens_faltando = [
        est.modelo
        for est in (cfg.llm.estagio_a, cfg.llm.estagio_b)
        if est.configurado and est.modelo not in ids
    ]
    if itens_faltando:
        return Item(
            "api_openrouter",
            ERRO,
            f"{len(modelos)} modelos disponiveis; id do config nao existe: {', '.join(itens_faltando)}",
        )
    return Item("api_openrouter", OK, f"{len(modelos)} modelos disponiveis")


def checar_banco(cfg: Config) -> list[Item]:
    existia = cfg.caminho_banco.exists()
    conn = db.abrir(cfg)
    try:
        diag = db.diagnostico_banco(conn)
    finally:
        conn.close()

    itens = [
        Item(
            "banco",
            OK,
            ("aberto" if existia else "criado agora") + f" em {cfg.caminho_banco}",
        )
    ]
    if diag["tabelas_faltando"]:
        itens.append(
            Item("schema", ERRO, "tabelas faltando: " + ", ".join(diag["tabelas_faltando"]))
        )
    else:
        itens.append(Item("schema", OK, f"{len(diag['contagens'])} tabelas presentes"))

    if diag["integridade"] != "ok":
        itens.append(Item("integridade", ERRO, str(diag["integridade"])))
    elif diag["fk_violacoes"]:
        itens.append(Item("integridade", ERRO, f"{diag['fk_violacoes']} violacoes de FK"))
    else:
        itens.append(Item("integridade", OK, f"integrity_check ok, journal={diag['journal_mode']}"))

    resumo = ", ".join(
        f"{t}={n}" for t, n in diag["contagens"].items() if n
    ) or "banco vazio"
    itens.append(Item("conteudo", OK, resumo, diag["contagens"]))
    return itens


def rodar(cfg: Optional[Config] = None, *, sem_rede: bool = False) -> list[Item]:
    cfg = cfg or config()
    itens = checar_config(cfg)
    itens.append(checar_chave())
    if sem_rede:
        itens.append(Item("api_hf", AVISO, "--sem-rede: checagem pulada"))
        itens.append(Item("api_openrouter", AVISO, "--sem-rede: checagem pulada"))
    else:
        itens.append(checar_hf(cfg))
        itens.append(checar_openrouter(cfg))
    itens.extend(checar_banco(cfg))
    return itens
