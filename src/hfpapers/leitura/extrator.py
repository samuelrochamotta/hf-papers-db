"""Extracao estruturada do texto completo com o Claude Haiku 5.5.

Regra que organiza o modulo: o modelo so copia e escolhe. Ele copia trechos
literais e numeros de tabela e escolhe valores de listas fechadas. Tudo que e
conta (delta contra o rival, solidez, esforco, eixos do radar) e feito depois,
por codigo, em `derivar.py`.

E o codigo confere a copia. Cada `trecho` e procurado no texto que o modelo
recebeu e cada `valor` de tabela precisa existir como numero nesse texto. O
resultado fica marcado no proprio JSON (`_ok`), e o painel so desenha numero
conferido. Isso transforma a alucinacao em dado faltante, que e visivel, em vez
de dado errado, que nao e.

A chamada passa pelo OpenRouter, com o mesmo `ClienteLLM` dos estagios A e B
e saida estruturada (`response_format` json_schema estrito, que o catalogo
anuncia para o Haiku 5.5): o JSON volta valido contra o esquema, e o cliente
cuida de retentativa, prazo, resposta cortada e custo pela tabela viva.
"""

from __future__ import annotations

import copy
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config import Config, config
from ..log import logger
from .texto import Conferidor, TextoPaper

log = logger("leitura")

# Palavras-chave de JSON Schema que a saida estruturada da Anthropic nao aceita
# (o OpenRouter repassa o esquema). Quem remove somos nos, e quem confere os
# limites depois e `validar_limites`.
_NAO_SUPORTADAS = {
    "maxLength",
    "minLength",
    "pattern",
    "maxItems",
    "minItems",
    "uniqueItems",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "minProperties",
    "maxProperties",
    "$schema",
    "$id",
    "title",
}


def carregar_esquema(cfg: Config | None = None) -> dict:
    cfg = cfg or config()
    caminho = cfg.dir_prompts / "leitura" / f"esquema-{cfg.leitura.versao_esquema}.json"
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


def instrucoes(esquema: dict) -> str:
    return (
        "Voce extrai dados de papers de IA para um banco de analise. "
        "Responda so com o objeto JSON pedido.\n\n" + esquema.get("description", "")
    )


def esquema_api(esquema: dict) -> dict:
    """Copia do esquema no formato que a saida estruturada aceita."""

    def limpar(no: Any) -> Any:
        if isinstance(no, dict):
            out = {}
            for k, v in no.items():
                if k in _NAO_SUPORTADAS:
                    continue
                out[k] = limpar(v)
            tipo = out.get("type")
            # ["string", "null"] com enum vira anyOf: o enum fica so no ramo string.
            if isinstance(tipo, list) and "null" in tipo:
                outros = [t for t in tipo if t != "null"]
                ramo = {
                    k: v
                    for k, v in out.items()
                    if k not in ("type", "enum", "description")
                }
                ramo["type"] = outros[0] if len(outros) == 1 else outros
                if "enum" in out:
                    ramo["enum"] = [e for e in out["enum"] if e is not None]
                novo = {"anyOf": [ramo, {"type": "null"}]}
                if "description" in out:
                    novo["description"] = out["description"]
                return novo
            return out
        if isinstance(no, list):
            return [limpar(x) for x in no]
        return no

    out = limpar(copy.deepcopy(esquema))
    out.pop("description", None)  # vai no system, nao precisa repetir no esquema
    return out


def montar_prompt(tp: TextoPaper, meta: dict) -> str:
    cab = [f"ID do arXiv: {tp.arxiv_id}", f"Titulo: {meta.get('titulo') or ''}"]
    if tp.fonte == "abstract":
        cab.append(
            "ATENCAO: so o abstract esta disponivel; leitura.fonte_texto='abstract', "
            "cobertura='parcial'."
        )
    elif not tp.chegou_ao_fim:
        cab.append(
            f"ATENCAO: o texto foi cortado depois da secao '{tp.cortado_em}'; "
            "leitura.cobertura='parcial'."
        )
    else:
        cab.append(
            "O texto vai do inicio ao fim do corpo (as referencias foram removidas): "
            "leitura.cobertura='completa'."
        )
    return "\n".join(cab) + "\n\n<paper>\n" + tp.texto + "\n</paper>"


# ── conferencia ─────────────────────────────────────────────────────────────


def conferir(dados: dict, tp: TextoPaper) -> dict:
    """Marca `_ok` em cada trecho e em cada valor de tabela; devolve contagens."""
    c = Conferidor(tp.texto)
    tr_total = tr_ok = num_total = num_ok = 0

    def marcar_trecho(item: dict, chave: str = "trecho") -> None:
        nonlocal tr_total, tr_ok
        ok = c.trecho(item.get(chave))
        if ok is not None:
            tr_total += 1
            tr_ok += int(ok)
        item["_ok"] = ok

    for chave in ("entrega", "camada"):
        if isinstance(dados.get(chave), dict):
            marcar_trecho(dados[chave])
    for lista in (
        "entidades",
        "relacoes",
        "efeitos_custo",
        "hardware",
        "compute_declarado",
        "escala",
        "alegacoes",
        "ressalvas",
        "artefatos",
    ):
        for item in dados.get(lista) or []:
            if isinstance(item, dict):
                marcar_trecho(item)
    if isinstance(dados.get("estatistica"), dict):
        marcar_trecho(dados["estatistica"])
    for r in dados.get("resultados") or []:
        for linha in r.get("linhas") or []:
            ok = c.numero(linha.get("valor"))
            if ok is not None:
                num_total += 1
                num_ok += int(ok)
            linha["_ok"] = ok
    return {
        "trechos": tr_total,
        "trechos_ok": tr_ok,
        "numeros": num_total,
        "numeros_ok": num_ok,
    }


