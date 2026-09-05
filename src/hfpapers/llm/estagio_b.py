"""Estagio B - portabilidade, criterios, veredito e ficha.

Roda so nos sobreviventes do Estagio A (~10/dia).

As validacoes da secao 4.4 rodam em codigo, depois da resposta: o schema garante
forma, nao coerencia. Violacao vira `ErroValidacao`, que o cliente reenvia com a
mensagem anexada. Se todas as tentativas do `ClienteLLM` se esgotarem, sobe
`ErroLLM` - quem decide o que fazer com isso e `estagios/classificacao.py`
(issue #1: nao fabrica veredito, deixa o paper pendente para a segunda passada
do estagio e, se preciso, para a proxima rodada).

Ha duas classes de regra, e a diferenca esta em quem paga quando o modelo
insiste no erro:

* **Essenciais** (`validar`): `fora` sem regra, aprovado sem criterio, veredito
  que contradiz a lista de criterios. Sem elas o veredito nao e integro, entao
  o paper fica pendente a ficar gravado errado.
* **De fronteira** (`Validador`): `decisao_fronteira` sem contraparte, ou
  contraparte do mesmo lado do veredito. E metadado sobre o veredito, nao o
  veredito: refaz **uma vez** e, se persistir, grava como veio e avisa
  (`fronteira_incoerente`). A flag nunca vira `false` pela nossa mao.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from ..config import Config, config
from ..log import logger
from . import prompts, schemas
from .cliente import ClienteLLM, ErroValidacao, Uso
from .estagio_a import PaperEntrada

log = logger("llm")

SISTEMA = (
    "Voce avalia papers de IA para engenheiros que usam modelos de linguagem em "
    "producao e nao treinam modelos. Emite os campos na ordem declarada no "
    "schema: o padrao e escrito e testado, os criterios sao listados e so entao "
    "o veredito e decidido. Responde sempre em JSON valido, em portugues do Brasil."
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

# Codigos de aviso que sobem em `ResultadoB.avisos`; `classificacao` anexa o
# `paper_id` e repassa para o resultado da rodada.
AVISO_FRONTEIRA_INCOERENTE = "fronteira_incoerente"
AVISO_CONTRAPARTE_DESCARTADA = "fronteira_contraparte_descartada"


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
    criterios_veredito: list[str]
    veredito: str
    regra_fora: Optional[str]
    justificativa_veredito: str
    decisao_fronteira: bool
    fronteira_contraparte: Optional[str]
    ficha: Optional[Ficha]
    uso: Uso = field(default_factory=Uso)
    avisos: list[str] = field(default_factory=list)

    @property
    def aprovado(self) -> bool:
        return self.veredito in ("amplo", "estrito")


# ── validacoes da secao 4.4 ─────────────────────────────────────────────────


def _criterios(dados: dict[str, Any]) -> list[str]:
    brutos = dados.get("criterios_veredito") or []
    return list(dict.fromkeys(c for c in brutos if isinstance(c, str)))


def validar(dados: dict[str, Any]) -> None:
    """Regras essenciais: violacao e `ErroValidacao` ate esgotar as tentativas."""
    veredito = dados.get("veredito")
    ficha = dados.get("ficha")
    padrao = dados.get("padrao_extraido")
    teste = dados.get("teste_portabilidade")
    tem_artefato = dados.get("tem_artefato_nomeado")
    criterios = _criterios(dados)
    regra = dados.get("regra_fora")

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
                "reprovou no teste de portabilidade: o veredito tem de ser 'fora' "
                f"(regra_fora '{schemas.REGRA_PORTABILIDADE}', se nenhuma regra de "
                "conteudo bater antes)"
            )
        mecanismo = (padrao.get("mecanismo") or "").strip()
        if not mecanismo:
            raise ErroValidacao("padrao_extraido.mecanismo vazio")
        if RE_SEGUNDA_PESSOA.search(mecanismo) or RE_IMPERATIVO.search(mecanismo):
            raise ErroValidacao(
                "o Padrao Extraido e impessoal: reescreva o mecanismo sem 'voce' e "
                "sem verbo dirigido ao leitor (isso pertence a Implicacao Pratica)"
            )

    # Regra de descarte: todo `fora` tem exatamente uma (ticket 02), e a de
    # portabilidade so existe se o teste de fato reprovou.
    if veredito == "fora" and not regra:
        raise ErroValidacao(
            "veredito 'fora' exige regra_fora: a primeira regra de descarte que bate, "
            "na ordem (" + ", ".join(schemas.REGRAS_FORA) + ")"
        )
    if regra == schemas.REGRA_PORTABILIDADE and not (
        isinstance(teste, dict) and teste.get("aprovado") is False
    ):
        raise ErroValidacao(
            f"regra_fora '{schemas.REGRA_PORTABILIDADE}' so vale quando "
            "teste_portabilidade.aprovado e false"
        )

    # Criterios de veredito (ticket 03): o veredito decorre da lista.
    if veredito == "fora" and criterios:
        raise ErroValidacao(
            "veredito 'fora' exige criterios_veredito vazio: criterio e motivo de "
            "aprovacao, e descarte tem regra_fora"
        )
    if veredito in ("amplo", "estrito"):
        if not criterios:
            raise ErroValidacao(
                f"veredito '{veredito}' exige ao menos um criterio em criterios_veredito "
                "(" + ", ".join(schemas.CRITERIOS_VEREDITO) + ")"
            )
        implicado = schemas.veredito_dos_criterios(criterios)
        if implicado != veredito:
            estritos = [c for c in criterios if c in schemas.CRITERIOS_ESTRITO]
            if implicado == "estrito":
                detalhe = (
                    f"a lista tem criterio de estrito ({', '.join(estritos)}) e "
                    "qualquer criterio de estrito implica veredito 'estrito'; ou o "
                    "veredito e 'estrito', ou esse criterio nao vale e sai da lista"
                )
            else:
                detalhe = (
                    "a lista so tem criterios de amplo, entao o veredito e 'amplo'; "
                    "se o paper e 'estrito', diga por qual criterio de estrito"
                )
            raise ErroValidacao(f"veredito '{veredito}' incoerente com criterios_veredito: {detalhe}")

    # Ultima, porque so faz sentido cobrar a explicacao de um veredito coerente.
    # O painel exibe este texto sob "POR QUE ESTRITO"/"POR QUE AMPLO": sem piso,
    # um "..." atravessa o schema e vira a explicacao da decisao.
    schemas.validar_justificativa(
        dados.get("justificativa_veredito"), "justificativa_veredito"
    )


def incoerencia_de_fronteira(dados: dict[str, Any]) -> Optional[str]:
    """Descreve por que a fronteira declarada nao se sustenta; None se coerente.

    So olha o caso `decisao_fronteira = true`: a contraparte e obrigatoria e
    tem de ser de lado diferente do veredito (ticket 06). `false` com
    contraparte preenchida nao e incoerencia de fronteira - a contraparte e
    descartada em `avaliar`, com aviso.
    """
    if not dados.get("decisao_fronteira"):
        return None
    veredito = dados.get("veredito")
    contraparte = dados.get("fronteira_contraparte")
    if not contraparte:
        return (
            "decisao_fronteira true exige fronteira_contraparte: a regra de descarte "
            "ou o criterio do outro lado que quase venceu"
        )
    if schemas.lado(contraparte) == veredito:
        return (
            f"fronteira_contraparte '{contraparte}' e do mesmo lado do veredito "
            f"'{veredito}': a contraparte e o que quase venceu, do outro lado"
        )
    return None


class Validador:
    """`validar` mais a regra de fronteira, com memoria entre as tentativas.

    E passado como `validar=` ao `ClienteLLM.chamar`, que o chama a cada
    resposta e reenvia a mensagem do `ErroValidacao` ao modelo. A memoria e o
    que permite a regra de fronteira ser "refazer uma vez": na primeira
    incoerencia levanta como qualquer outra regra; na segunda deixa passar e
    registra o aviso, porque fronteira e metadado - nao vale um paper pendente.
    Uma instancia por chamada: o estado e desta resposta, nao do processo.
    """

    def __init__(self) -> None:
        self.fronteira_refeita = False
        self.avisos: list[str] = []

    def __call__(self, dados: dict[str, Any]) -> None:
        validar(dados)
        problema = incoerencia_de_fronteira(dados)
        if problema is None:
            return
        if not self.fronteira_refeita:
            self.fronteira_refeita = True
            raise ErroValidacao(problema)
        log.warning("fronteira incoerente mantida como veio: %s", problema)
        self.avisos.append(AVISO_FRONTEIRA_INCOERENTE)


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
    validador = Validador()
    resposta = cliente.chamar(
        etapa="estagio_b",
        modelo=est.modelo,
        prompt=montar_prompt(paper, cfg),
        sistema=SISTEMA,
        response_format=schemas.response_format("avaliacao_ficha", schemas.SCHEMA_ESTAGIO_B),
        temperatura=est.temperatura,
        max_tokens=est.max_tokens,
        paper_id=paper.paper_id,
        validar=validador,
    )
    d = resposta.dados
    veredito = d["veredito"]
    avisos = list(validador.avisos)

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

    fronteira = bool(d.get("decisao_fronteira"))
    contraparte = d.get("fronteira_contraparte") or None
    if not fronteira and contraparte:
        # Sem fronteira nao ha "quase": a contraparte e ruido e sai, com aviso.
        # A flag e o que o modelo declarou e fica como veio.
        log.warning(
            "%s: fronteira_contraparte '%s' descartada porque decisao_fronteira e false",
            paper.paper_id, contraparte,
        )
        avisos.append(AVISO_CONTRAPARTE_DESCARTADA)
        contraparte = None

    return ResultadoB(
        paper_id=paper.paper_id,
        tem_artefato_nomeado=bool(d.get("tem_artefato_nomeado")),
        padrao_extraido=padrao,
        teste_portabilidade=d.get("teste_portabilidade"),
        criterios_veredito=_criterios(d) if veredito != "fora" else [],
        veredito=veredito,
        regra_fora=d.get("regra_fora") if veredito == "fora" else None,
        justificativa_veredito=d.get("justificativa_veredito", ""),
        decisao_fronteira=fronteira,
        fronteira_contraparte=contraparte,
        ficha=ficha,
        uso=resposta.uso,
        avisos=avisos,
    )
