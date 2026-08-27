"""Logging: legivel no console, JSON em arquivo.

A chave da API nunca e logada. Como garantia mecanica, `_Redator` corta qualquer
token que se pareca com uma chave do OpenRouter antes de a linha ser escrita.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Optional

_PADROES_SEGREDO = [
    re.compile(r"sk-or-v1-[A-Za-z0-9\-_]{8,}"),
    re.compile(r"sk-[A-Za-z0-9\-_]{20,}"),
    re.compile(r"(?i)(api[_-]?key\"?\s*[:=]\s*\"?)([A-Za-z0-9\-_]{8,})"),
]


def redigir(texto: str) -> str:
    for p in _PADROES_SEGREDO:
        if p.groups == 2:
            texto = p.sub(r"\1***", texto)
        else:
            texto = p.sub("***", texto)
    return texto


class _Redator(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redigir(record.msg)
        if record.args:
            record.args = tuple(
                redigir(a) if isinstance(a, str) else a for a in record.args
            )
        return True


class _FormatoJSON(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "nivel": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for k, v in getattr(record, "extra_campos", {}).items():
            payload[k] = v
        if record.exc_info:
            payload["excecao"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class _FormatoConsole(logging.Formatter):
    def __init__(self) -> None:
        super().__init__("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S")


_CONFIGURADO = False


def configurar(
    dir_logs: Optional[Path] = None, *, nivel: str = "INFO", arquivo: str = "hfpapers.jsonl"
) -> None:
    global _CONFIGURADO
    if _CONFIGURADO:
        return
    nivel = os.environ.get("HFPAPERS_LOG_LEVEL", nivel).upper()
    raiz = logging.getLogger("hfpapers")
    raiz.setLevel(nivel)
    raiz.propagate = False

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(_FormatoConsole())
    console.addFilter(_Redator())
    raiz.addHandler(console)

    if dir_logs is not None:
        dir_logs.mkdir(parents=True, exist_ok=True)
        arq = logging.FileHandler(dir_logs / arquivo, encoding="utf-8")
        arq.setFormatter(_FormatoJSON())
        arq.addFilter(_Redator())
        raiz.addHandler(arq)

    _CONFIGURADO = True


def logger(nome: str) -> logging.Logger:
    return logging.getLogger(f"hfpapers.{nome}")
