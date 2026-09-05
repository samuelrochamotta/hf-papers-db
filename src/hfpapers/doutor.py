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
        fora_sem_regra = db.contar(
            conn, "fato_triagem", "veredito = 'fora' AND regra_fora IS NULL"
        )
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

    # Toda regra de descarte e obrigatoria desde `bf3660c`, e o Estagio A e o
    # Estagio B recusam o `fora` sem regra antes de gravar: o que sobra aqui e
    # linha antiga, que a reclassificacao total apaga. Erro, e nao aviso,
    # porque um `fora` sem regra nao explica a si mesmo no painel - e o
    # conserto e um comando, nao uma investigacao.
    if fora_sem_regra:
        itens.append(
            Item(
                "regra_fora",
                ERRO,
                f"{fora_sem_regra} paper(s) 'fora' sem regra de descarte - "
                "rode `hfpapers reclassificar --tudo`",
                {"fora_sem_regra": fora_sem_regra},
            )
        )
    else:
        itens.append(
            Item("regra_fora", OK, "todo 'fora' tem regra de descarte", {"fora_sem_regra": 0})
        )

    resumo = ", ".join(
        f"{t}={n}" for t, n in diag["contagens"].items() if n
    ) or "banco vazio"
    itens.append(Item("conteudo", OK, resumo, diag["contagens"]))
    return itens


def checar_vocabulario(cfg: Config) -> Item:
    """Banco sem area ou sem topico nao classifica: `schema_estagio_a` recusa o
    enum vazio antes da primeira chamada. Aviso, e nao erro, porque o banco
    recem-criado passa por aqui legitimamente - o conserto e uma linha."""
    conn = db.abrir(cfg)
    try:
        n_areas = db.contar(conn, "dim_area")
        n_topicos = db.contar(conn, "dim_topico")
    finally:
        conn.close()

    dados = {"areas": n_areas, "topicos": n_topicos}
    if n_areas and n_topicos:
        return Item("vocabulario", OK, f"{n_areas} areas, {n_topicos} topicos", dados)

    falta = " e ".join(n for n, q in (("dim_area", n_areas), ("dim_topico", n_topicos)) if not q)
    return Item(
        "vocabulario",
        AVISO,
        f"{falta} sem linhas - rode "
        "`hfpapers taxonomia carregar config/taxonomia_inicial.json`",
        dados,
    )


def checar_pendencias(cfg: Config) -> Item:
    """Papers sem veredito - e se a repescagem ja teve chance de pega-los.

    O refresh (estagio 4) roda DEPOIS da classificacao (estagio 3) e grava
    paper novo: o HF acrescenta paper ao daily de um dia ja passado, e o
    refresh o descobre tarde demais para a rodada que o achou. Ele nasce sem
    triagem e so e classificado na rodada seguinte, que varre todo pendente de
    qualquer dia (`classificacao.selecionar` sem `--data`). Isso e latencia
    normal, nao falha - por isso `na fila` fica em `ok`.

    O que merece aviso e o pendente que JA passou por uma rodada de
    classificacao e continuou sem veredito: ali a repescagem teve chance e nao
    pegou. O corte e a ultima execucao que classificou alguem; uma rodada que
    nao classificou nada pode nem ter rodado o estagio 3 (`--only export`),
    entao nao serve de prova de que houve chance.

    O instante do corte e o fim do estagio 3 dessa execucao - o ultimo
    `classificado_em` que ela gravou - e nao `finalizado_em`. `finalizado_em`
    e carimbado depois do refresh, e o refresh e justamente quem grava o
    paper novo: um paper visto entre o fim da classificacao e o fim da rodada
    nao teve chance nenhuma. Em 03/09 e 04/09 os dois instantes cairam no
    mesmo segundo por coincidencia; um refresh que demore mais faria o doutor
    acusar de atraso quem acabou de nascer. `finalizado_em` fica so como
    reserva para uma execucao sem linha propria em `fato_triagem` (todas as
    dela ja reclassificadas, que troca o `run_id` da linha).
    """
    conn = db.abrir(cfg)
    try:
        pendentes = [
            (r["paper_id"], str(r["primeiro_visto_em"] or ""))
            for r in conn.execute(
                "SELECT paper_id, primeiro_visto_em FROM dim_paper "
                "WHERE paper_id NOT IN (SELECT paper_id FROM fato_triagem) "
                "ORDER BY primeiro_visto_em, paper_id"
            )
        ]
        if not pendentes:
            total = db.contar(conn, "dim_paper")
            return Item("triagem", OK, f"{total} papers, todos com veredito", {"pendentes": 0})

        row = conn.execute(
            "SELECT e.run_id, e.finalizado_em, "
            "(SELECT MAX(t.classificado_em) FROM fato_triagem t WHERE t.run_id = e.run_id) AS fim_estagio_3 "
            "FROM log_execucao e "
            "WHERE e.finalizado_em IS NOT NULL "
            "AND COALESCE(e.qtd_fora,0) + COALESCE(e.qtd_amplo,0) + COALESCE(e.qtd_estrito,0) > 0 "
            "ORDER BY e.finalizado_em DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()

    corte = str(row["fim_estagio_3"] or row["finalizado_em"]) if row else ""
    atrasados = [pid for pid, visto in pendentes if corte and visto and visto < corte]
    na_fila = len(pendentes) - len(atrasados)

    if not atrasados:
        return Item(
            "triagem",
            OK,
            f"{na_fila} sem veredito, todos vistos depois da ultima classificacao "
            "(entram na proxima rodada)",
            {"pendentes": len(pendentes), "atrasados": 0, "na_fila": na_fila},
        )

    amostra = ", ".join(atrasados[:3]) + ("..." if len(atrasados) > 3 else "")
    fila = f" (+{na_fila} na fila)" if na_fila else ""
    return Item(
        "triagem",
        AVISO,
        f"{len(atrasados)} sem veredito apos a rodada de {corte[:16]}{fila}: {amostra} "
        "- rode `hfpapers run --only classificacao,export`",
        {
            "pendentes": len(pendentes),
            "atrasados": len(atrasados),
            "na_fila": na_fila,
            "corte": corte,
            "ids": atrasados,
        },
    )


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
    itens.append(checar_vocabulario(cfg))
    itens.append(checar_pendencias(cfg))
    return itens
