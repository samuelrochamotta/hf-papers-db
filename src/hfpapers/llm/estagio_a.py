"""Estagio A - triagem barata + classificacao taxonomica.

Roda em TODOS os papers do dia, inclusive nos que serao descartados: e o que
garante area, sub-area e vertente para 100% da base, nao so para os aprovados.

`upvotes` nao entra no prompt (secao 6.6) - nem aqui nem no Estagio B.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Any, Optional

from .. import taxonomia
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
    """Os dois eixos que o Estagio A oferece: a area hierarquica e a vertente.

    A vertente viaja com a definicao ao lado do rotulo porque e o complemento
    que fixa o sentido do verbo - "Medir" sozinho se le como tema, "Medir: cria
    o instrumento" nao.
    """

    areas: list[taxonomia.Area] = field(default_factory=list)
    vertentes: list[tuple[str, str]] = field(default_factory=list)

    @property
    def rotulos_area(self) -> list[str]:
        return [a.rotulo for a in self.areas]

    @property
    def rotulos_subarea(self) -> list[str]:
        return [s.rotulo for a in self.areas for s in a.subareas]

    @property
    def rotulos_vertente(self) -> list[str]:
        return [v for v, _ in self.vertentes]

    def texto_areas(self) -> str:
        """A grade aninhada: a sub-area indentada sob a area de que e filha.

        A lista plana era o que o prompt mostrava antes, e escondia justamente
        o parentesco que o enum tambem nao consegue declarar - o modelo tinha de
        adivinhar de quem cada sub-area era filha.
        """
        linhas: list[str] = []
        for a in self.areas:
            linhas.append(f"- **{a.rotulo}** — {a.definicao}")
            linhas.extend(f"    - `{s.rotulo}` — {s.definicao}" for s in a.subareas)
        return "\n".join(linhas)

    def texto_vertentes(self) -> str:
        return "\n".join(f"- **{v}** — {d}" for v, d in self.vertentes)


def carregar_vocabulario(conn: sqlite3.Connection) -> Vocabulario:
    """O que o modelo pode escolher: vira texto no prompt e enum no schema.

    A area vem da grade facetada - raiz com sub-areas -, e nao de `dim_area`
    inteira: a grade plana anterior ainda convive no banco ate a contracao do
    ticket 05, e oferecer as duas juntas daria ao modelo dois vocabularios que
    dizem a mesma coisa em resolucoes diferentes.
    """
    areas = taxonomia.areas_facetadas(conn)
    vertentes = [
        (r["vertente"], r["definicao"])
        for r in conn.execute(
            "SELECT vertente, definicao FROM dim_vertente ORDER BY vertente"
        )
    ]
    return Vocabulario(areas, vertentes)


@dataclass
class ResultadoA:
    paper_id: str
    veredito_preliminar: str
    regra_fora: Optional[str]
    justificativa: str
    area_primaria: str
    subarea_primaria: str
    area_secundaria: Optional[str]
    subarea_secundaria: Optional[str]
    # Ordenada: a dominante em primeiro. E essa ordem que vira a `ordem` da
    # ponte em `taxonomia.aplicar_classificacao`.
    vertentes: list[str]
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
    vertentes: list[str] = field(default_factory=list)


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
        VERTENTES=vocab.texto_vertentes(),
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
            schemas.schema_estagio_a(
                vocab.rotulos_area, vocab.rotulos_subarea, vocab.rotulos_vertente
            ),
        ),
        temperatura=est.temperatura,
        max_tokens=est.max_tokens,
        esforco_raciocinio=est.esforco_raciocinio,
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
        subarea_primaria=d["subarea_primaria"],
        area_secundaria=d.get("area_secundaria"),
        subarea_secundaria=d.get("subarea_secundaria"),
        # A deduplicacao preserva a ordem, que e o que distingue a dominante da
        # secundaria. O teto nao e aplicado aqui: quem o aplica e a persistencia
        # (`taxonomia.aplicar_classificacao`), num lugar so.
        vertentes=list(dict.fromkeys(d.get("vertentes") or [])),
        candidato_novo_rotulo=d.get("candidato_novo_rotulo"),
        uso=resposta.uso,
    )
