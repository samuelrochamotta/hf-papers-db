"""JSON Schemas dos dois estagios (secoes 4.3 e 4.4 do PROMPT).

Os `enum` de area e topico do Estagio A sao injetados em tempo de execucao a
partir do banco. E isso que impede a LLM de inventar rotulo e fragmentar os
filtros do Power BI.

No Estagio B a **ordem das propriedades e normativa**: ela reproduz a ordem do
raciocinio (o padrao e escrito e testado antes de o veredito ser decidido). Nao
reordene.

O piso da justificativa mora aqui em duas formas - `minLength` no schema e
`validar_justificativa` em codigo. Ficam lado a lado de proposito: a declaracao
sozinha nao e cumprida por todo provedor, e separar as duas em modulos
diferentes seria o convite para elas divergirem. O teto tem so a declaracao e um
aviso no log; `validar_justificativa` explica por que ele nao derruba o paper.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from ..log import logger
from .cliente import ErroValidacao

log = logger("llm")

# Regras de descarte, na ordem de teste (secao 1 de `regras_classificacao.md`).
# Todo `fora` tem exatamente uma; a primeira que bate basta. As cinco primeiras
# sao de conteudo e servem aos dois estagios; `portabilidade_reprovada` e a
# unica que so o Estagio B pode emitir, porque so ele aplica o teste.
REGRAS_FORA_CONTEUDO = [
    "treino_ou_postreino",
    "geracao_de_midia",
    "percepcao_robotica_embodied",
    "relatorio_tecnico_de_modelo",
    "fora_de_escopo",
]
REGRA_PORTABILIDADE = "portabilidade_reprovada"
REGRAS_FORA = [*REGRAS_FORA_CONTEUDO, REGRA_PORTABILIDADE]

VEREDITOS = ["fora", "amplo", "estrito"]

# Criterios de veredito (secao 3): por que um aprovado e estrito ou amplo. O
# veredito decorre da lista - qualquer criterio de estrito ⇒ estrito - e a
# coerencia entre os dois e cobrada em `estagio_b.validar`.
CRITERIOS_ESTRITO = [
    "padrao_arquitetural",
    "artefato_aberto",
    "invalida_pratica",
    "vulnerabilidade",
    "tecnica_de_avaliacao",
]
# Excludente: nao coexiste com criterio de estrito (ver estagio_b.validar).
CRITERIO_ACESSO_INTERNO = "exige_acesso_interno"

CRITERIOS_AMPLO = [
    "benchmark",
    "panorama",
    "framework_conceitual",
    "principio_sem_o_como",
    "exige_acesso_interno",
]
CRITERIOS_VEREDITO = [*CRITERIOS_ESTRITO, *CRITERIOS_AMPLO]

# O que quase venceu numa decisao de fronteira: regra de descarte ou criterio,
# de lado diferente do veredito. `lado` e a funcao que diz de que lado cada
# rotulo esta - a mesma para o veredito e para a contraparte.
CONTRAPARTES_FRONTEIRA = [*REGRAS_FORA, *CRITERIOS_VEREDITO]


def lado(rotulo: str) -> Optional[str]:
    """Veredito para o qual um rotulo (regra ou criterio) puxa; None se desconhecido."""
    if rotulo in REGRAS_FORA:
        return "fora"
    if rotulo in CRITERIOS_ESTRITO:
        return "estrito"
    if rotulo in CRITERIOS_AMPLO:
        return "amplo"
    return None


def veredito_dos_criterios(criterios: Sequence[str]) -> Optional[str]:
    """O veredito que a lista de criterios implica; None para lista vazia."""
    if not criterios:
        return None
    return "estrito" if any(c in CRITERIOS_ESTRITO for c in criterios) else "amplo"

# Piso da justificativa, nos dois estagios. Existe porque teto sem piso deixa
# passar resposta degenerada - na migracao da issue #3 o paper 2608.06867
# devolveu literalmente "..." e o painel exibiria os tres pontos sob "POR QUE
# ESTRITO" (a defesa de `justificativa_exibivel` so troca texto vazio, e "..."
# nao e vazio). 80 nao corta nada legitimo: as 317 justificativas do corpus
# migrado em 2026-09-04 tem minimo de 104 caracteres e media de 200.
PISO_JUSTIFICATIVA = 80

# Segundo piso, em letras: o de caracteres sozinho aceitaria 80 sinais de
# pontuacao. Nao e um segundo palpite sobre tamanho, e um detector de
# preenchimento - as 317 justificativas do corpus tem no minimo 0,76 letra por
# caractere (a pior delas: 82 letras em 104 caracteres) e um enfileiramento de
# pontuacao tem zero, entao 0,50 passa longe dos dois lados. Numero proprio, e
# nao `PISO_JUSTIFICATIVA // 2`, para que mexer num nao mova o outro em silencio.
PISO_LETRAS_JUSTIFICATIVA = 40

# Teto da secao 4.4. Declarado no schema e conferido em codigo so para virar
# aviso: ver `validar_justificativa` para por que estourar o teto nao derruba o
# paper como estourar o piso derruba.
TETO_JUSTIFICATIVA = 300


def schema_estagio_a(areas: Sequence[str], topicos: Sequence[str]) -> dict[str, Any]:
    areas = list(areas)
    topicos = list(topicos)
    if not areas or not topicos:
        raise ValueError(
            "vocabulario vazio: rode `hfpapers taxonomia carregar`"
        )
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "veredito_preliminar",
            "regra_fora",
            "justificativa",
            "area_primaria",
            "areas_secundarias",
            "topicos",
            "candidato_novo_rotulo",
        ],
        "properties": {
            "veredito_preliminar": {"type": "string", "enum": ["fora", "candidato"]},
            # So as regras de conteudo: `portabilidade_reprovada` exige o teste,
            # que e do Estagio B.
            "regra_fora": {"type": ["string", "null"], "enum": [*REGRAS_FORA_CONTEUDO, None]},
            "justificativa": {
                "type": "string",
                "minLength": PISO_JUSTIFICATIVA,
                "maxLength": TETO_JUSTIFICATIVA,
            },
            "area_primaria": {"type": "string", "enum": areas},
            "areas_secundarias": {
                "type": "array",
                "maxItems": 3,
                "items": {"type": "string", "enum": areas},
            },
            "topicos": {
                "type": "array",
                "minItems": 1,
                "maxItems": 5,
                "items": {"type": "string", "enum": topicos},
            },
            "candidato_novo_rotulo": {
                "type": ["object", "null"],
                "additionalProperties": False,
                "required": ["rotulo", "tipo", "definicao"],
                "properties": {
                    "rotulo": {"type": "string"},
                    "tipo": {"type": "string", "enum": ["area", "topico"]},
                    "definicao": {"type": "string"},
                },
            },
        },
    }


SCHEMA_ESTAGIO_B: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "tem_artefato_nomeado",
        "padrao_extraido",
        "teste_portabilidade",
        "criterios_veredito",
        "veredito",
        "regra_fora",
        "justificativa_veredito",
        "decisao_fronteira",
        "fronteira_contraparte",
        "ficha",
    ],
    "properties": {
        "tem_artefato_nomeado": {"type": "boolean"},
        "padrao_extraido": {
            "type": ["object", "null"],
            "additionalProperties": False,
            "required": ["nome", "mecanismo"],
            "properties": {
                "nome": {"type": "string", "maxLength": 80},
                "mecanismo": {"type": "string"},
            },
        },
        "teste_portabilidade": {
            "type": ["object", "null"],
            "additionalProperties": False,
            "required": ["depende_do_nome_proprio", "colapsa_em_generalidade", "aprovado"],
            "properties": {
                "depende_do_nome_proprio": {"type": "boolean"},
                "colapsa_em_generalidade": {"type": "boolean"},
                "aprovado": {"type": "boolean"},
            },
        },
        # Sem `minItems`: o piso e condicional (>= 1 so quando aprovado, vazio
        # quando `fora`) e o JSON Schema estrito do provedor nao expressa isso.
        # Quem cobra e `estagio_b.validar`.
        "criterios_veredito": {
            "type": "array",
            "items": {"type": "string", "enum": CRITERIOS_VEREDITO},
        },
        "veredito": {"type": "string", "enum": VEREDITOS},
        "regra_fora": {"type": ["string", "null"], "enum": [*REGRAS_FORA, None]},
        "justificativa_veredito": {
            "type": "string",
            "minLength": PISO_JUSTIFICATIVA,
            "maxLength": TETO_JUSTIFICATIVA,
        },
        "decisao_fronteira": {"type": "boolean"},
        "fronteira_contraparte": {
            "type": ["string", "null"],
            "enum": [*CONTRAPARTES_FRONTEIRA, None],
        },
        "ficha": {
            "type": ["object", "null"],
            "additionalProperties": False,
            "required": ["achado", "implicacao_pratica", "exemplo_concreto", "ressalva"],
            "properties": {
                "achado": {"type": "string"},
                "implicacao_pratica": {"type": "string"},
                "exemplo_concreto": {"type": "string"},
                "ressalva": {"type": "string"},
            },
        },
    },
}


def response_format(nome: str, schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {"name": nome, "strict": True, "schema": schema},
    }


# ── rede em codigo para o piso ──────────────────────────────────────────────


def validar_justificativa(texto: Any, campo: str) -> None:
    """Confere o tamanho util de `campo` e levanta `ErroValidacao` se fugir dele.

    `minLength` sob `strict: true` nao e cumprido por todo provedor, entao o
    piso e cobrado aqui. Quem chama sao `estagio_a.validar` e
    `estagio_b.validar`, e o `ErroValidacao` volta ao modelo pelo mesmo caminho
    de retentativa das outras regras da secao 4.4; esgotadas as tentativas vira
    `ErroLLM` e o paper cai em pendencia, que e o desfecho certo - justificativa
    degenerada e falha de geracao, nao veredito.

    **O teto nao e cobrado do mesmo jeito**, e a assimetria e deliberada.
    `_validar_tamanho` da migracao da issue #3 (commit `fa840aa`) estourava nos
    dois limites, mas la o custo de estourar era uma linha nao migrada e uma
    entrada no relatorio de diff. Aqui o custo e outro: `ErroLLM` no Estagio A
    faz `classificacao` pular o paper, que fica sem area e sem topico - o buraco
    que a issue #3 existiu para tapar - e ainda marca a rodada como `parcial`.
    Perder a taxonomia de um paper bem classificado por 5 caracteres a mais e
    pior do que gravar 305 caracteres numa coluna `TEXT` sem constraint, que o
    painel renderiza sem reclamar. Justificativa curta demais e falha de
    conteudo; comprida demais e cosmetica. O teto continua declarado no schema e
    passa a ser registrado no log quando violado, para que um provedor mal
    comportado apareca sem custar papers.

    O tamanho e medido depois do `strip()`, entao `"   "` conta como zero. A
    segunda checagem existe porque a primeira, sozinha, aceitaria 80 caracteres
    de pontuacao ou de espaco interno: exige um minimo de letras muito abaixo do
    que qualquer frase real tem (uma justificativa de 80 caracteres em portugues
    passa dos 60 letras) e muito acima do que um preenchimento de pontuacao
    alcanca (zero).
    """
    limpo = texto.strip() if isinstance(texto, str) else ""
    if len(limpo) < PISO_JUSTIFICATIVA:
        raise ErroValidacao(
            f"{campo} tem {len(limpo)} caracteres uteis e o piso e "
            f"{PISO_JUSTIFICATIVA}: escreva uma ou duas frases dizendo em que a "
            "decisao se apoiou"
        )
    letras = sum(1 for c in limpo if c.isalpha())
    if letras < PISO_LETRAS_JUSTIFICATIVA:
        raise ErroValidacao(
            f"{campo} tem {letras} letras em {len(limpo)} caracteres: nao e uma "
            "frase, e preenchimento"
        )
    if len(limpo) > TETO_JUSTIFICATIVA:
        log.warning(
            "%s veio com %d caracteres, acima do teto de %d declarado no schema",
            campo,
            len(limpo),
            TETO_JUSTIFICATIVA,
        )
