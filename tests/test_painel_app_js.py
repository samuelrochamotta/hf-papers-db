"""A suite de `painel_app.js`, rodada pelo `node --test`, entra no pytest.

O painel tem duas metades: `gerar_painel.py`, que monta `DADOS`, e
`painel_app.js`, que o le no navegador. Toda a logica de recorte - o que cada
filtro esconde e o que cada contagem afirma - mora na segunda, e ate aqui nao
tinha teste nenhum: os arquivos `test_painel_*.py` travam o contrato de dados,
nao o comportamento.

Os casos ficam em `tests/js/` porque sao JavaScript de verdade, exercitando o
proprio arquivo que vai para o navegador (ver `tests/js/dom_painel.mjs`). Este
modulo so os traz para dentro da porta unica do projeto, que e o `pytest`.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).parents[1]
CASOS = sorted((RAIZ / "tests" / "js").glob("*.test.mjs"))


@pytest.mark.skipif(shutil.which("node") is None, reason="node nao instalado")
def test_suite_js_do_painel():
    assert CASOS, "nenhum caso em tests/js/*.test.mjs"
    r = subprocess.run(
        ["node", "--test", *[str(c) for c in CASOS]],
        cwd=RAIZ, capture_output=True, text=True, check=False,
    )
    assert r.returncode == 0, r.stdout + r.stderr
