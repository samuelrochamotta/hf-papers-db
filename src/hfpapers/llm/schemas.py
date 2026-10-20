"""JSON Schemas dos dois estagios (secoes 4.3 e 4.4 do PROMPT).

Os `enum` de area, sub-area e vertente do Estagio A sao injetados em tempo de
execucao a partir do banco. E isso que impede a LLM de inventar rotulo e
fragmentar os filtros do Power BI.

No Estagio B a **ordem das propriedades e normativa**: ela reproduz a ordem do
raciocinio (a natureza e o padrao vem antes do pre-requisito, e a justificativa
depois de tudo que ela explica). Nao reordene.

O piso da justificativa mora aqui em duas formas - `minLength` no schema e
`validar_justificativa` em codigo. Ficam lado a lado de proposito: a declaracao
sozinha nao e cumprida por todo provedor, e separar as duas em modulos
diferentes seria o convite para elas divergirem. O teto tem so a declaracao e um
aviso no log; `validar_justificativa` explica por que ele nao derruba o paper.
"""

from __future__ import annotations

from typing import Any, Sequence

from ..log import logger
from ..taxonomia import EIXOS, MAX_VERTENTES_POR_PAPER
from .cliente import ErroValidacao

log = logger("llm")

# Regras de descarte, na ordem de teste (secao 1 da spec
# `docs/specs/natureza-prerequisito.md`). Todo `fora` tem exatamente uma; a
# primeira que bate basta. Sao as mesmas nos dois estagios: o Estagio B so as
# repete como rede de seguranca. `treino_ou_postreino`,
# `relatorio_tecnico_de_modelo` e `portabilidade_reprovada` sairam no ADR 004 -
# a primeira escondia midia, robotica e nao-LLM atras de si por ser testada
# antes delas.
REGRAS_FORA = [
    "geracao_de_midia",
    "percepcao_robotica_embodied",
    "fora_de_escopo",
]

VEREDITOS = ["fora", "aprovado"]

# Que tipo de afirmacao o paper faz. O *que* ele faz e a vertente; por isso
# benchmark e `proposta` (Medir ja diz que e medicao) e artefato nao e natureza
# (e condicao de adocao, ver `ARTEFATO_STATUS`).
NATUREZAS = ["proposta", "achado_empirico", "teoria", "panorama"]
NATUREZAS_SEM_ADOCAO = ("teoria", "panorama")

# Escada de capacidade: cada degrau implica os anteriores. A ordem desta lista
# e a ordem de `dim_prerequisito` (teste em `test_vocabulario_v2`), e e ela que
# o painel e o Power BI usam para ordenar. `sem_acao` e valor explicito, e nao
# NULL, para que nenhum filtro precise tratar nulo.
PREREQUISITOS = ["nenhum", "implementar", "acesso_interno", "treino", "sem_acao"]
SEM_ACAO = "sem_acao"

# So perguntado quando ha evidencia externa de artefato (`vw_artefato`); sem
# ela o codigo sobrescreve para NULL, sem gastar retentativa.
ARTEFATO_STATUS = ["liberado", "prometido"]

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


