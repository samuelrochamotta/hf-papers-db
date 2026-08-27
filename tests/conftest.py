import json
from pathlib import Path

import pytest

from hfpapers import db
from hfpapers.config import Config

FIXTURES = Path(__file__).parent / "fixtures"
SEED = Path(__file__).parents[1] / "seed"


@pytest.fixture()
def daily_bruto() -> list[dict]:
    return json.loads((FIXTURES / "daily_papers_2026-08-25.json").read_text(encoding="utf-8"))


@pytest.fixture()
def paper_bruto() -> dict:
    return json.loads((FIXTURES / "paper_2608.23552.json").read_text(encoding="utf-8"))


@pytest.fixture()
def conn(tmp_path):
    c = db.conectar(tmp_path / "t.db")
    yield c
    c.close()


@pytest.fixture()
def cfg(tmp_path) -> Config:
    """Config isolada: banco e marts no tmp, prompts reais do repo."""
    raiz = Path(__file__).parents[1]
    c = Config()
    c.raiz = raiz
    c.paths.banco = str(tmp_path / "hfpapers.db")
    c.paths.marts = str(tmp_path / "marts")
    c.paths.relatorios = str(tmp_path / "relatorios")
    c.paths.logs = str(tmp_path / "logs")
    c.llm.estagio_a.modelo = "modelo/teste-a"
    c.llm.estagio_b.modelo = "modelo/teste-b"
    c.llm.retry.backoff_inicial_s = 0     # sem espera artificial nos testes
    return c


@pytest.fixture()
def seed_dir() -> Path:
    return SEED
