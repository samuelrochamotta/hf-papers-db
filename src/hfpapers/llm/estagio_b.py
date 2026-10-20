"""Estagio B - natureza, pre-requisito e ficha.

Roda nos sobreviventes do Estagio A. Desde o ADR 004 isso inclui os papers de
treino e os relatorios tecnicos de modelo de fundacao, que antes eram
descartados no A.

As validacoes da secao 2 da spec (`docs/specs/natureza-prerequisito.md`) rodam
em codigo, depois da resposta: o schema garante forma, nao coerencia. Violacao
vira `ErroValidacao`, que o cliente reenvia com a mensagem anexada. Se todas as
tentativas do `ClienteLLM` se esgotarem, sobe `ErroLLM` - quem decide o que
fazer com isso e `estagios/classificacao.py` (issue #1: nao fabrica veredito,
deixa o paper pendente para a segunda passada e, se preciso, para a proxima
rodada).

Ha tres classes de regra, e a diferenca esta em quem paga quando o modelo
insiste no erro:

* **Essenciais** (`validar`): aprovado sem natureza ou sem ficha, natureza que
  contradiz o pre-requisito, padrao que vaza o nome proprio. Sem elas a
  classificacao nao e integra, entao o paper fica pendente a ficar gravado
  errado.
* **Sobrescritas** (`avaliar`): `artefato_status` sem evidencia externa vira
  NULL; campos que sobram num `fora` sao zerados. Nao vale retentativa: o
  schema e fixo e o modelo responde o campo mesmo quando nao foi perguntado.
* **Avisos** (`avisos_de_coerencia`): combinacoes suspeitas, mas possiveis.
  Gravam como veio e sobem para `log_execucao.avisos`.
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
    "Voce avalia papers de IA para leitores com perfis diferentes: quem constroi "
    "produto com modelos de linguagem e quem treina ou pesquisa modelos. Emite os "
    "campos na ordem declarada no schema: a natureza e o padrao vem antes do "
    "pre-requisito, e a justificativa depois de tudo que ela explica. Responde "
    "sempre em JSON valido, em portugues do Brasil."
)

# O Padrao e impessoal por definicao: pronome de segunda pessoa ou imperativo
# dirigido ao leitor sao a marca de que a Implicacao Pratica vazou para dentro
# dele.
RE_SEGUNDA_PESSOA = re.compile(
    r"\b(voc[eê]s?|teu|tua|seus?\s+prompts?|vc)\b", re.IGNORECASE
)
RE_IMPERATIVO = re.compile(
    r"(?:^|[.;]\s+)(use|utilize|adote|considere|evite|prefira|fa[çc]a|troque|"
    r"meça|meca|monte|escolha|verifique|aplique|comece|pare)\b",
    re.IGNORECASE,
)

# Nome proprio do artefato dos autores: o que vem antes do ":" no titulo, e so
# os tokens com cara de nome (acronimo, CamelCase, letra com digito). Substitui
# o teste de portabilidade autoavaliado, que reprovou 7 papers em 4477: o
# modelo se aprovava. Siglas de uso geral nao contam como nome dos autores.
RE_TOKEN_NOME = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:[-.][A-Za-z0-9]+)*")
SIGLAS_COMUNS = frozenset(
    {
        "LLM", "LLMS", "VLM", "VLMS", "MLLM", "MLLMS", "LM", "LMS", "RAG", "RL",
        "RLHF", "RLVR", "SFT", "DPO", "PPO", "GRPO", "KV", "MOE", "AI", "NLP",
        "API", "GPU", "GPUS", "CPU", "SQL", "QA", "COT", "OCR", "ASR", "TTS",
        "SOTA", "MCP", "GUI", "UI", "LORA", "VQA", "ML", "NN", "CNN", "RNN",
    }
)

# Codigos de aviso que sobem em `ResultadoB.avisos`; `classificacao` anexa o
# `paper_id` e repassa para o resultado da rodada.
AVISO_CONTRADICAO_SEM_DEGRAU = "contradicao_sem_degrau"
AVISO_ACHADO_SEM_ACAO = "achado_sem_acao"
AVISO_TREINAR_SEM_DEGRAU = "treinar_sem_degrau"

CAMPOS_FICHA = ("achado", "implicacao_pratica", "exemplo_concreto", "ressalva")


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
    regra_fora: Optional[str]
    natureza: Optional[str]
    padrao_extraido: Optional[dict[str, str]]
    prerequisito: Optional[str]
    pratica_contradita: Optional[str]
    falta_o_como: Optional[str]
    artefato_status: Optional[str]
    justificativa: str
    ficha: Optional[Ficha]
    uso: Uso = field(default_factory=Uso)
    avisos: list[str] = field(default_factory=list)

    @property
    def veredito(self) -> str:
        return "fora" if self.regra_fora else "aprovado"

    @property
    def aprovado(self) -> bool:
        return self.regra_fora is None


# ── validacoes ──────────────────────────────────────────────────────────────


def _texto(valor: Any) -> Optional[str]:
    """Texto aparado, ou None. Vazio e ausencia: nao vale retentativa."""
    if not isinstance(valor, str):
        return None
    limpo = valor.strip()
    return limpo or None


def nomes_proprios(titulo: str) -> set[str]:
    """Os tokens com cara de nome do artefato, tirados de antes do ":" do titulo.

    Sem ":" nao ha nome a proteger - o titulo e uma frase, e caçar acronimo nele
    pegaria sigla de dominio. Devolve vazio nesse caso.
    """
    if ":" not in titulo:
        return set()
    prefixo = titulo.split(":", 1)[0]
    nomes = set()
    for tok in RE_TOKEN_NOME.findall(prefixo):
        if tok.upper() in SIGLAS_COMUNS or len(tok) < 3:
            continue
        miolo = tok[1:]
        acronimo = sum(c.isupper() for c in tok) >= 2
        camel = any(c.isupper() for c in miolo) and any(c.islower() for c in tok)
        com_digito = any(c.isdigit() for c in tok) and any(c.isalpha() for c in tok)
        if acronimo or camel or com_digito:
            nomes.add(tok)
    return nomes


def _cita_nome(texto: str, nomes: set[str]) -> Optional[str]:
    for nome in sorted(nomes):
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(nome)}(?![A-Za-z0-9])", texto):
            return nome
    return None


def validar(dados: dict[str, Any], titulo: str = "") -> None:
    """Regras essenciais: violacao e `ErroValidacao` ate esgotar as tentativas."""
    regra = dados.get("regra_fora")
    natureza = dados.get("natureza")
    prereq = dados.get("prerequisito")
    padrao = dados.get("padrao_extraido")
    ficha = dados.get("ficha")

    if regra:
        if ficha is not None or natureza is not None or prereq is not None:
            raise ErroValidacao(
                f"regra_fora '{regra}' e descarte: natureza, prerequisito e ficha "
                "devem ser null"
            )
        schemas.validar_justificativa(dados.get("justificativa"), "justificativa")
        return

    if natureza is None:
        raise ErroValidacao(
            "paper aprovado exige natureza (" + ", ".join(schemas.NATUREZAS) + ")"
        )
    if prereq is None:
        raise ErroValidacao(
            "paper aprovado exige prerequisito ("
            + ", ".join(schemas.PREREQUISITOS) + ")"
        )
    if not isinstance(ficha, dict):
        raise ErroValidacao("paper aprovado exige ficha preenchida")
    vazios = [c for c in CAMPOS_FICHA if not (ficha.get(c) or "").strip()]
    if vazios:
        raise ErroValidacao("campos vazios na ficha: " + ", ".join(vazios))

    if natureza in schemas.NATUREZAS_SEM_ADOCAO and prereq != schemas.SEM_ACAO:
        raise ErroValidacao(
            f"natureza '{natureza}' nao tem o que adotar: prerequisito tem de ser "
            f"'{schemas.SEM_ACAO}'"
        )

    if natureza == "proposta":
        if prereq == schemas.SEM_ACAO:
            raise ErroValidacao(
                "natureza 'proposta' anuncia algo adotavel: prerequisito nao pode ser "
                f"'{schemas.SEM_ACAO}' - diga o degrau mais barato ate o ganho principal"
            )
        if not isinstance(padrao, dict) or not (padrao.get("mecanismo") or "").strip():
            raise ErroValidacao(
                "natureza 'proposta' exige padrao_extraido com nome e mecanismo"
            )
    elif padrao is not None:
        raise ErroValidacao(
            f"padrao_extraido so existe para natureza 'proposta'; em '{natureza}' o "
            "achado ja e o padrao, e o campo e null"
        )

    if isinstance(padrao, dict):
        mecanismo = (padrao.get("mecanismo") or "").strip()
        if RE_SEGUNDA_PESSOA.search(mecanismo) or RE_IMPERATIVO.search(mecanismo):
            raise ErroValidacao(
                "o Padrao Extraido e impessoal: reescreva o mecanismo sem 'voce' e "
                "sem verbo dirigido ao leitor (isso pertence a Implicacao Pratica)"
            )
        nome = _cita_nome(
            f"{padrao.get('nome') or ''} {mecanismo}", nomes_proprios(titulo)
        )
        if nome:
            raise ErroValidacao(
                f"o Padrao Extraido cita '{nome}', o nome proprio dos autores: "
                "descreva o mecanismo de modo que ele se sustente sem o nome - se nao "
                "se sustenta, o padrao nao e portavel"
            )

    # Ultima, porque so faz sentido cobrar a explicacao de uma classificacao
    # coerente. O painel exibe este texto como o "por que" do paper.
    schemas.validar_justificativa(dados.get("justificativa"), "justificativa")


def avisos_de_coerencia(
    r: "ResultadoB", vertentes: list[str], evidencia_artefato: bool
) -> list[str]:
    """Combinacoes possiveis mas suspeitas: viram aviso, nunca retentativa."""
    if not r.aprovado:
        return []
    avisos = []
    if r.pratica_contradita and r.prerequisito == schemas.SEM_ACAO:
        # A contradicao recebe o degrau necessario para aplicar a correcao.
        avisos.append(AVISO_CONTRADICAO_SEM_DEGRAU)
    if r.natureza == "achado_empirico" and r.prerequisito == schemas.SEM_ACAO and not r.pratica_contradita:
        avisos.append(AVISO_ACHADO_SEM_ACAO)
    if (
        vertentes[:1] == ["Treinar"]
        and r.prerequisito == "nenhum"
        and not evidencia_artefato
    ):
        avisos.append(AVISO_TREINAR_SEM_DEGRAU)
    return avisos


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
        VERTENTES=", ".join(paper.vertentes) or "(nenhuma)",
        ABSTRACT=paper.abstract or "(abstract indisponivel)",
        RESUMO_HF=resumo,
        EVIDENCIA_ARTEFATO=_texto_evidencia(paper),
    )


def _texto_evidencia(paper: PaperEntrada) -> str:
    if not paper.evidencia_artefato:
        return (
            "nenhuma (sem repositorio, sem link no abstract, sem modelo ou dataset "
            "vinculado no HF): responda `artefato_status` = null"
        )
    links = ", ".join(paper.links_artefato) or "modelo ou dataset vinculado no HF"
    return f"sim ({links}): responda `artefato_status`"


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
        esforco_raciocinio=est.esforco_raciocinio,
        paper_id=paper.paper_id,
        validar=lambda d: validar(d, paper.titulo),
    )
    d = resposta.dados
    regra = d.get("regra_fora") or None
    aprovado = regra is None

    padrao = d.get("padrao_extraido") if aprovado else None
    ficha = None
    ficha_bruta = d.get("ficha")
    if aprovado and isinstance(ficha_bruta, dict):
        ficha = Ficha(
            **{c: ficha_bruta[c].strip() for c in CAMPOS_FICHA},
            padrao_nome=(padrao or {}).get("nome"),
            padrao_mecanismo=(padrao or {}).get("mecanismo"),
        )

    # Sobrescrita, nao retentativa: o campo esta sempre no schema, e sem
    # evidencia externa o "liberado" do modelo nao tem em que se apoiar.
    status = d.get("artefato_status") if aprovado and paper.evidencia_artefato else None
    if aprovado and d.get("natureza") in schemas.NATUREZAS_SEM_ADOCAO:
        status = None

    r = ResultadoB(
        paper_id=paper.paper_id,
        regra_fora=regra,
        natureza=d.get("natureza") if aprovado else None,
        padrao_extraido=padrao,
        prerequisito=d.get("prerequisito") if aprovado else None,
        pratica_contradita=_texto(d.get("pratica_contradita")) if aprovado else None,
        falta_o_como=_texto(d.get("falta_o_como")) if aprovado else None,
        artefato_status=status,
        justificativa=d.get("justificativa", ""),
        ficha=ficha,
        uso=resposta.uso,
    )
    r.avisos = avisos_de_coerencia(r, paper.vertentes, paper.evidencia_artefato)
    return r