def fixar_leitura(dados: dict, tp: TextoPaper) -> None:
    """A cobertura e fato do codigo, nao opiniao do modelo."""
    lt = dados.setdefault("leitura", {})
    lt["fonte_texto"] = tp.fonte
    lt["cobertura"] = (
        "completa" if (tp.fonte == "html" and tp.chegou_ao_fim) else "parcial"
    )
    if tp.cortado_em:
        lt["termina_em"] = tp.cortado_em
    dados["id"] = tp.arxiv_id


# ── chamada ─────────────────────────────────────────────────────────────────


@dataclass
class Leitura:
    arxiv_id: str
    dados: dict
    conferencia: dict
    modelo: str
    tokens_entrada: int = 0
    tokens_saida: int = 0
    custo_usd: float = 0.0
    latencia_ms: int = 0
    caracteres: int = 0
    avisos: list[str] = field(default_factory=list)


def config_leitura(cfg: Config) -> Config:
    """Copia do config com o prazo da leitura no lugar do prazo dos estagios."""
    lc = cfg.leitura
    llm = cfg.llm.model_copy(
        update={
            "prazo_total_s": lc.prazo_s,
            "timeout_s": max(cfg.llm.timeout_s, lc.prazo_s),
        }
    )
    return cfg.model_copy(update={"llm": llm})


def cliente_llm(
    cfg: Config | None = None,
    *,
    conn: sqlite3.Connection | None = None,
    run_id: str = "sem-run",
):
    """O mesmo cliente do OpenRouter dos estagios A e B: retentativa, prazo,
    preco da tabela viva e linha em `log_llm` por tentativa."""
    from ..llm.cliente import ClienteLLM

    return ClienteLLM(config_leitura(cfg or config()), conn=conn, run_id=run_id)


def formato_resposta(esquema: dict) -> dict:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "leitura_paper",
            "strict": True,
            "schema": esquema_api(esquema),
        },
    }


def extrair(
    tp: TextoPaper,
    meta: dict,
    *,
    cliente: Any,
    cfg: Config | None = None,
    esquema: dict | None = None,
) -> Leitura:
    """`cliente` e um `ClienteLLM` (ou um duble com o mesmo `chamar`)."""
    cfg = cfg or config()
    lc = cfg.leitura
    esquema = esquema or carregar_esquema(cfg)
    r = cliente.chamar(
        etapa="leitura",
        modelo=lc.modelo,
        prompt=montar_prompt(tp, meta),
        sistema=instrucoes(esquema),
        response_format=formato_resposta(esquema),
        max_tokens=lc.max_tokens,
        esforco_raciocinio=lc.esforco,
        paper_id=tp.arxiv_id,
    )
    dados = r.dados
    fixar_leitura(dados, tp)
    conf = conferir(dados, tp)
    avisos = validar_limites(dados, esquema)
    return Leitura(
        tp.arxiv_id,
        dados,
        conf,
        r.modelo,
        r.uso.tokens_entrada,
        r.uso.tokens_saida,
        r.uso.custo_usd,
        r.latencia_ms,
        tp.caracteres,
        avisos,
    )


def validar_limites(dados: dict, esquema: dict) -> list[str]:
    """Os limites que saem do esquema enviado (tamanho de lista e de texto)
    voltam aqui como avisos. Nao rejeitam: um trecho de 31 palavras e copia
    longa, nao dado errado."""
    avisos: list[str] = []

    def andar(no: Any, sch: dict, caminho: str) -> None:
        if not isinstance(sch, dict):
            return
        if isinstance(no, str) and sch.get("maxLength") and len(no) > sch["maxLength"]:
            avisos.append(
                f"{caminho}: texto com {len(no)} caracteres (teto {sch['maxLength']})"
            )
        if isinstance(no, list):
            if sch.get("maxItems") and len(no) > sch["maxItems"]:
                avisos.append(f"{caminho}: {len(no)} itens (teto {sch['maxItems']})")
            if sch.get("uniqueItems") and len(
                {json.dumps(x, sort_keys=True) for x in no}
            ) < len(no):
                avisos.append(f"{caminho}: itens repetidos")
            for i, x in enumerate(no):
                andar(x, _resolver(sch.get("items", {}), esquema), f"{caminho}[{i}]")
        if isinstance(no, dict):
            for k, v in no.items():
                sub = (sch.get("properties") or {}).get(k)
                if sub is not None:
                    andar(
                        v, _resolver(sub, esquema), f"{caminho}.{k}" if caminho else k
                    )

    andar(dados, esquema, "")
    return avisos


def _resolver(sch: dict, raiz: dict) -> dict:
    ref = sch.get("$ref") if isinstance(sch, dict) else None
    if ref and ref.startswith("#/$defs/"):
        return raiz.get("$defs", {}).get(ref.split("/")[-1], {})
    return sch
