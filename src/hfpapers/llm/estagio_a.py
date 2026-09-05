"""Estagio A - triagem barata + classificacao taxonomica.

Roda em TODOS os papers do dia, inclusive nos que serao descartados: e o que
garante area e topico para 100% da base, nao so para os aprovados.

`upvotes` nao entra no prompt (secao 6.6) - nem aqui nem no Estagio B.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Any, Optional

from ..config import Config, config
from . import prompts, schemas
from .cliente import ClienteLLM, ErroValidacao, Uso

SISTEMA = (
    "Voce e um triador de papers de IA para engenheiros que usam modelos de "
    "linguagem em producao e nao treinam modelos. Responde sempre em JSON valido "
    "conforme o schema, em portugues do Brasil."
)


@dataclass
class Vocabulario:
    areas: list[tuple[str, str]] = field(default_factory=list)   # (rotulo, definicao)
    topicos: list[tuple[str, str]] = field(default_factory=list)

    @property
    def rotulos_area(self) -> list[str]:
        return [a for a, _ in self.areas]

    @property
    def rotulos_topico(self) -> list[str]:
        return [t for t, _ in self.topicos]

    def texto_areas(self) -> str:
        return "\n".join(f"- **{a}** — {d}" for a, d in self.areas)

    def texto_topicos(self) -> str:
        return "\n".join(f"- **{t}** — {d}" for t, d in self.topicos)


def carregar_vocabulario(conn: sqlite3.Connection) -> Vocabulario:
    areas = [
        (r["area"], r["definicao"])
        for r in conn.execute("SELECT area, definicao FROM dim_area ORDER BY area")
    ]
    topicos = [
        (r["topico"], r["definicao"])
        for r in conn.execute("SELECT topico, definicao FROM dim_topico ORDER BY topico")
    ]
    return Vocabulario(areas, topicos)


@dataclass
class ResultadoA:
    paper_id: str
    veredito_preliminar: str
    regra_fora: Optional[str]
    justificativa: str
    area_primaria: str
    areas_secundarias: list[str]
    topicos: list[str]
    candidato_novo_rotulo: Optional[dict[str, Any]]
    uso: Uso = field(default_factory=Uso)

    @property
    def candidato(self) -> bool:
        return self.veredito_preliminar == "candidato"


@dataclass
class PaperEntrada:
    """O recorte do paper que a LLM ve. Sem upvotes, de proposito."""

    paper_id: str
    titulo: str
    abstract: str = ""
    keywords: list[str] = field(default_factory=list)
    ai_summary: Optional[str] = None
    area_primaria: Optional[str] = None
    topicos: list[str] = field(default_factory=list)


# ── validacao pos-resposta ──────────────────────────────────────────────────


def validar(dados: dict[str, Any]) -> None:
    """As duas regras do Estagio A que o schema nao consegue garantir sozinho.

    1. Todo `fora` tem regra. O enum aceita `null` porque `candidato` exige
       `null`, e o JSON Schema estrito nao expressa o condicional; sem a rede
       aqui o modelo as vezes nem preenche a regra que existe (ticket 02:
       `2609.01507` era treino e veio nulo). `ErroValidacao` volta ao modelo com
       a mensagem; esgotadas as tentativas, `ErroLLM` deixa o paper pendente -
       nunca um `fora` sem motivo.
    2. A justificativa daqui e a que o painel exibe para os descartados, na
       aba historica - o mesmo problema do campo gemeo do Estagio B, e por isso
       a mesma rede: ver `schemas.validar_justificativa`.
    """
    if dados.get("veredito_preliminar") == "fora" and not dados.get("regra_fora"):
        raise ErroValidacao(
            "veredito 'fora' exige regra_fora: informe a primeira regra de descarte "
            "que bate, na ordem (" + ", ".join(schemas.REGRAS_FORA_CONTEUDO) + ")"
        )
    schemas.validar_justificativa(dados.get("justificativa"), "justificativa")


def montar_prompt(
    paper: PaperEntrada, vocab: Vocabulario, cfg: Optional[Config] = None
) -> str:
    return prompts.preencher(
        prompts.carregar("estagio_a", cfg or config()),
        AREAS=vocab.texto_areas(),
        TOPICOS=vocab.texto_topicos(),
        TITULO=paper.titulo,
        KEYWORDS=", ".join(paper.keywords) or "(nenhuma)",
        ABSTRACT=paper.abstract or "(abstract indisponivel)",
    )


def classificar(
    cliente: ClienteLLM,
    paper: PaperEntrada,
    vocab: Vocabulario,
    *,
    cfg: Optional[Config] = None,
) -> ResultadoA:
    cfg = cfg or config()
    est = cfg.llm.estagio_a
    resposta = cliente.chamar(
        etapa="estagio_a",
        modelo=est.modelo,
        prompt=montar_prompt(paper, vocab, cfg),
        sistema=SISTEMA,
        response_format=schemas.response_format(
            "triagem_taxonomia",
            schemas.schema_estagio_a(vocab.rotulos_area, vocab.rotulos_topico),
        ),
        temperatura=est.temperatura,
        max_tokens=est.max_tokens,
        paper_id=paper.paper_id,
        validar=validar,
    )
    d = resposta.dados
    return ResultadoA(
        paper_id=paper.paper_id,
        veredito_preliminar=d["veredito_preliminar"],
        regra_fora=d.get("regra_fora") if d["veredito_preliminar"] == "fora" else None,
        justificativa=d.get("justificativa", ""),
        area_primaria=d["area_primaria"],
        areas_secundarias=[a for a in d.get("areas_secundarias") or [] if a != d["area_primaria"]],
        topicos=list(dict.fromkeys(d.get("topicos") or []))[: cfg.taxonomia.max_topicos_por_paper],
        candidato_novo_rotulo=d.get("candidato_novo_rotulo"),
        uso=resposta.uso,
    )