def schema_estagio_a(
    areas: Sequence[str], subareas: Sequence[str], vertentes: Sequence[str]
) -> dict[str, Any]:
    """O contrato da triagem, com o vocabulario vigente injetado nos `enum`.

    **A sub-area entra num enum plano, com todas as filhas de todas as areas.**
    JSON Schema so expressaria "sub-area valida *dado* que a area e X" com um
    `oneOf` de um ramo por area, e nem todo provedor trata isso sob
    `strict: true`. O parentesco e cobrado depois, na persistencia
    (`taxonomia.aplicar_classificacao`), onde o par que nao fecha e ignorado sem
    derrubar a classificacao do paper.

    O teto de duas vertentes e declarado aqui e **cobrado de novo** na mesma
    persistencia: `maxItems` sob `strict: true` nao e cumprido por todo provedor,
    e o numero vem de `taxonomia` para que os dois lugares nao possam divergir.
    """
    areas = list(areas)
    subareas = list(subareas)
    vertentes = list(vertentes)
    if not areas or not subareas or not vertentes:
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
            "subarea_primaria",
            "area_secundaria",
            "subarea_secundaria",
            "vertentes",
            "nao_coube",
        ],
        "properties": {
            "veredito_preliminar": {"type": "string", "enum": ["fora", "candidato"]},
            "regra_fora": {"type": ["string", "null"], "enum": [*REGRAS_FORA, None]},
            "justificativa": {
                "type": "string",
                "minLength": PISO_JUSTIFICATIVA,
                "maxLength": TETO_JUSTIFICATIVA,
            },
            "area_primaria": {"type": "string", "enum": areas},
            "subarea_primaria": {"type": "string", "enum": subareas},
            # O par secundario e nulo na maioria dos papers, e o `null` no enum
            # e o que torna isso uma resposta e nao uma falha de validacao.
            "area_secundaria": {"type": ["string", "null"], "enum": [*areas, None]},
            "subarea_secundaria": {"type": ["string", "null"], "enum": [*subareas, None]},
            # Ordenada, a dominante primeiro: e a posicao no array que vira a
            # `ordem` da ponte, e o prompt diz isso em prosa.
            "vertentes": {
                "type": "array",
                "minItems": 1,
                "maxItems": MAX_VERTENTES_POR_PAPER,
                "items": {"type": "string", "enum": vertentes},
            },
            # Uma constatacao, e nao um rotulo: o campo antigo pedia um nome
            # inventado e o que se acumulou foram sinonimos. Aqui o modelo diz
            # em qual dos tres eixos o encaixe falhou e por que - quem promove
            # rotulo e a revisao da grade, por quorum, nunca a classificacao.
            # Nulo e a resposta comum, como no par secundario. Sem `minLength`
            # e sem rede em `validar`, ao contrario da justificativa do
            # veredito: piso aqui viraria `ErroValidacao` e, esgotada a
            # retentativa, deixaria pendente um paper que o modelo classificou
            # bem - a declaracao de nao-encaixe nao pode custar a atribuicao.
            # Justificativa vazia e descartada na persistencia, com aviso.
            "nao_coube": {
                "type": ["object", "null"],
                "additionalProperties": False,
                "required": ["eixo", "justificativa"],
                "properties": {
                    "eixo": {"type": "string", "enum": list(EIXOS)},
                    "justificativa": {"type": "string"},
                },
            },
        },
    }


_TEXTO_OU_NULO = {"type": ["string", "null"]}

SCHEMA_ESTAGIO_B: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "regra_fora",
        "natureza",
        "padrao_extraido",
        "prerequisito",
        "pratica_contradita",
        "falta_o_como",
        "artefato_status",
        "justificativa",
        "ficha",
    ],
    "properties": {
        # Rede de seguranca: as mesmas tres regras do Estagio A. Nao nula, todo
        # o resto e nulo - quem cobra e `estagio_b.validar`.
        "regra_fora": {"type": ["string", "null"], "enum": [*REGRAS_FORA, None]},
        "natureza": {"type": ["string", "null"], "enum": [*NATUREZAS, None]},
        # Obrigatorio so para `proposta`; o condicional nao cabe no JSON Schema
        # estrito e e cobrado em `estagio_b.validar`.
        "padrao_extraido": {
            "type": ["object", "null"],
            "additionalProperties": False,
            "required": ["nome", "mecanismo"],
            "properties": {
                "nome": {"type": "string", "maxLength": 80},
                "mecanismo": {"type": "string"},
            },
        },
        "prerequisito": {"type": ["string", "null"], "enum": [*PREREQUISITOS, None]},
        # Textos, e nao booleanos: "nomeie a pratica" passa a ser cobrado pela
        # forma da resposta. Os booleanos derivam deles no codigo.
        "pratica_contradita": _TEXTO_OU_NULO,
        "falta_o_como": _TEXTO_OU_NULO,
        "artefato_status": {"type": ["string", "null"], "enum": [*ARTEFATO_STATUS, None]},
        "justificativa": {
            "type": "string",
            "minLength": PISO_JUSTIFICATIVA,
            "maxLength": TETO_JUSTIFICATIVA,
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
    faz `classificacao` pular o paper, que fica sem area e sem vertente - o buraco
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
