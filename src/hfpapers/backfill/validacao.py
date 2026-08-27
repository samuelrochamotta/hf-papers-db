"""Relatorio de validacao: fichas regeneradas vs. as 83 do pipeline antigo."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .. import db, digests as mod_digests
from ..config import Config
from .regeneracao import vereditos_regenerados
from .tipos import ResultadoBackfill


def relatorio_validacao(
    conn: sqlite3.Connection, seed: Path, cfg: Config, res: ResultadoBackfill
) -> Path:
    """Compara as fichas regeneradas com as 83 do pipeline antigo.

    Nao corrige nada: e o instrumento para julgar se o prompt novo reproduz a
    qualidade do antigo. Divergencia grande aponta o prompt do Estagio B, nao as
    fichas antigas.
    """
    historicas = mod_digests.fichas_por_id(mod_digests.carregar_digests(seed / "digests"))
    novos_vereditos = vereditos_regenerados(cfg)
    linhas_md: list[str] = []
    iguais_veredito = divergentes_veredito = 0
    iguais_padrao = divergentes_padrao = 0
    nomes_iguais = 0
    sem_regenerada = 0
    reprovados_agora = 0

    detalhes: list[str] = []
    for pid, h in sorted(historicas.items()):
        veredito_novo = novos_vereditos.get(pid)
        if veredito_novo is None:
            sem_regenerada += 1
            detalhes.append(f"| {pid} | {h.veredito} | (nao regenerada) | — | — |")
            continue

        # 'aprovado' e o registro parcial de uma ficha gerada antes de o veredito
        # passar a ser guardado: sabe-se que passou, nao se foi amplo ou estrito.
        concorda = veredito_novo == h.veredito or (
            veredito_novo == "aprovado" and h.veredito in ("amplo", "estrito")
        )
        if concorda:
            iguais_veredito += 1
        else:
            divergentes_veredito += 1
            if veredito_novo == "fora":
                reprovados_agora += 1

        nova = conn.execute(
            "SELECT padrao_nome, padrao_mecanismo FROM dim_ficha WHERE paper_id = ?",
            (pid,),
        ).fetchone()
        nova = nova or {"padrao_nome": None, "padrao_mecanismo": None}
        tem_padrao_novo = bool(nova["padrao_nome"])
        if tem_padrao_novo == h.tem_padrao:
            iguais_padrao += 1
        else:
            divergentes_padrao += 1

        nome_igual = (
            h.tem_padrao
            and tem_padrao_novo
            and (h.padrao_nome or "").strip().lower() == (nova["padrao_nome"] or "").strip().lower()
        )
        if nome_igual:
            nomes_iguais += 1

        if not concorda or tem_padrao_novo != h.tem_padrao:
            detalhes.append(
                f"| {pid} | {h.veredito} | {veredito_novo} | "
                f"{'sim' if h.tem_padrao else 'nao'} | {'sim' if tem_padrao_novo else 'nao'} |"
            )

    total = len(historicas)
    linhas_md.append("# Validação do backfill — fichas regeneradas vs. históricas\n")
    linhas_md.append(f"Gerado em {db.agora()}  ")
    linhas_md.append(f"Modelo do Estágio B: `{cfg.llm.estagio_b.modelo}`\n")
    linhas_md.append("## Resumo\n")
    linhas_md.append("| Métrica | Valor |")
    linhas_md.append("|---|---|")
    linhas_md.append(f"| Fichas históricas | {total} |")
    linhas_md.append(f"| Regeneradas | {total - sem_regenerada} |")
    linhas_md.append(f"| Mesmo veredito | {iguais_veredito} |")
    linhas_md.append(f"| Veredito divergente | {divergentes_veredito} |")
    linhas_md.append(f"| Aprovado antes, FORA agora | {reprovados_agora} |")
    linhas_md.append(f"| Mesma presença/ausência de Padrão Extraído | {iguais_padrao} |")
    linhas_md.append(f"| Presença de Padrão divergente | {divergentes_padrao} |")
    linhas_md.append(f"| Nome do padrão idêntico | {nomes_iguais} |")
    linhas_md.append("")
    linhas_md.append("## Divergências\n")
    if detalhes:
        linhas_md.append("| paper_id | veredito histórico | veredito novo | padrão histórico | padrão novo |")
        linhas_md.append("|---|---|---|---|---|")
        linhas_md.extend(detalhes)
    else:
        linhas_md.append("Nenhuma divergência de veredito ou de presença de Padrão Extraído.")
    linhas_md.append("")
    linhas_md.append(
        "> Este relatório não corrige nada. Divergência alta significa que o prompt do "
        "Estágio B precisa de ajuste — as fichas históricas já foram revisadas."
    )
    linhas_md.append("")
    linhas_md.append(
        "> O veredito histórico é o que está gravado em `fato_triagem` (o backfill não o "
        "reabre). O veredito novo é o que o Estágio B devolveu nesta regeneração, "
        "registrado em `data/estado/vereditos_estagio_b.json` só para efeito de comparação. "
        "Papers marcados `(nao regenerada)` ainda não passaram pelo Estágio B nesta versão."
    )

    cfg.dir_relatorios.mkdir(parents=True, exist_ok=True)
    caminho = cfg.dir_relatorios / "validacao_backfill.md"
    caminho.write_text("\n".join(linhas_md), encoding="utf-8")
    res.relatorio = caminho
    return caminho
