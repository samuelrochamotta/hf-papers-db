"""Carregamento dos prompts versionados em `prompts/`.

As regras de negocio vivem em arquivo, nao em f-string no meio do codigo: elas
sao o ativo do projeto e precisam de historico no git.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from ..config import Config, config


@lru_cache(maxsize=8)
def _ler(caminho: str) -> str:
    return Path(caminho).read_text(encoding="utf-8")


def carregar(nome: str, cfg: Optional[Config] = None) -> str:
    cfg = cfg or config()
    return _ler(str(cfg.dir_prompts / f"{nome}.md"))


def preencher(template: str, **campos: str) -> str:
    """Substituicao literal de `{CHAVE}`.

    Nao usa `str.format`: os prompts tem chaves de JSON no texto e `format`
    trataria `{nome}` como campo.
    """
    texto = template
    for chave, valor in campos.items():
        texto = texto.replace("{" + chave + "}", valor)
    return texto
