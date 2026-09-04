"""Estagio B - portabilidade, veredito e ficha.

Roda so nos sobreviventes do Estagio A (~10/dia).

As validacoes da secao 4.4 rodam em codigo, depois da resposta: o schema garante
forma, nao coerencia. Violacao vira `ErroValidacao`, que o cliente reenvia com a
mensagem anexada. Se todas as tentativas do `ClienteLLM` se esgotarem, sobe
`ErroLLM` - quem decide o que fazer com isso e `estagios/classificacao.py`
(issue #1: nao fabrica veredito, deixa o paper pendente para a segunda passada
do estagio e, se preciso, para a proxima rodada).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from ..config import Config, config
from . import prompts, schemas
from .cliente import ClienteLLM, ErroValidacao, Uso
from .estagio_a import PaperEntrada

SISTEMA = (
    "Voce avalia papers de IA para engenheiros que usam modelos de linguagem em "
    "producao e nao treinam modelos. Emite os campos na ordem declarada no "
    "schema: o padrao e escrito e testado antes de o veredito ser decidido. "
    "Responde sempre em JSON valido, em portugues do Brasil."
)

# O Padrao e impessoal por definicao (secao 6.4): pronome de segunda pessoa ou
# imperativo dirigido ao leitor sao a marca de que a Implicacao Pratica vazou
# para dentro dele.
RE_SEGUNDA_PESSOA = re.compile(
    r"\b(voc[eê]s?|teu|tua|seus?\s+prompts?|vc)\b", re.IGNORECASE
)
RE_IMPERATIVO = re.compile(
    r"(?:^|[.;]\s+)(use|utilize|adote|considere|evite|prefira|fa[çc]a|troque|"
    r"meça|meca|monte|escolha|verifique|aplique|comece|pare)\b",
    re.IGNORECASE,
)


@dataclass
class Ficha:
    achado: str
    implicacao_pratica: str
    exemplo_concreto: str
    ressalva: str
    padrao_nome: Optional[str] = None
    padrao_mecanismo: Optional[str] = None


@dataclass
class ResultadoB:
    paper_id: str
    tem_artefato_nomeado: bool
    padrao_extraido: Optional[dict[str, str]]
    teste_portabilidade: Optional[dict[str, bool]]
    veredito: str
    justificativa_veredito: str
    decisao_fronteira: bool
    ficha: Optional[Ficha]
    uso: Uso = field(default_factory=Uso)

    @property
    def aprovado(self) -> bool:
        return self.veredito in ("amplo", "estrito")


# ── validacoes da secao 4.4 ─────────────────────────────────────────────────


def validar(dados: dict[str, Any]) -> None:
    veredito = dados.get("veredito")
    ficha = dados.get("ficha")
    padrao = dados.get("padrao_extraido")
    teste = dados.get("teste_portabilidade")
    tem_artefato = dados.get("tem_artefato_nomeado")

    if veredito == "fora" and ficha is not None:
        raise ErroValidacao("veredito 'fora' exige ficha null")

    if veredito in ("amplo", "estrito"):
        if not isinstance(ficha, dict):
            raise ErroValidacao(f"veredito '{veredito}' exige ficha preenchida")
        vazios = [
            c
            for c in ("achado", "implicacao_pratica", "exemplo_concreto", "ressalva")
            if not (ficha.get(c) or "").strip()
        ]
        if vazios:
            raise ErroValidacao("campos vazios na ficha: " + ", ".join(vazios))

    if tem_artefato is False and (padrao is not None or teste is not None):
        raise ErroValidacao(
            "sem artefato nomeado, padrao_extraido e teste_portabilidade devem ser null"
        )

    if tem_artefato is True:
        if not isinstance(padrao, dict) or not isinstance(teste, dict):
            raise ErroValidacao(
                "com artefato nomeado, padrao_extraido e teste_portabilidade sao obrigatorios"
            )
        esperado = not (
            teste.get("depende_do_nome_proprio") or teste.get("colapsa_em_generalidade")
        )
        if bool(teste.get("aprovado")) != esperado:
            raise ErroValidacao(
                "teste_portabilidade.aprovado deve ser true apenas quando as duas "
                "formas de reprovacao sao false"
            )
        if teste.get("aprovado") is False and veredito != "fora":
            raise ErroValidacao(
                "reprovou no teste de portabilidade: o veredito tem de ser 'fora'"
            )
        mecanismo = (padrao.get("mecanismo") or "").strip()
        if not mecanismo:
            raise ErroValidacao("padrao_extraido.mecanismo vazio")
        if RE_SEGUNDA_PESSOA.search(mecanismo) or RE_IMPERATIVO.search(mecanismo):
            raise ErroValidacao(
                "o Padrao Extraido e impessoal: reescreva o mecanismo sem 'voce' e "
                "sem verbo dirigido ao leitor (isso pertence a Implicacao Pratica)"
            )


# ── prompt e chamada ────────────────────────────────────────────────────────


def montar_prompt(paper: PaperEntrada, cfg: Optional[Config] = None) -> str:
    resumo = (
        f"**Resumo gerado pelo HF:**\n{paper.ai_summary}" if paper.ai_summary else ""
    )
    return prompts.preencher(
        prompts.carregar("estagio_b", cfg or config()),
        TITULO=paper.titulo,
        KEYWORDS=", ".join(paper.keywords) or "(nenhuma)",
        AREA=paper.area_primaria or "(nao atribuida)",
        TOPICOS=", ".join(paper.topicos) or "(nenhum)",
        ABSTRACT=paper.abstract or "(abstract indisponivel)",
        RESUMO_HF=resumo,
    )


def avaliar(
    cliente: ClienteLLM, paper: PaperEntrada, *, cfg: Optional[Config] = None
) -> ResultadoB:
    cfg = cfg or config()
    est = cfg.llm.estagio_b
    resposta = cliente.chamar(
        etapa="estagio_b",
        modelo=est.modelo,
        prompt=montar_prompt(paper, cfg),
        sistema=SISTEMA,
        response_format=schemas.response_format("avaliacao_ficha", schemas.SCHEMA_ESTAGIO_B),
        temperatura=est.temperatura,
        max_tokens=est.max_tokens,
        paper_id=paper.paper_id,
        validar=validar,
    )
    d = resposta.dados
    padrao = d.get("padrao_extraido")
    ficha_bruta = d.get("ficha")
    ficha = None
    if isinstance(ficha_bruta, dict):
        ficha = Ficha(
            achado=ficha_bruta["achado"],
            implicacao_pratica=ficha_bruta["implicacao_pratica"],
            exemplo_concreto=ficha_bruta["exemplo_concreto"],
            ressalva=ficha_bruta["ressalva"],
            padrao_nome=(padrao or {}).get("nome"),
            padrao_mecanismo=(padrao or {}).get("mecanismo"),
        )
    return ResultadoB(
        paper_id=paper.paper_id,
        tem_artefato_nomeado=bool(d.get("tem_artefato_nomeado")),
        padrao_extraido=padrao,
        teste_portabilidade=d.get("teste_portabilidade"),
        veredito=d["veredito"],
        justificativa_veredito=d.get("justificativa_veredito", ""),
        decisao_fronteira=bool(d.get("decisao_fronteira")),
        ficha=ficha,
        uso=resposta.uso,
    )
