"""JSON Schemas dos dois estagios (secoes 4.3 e 4.4 do PROMPT).

Os `enum` de area e topico do Estagio A sao injetados em tempo de execucao a
partir do banco. E isso que impede a LLM de inventar rotulo e fragmentar os
filtros do Power BI.

No Estagio B a **ordem das propriedades e normativa**: ela reproduz a ordem do
raciocinio (o padrao e escrito e testado antes de o veredito ser decidido). Nao
reordene.
"""

from __future__ import annotations

from typing import Any, Sequence

REGRAS_FORA = [
    "treino_ou_postreino",
    "geracao_de_midia",
    "percepcao_robotica_embodied",
    "relatorio_tecnico_de_modelo",
]

VEREDITOS = ["fora", "amplo", "estrito"]


def schema_estagio_a(areas: Sequence[str], topicos: Sequence[str]) -> dict[str, Any]:
    areas = list(areas)
    topicos = list(topicos)
    if not areas or not topicos:
        raise ValueError("vocabulario vazio: rode o backfill ou semeie dim_area/dim_topico")
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
            "regra_fora": {"type": ["string", "null"], "enum": [*REGRAS_FORA, None]},
            "justificativa": {"type": "string", "maxLength": 300},
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
        "veredito",
        "justificativa_veredito",
        "decisao_fronteira",
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
        "veredito": {"type": "string", "enum": VEREDITOS},
        "justificativa_veredito": {"type": "string"},
        "decisao_fronteira": {"type": "boolean"},
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
