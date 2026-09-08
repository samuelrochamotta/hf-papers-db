"""Configuracao: config.yaml (parametros) + .env (segredos).

Regra: a chave da API vive so no ambiente e nunca aparece em log nem em repr.
Por isso `Ambiente.openrouter_api_key` e um SecretStr.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ = Path(__file__).resolve().parents[2]


# ── Segredos ────────────────────────────────────────────────────────────────


class Ambiente(BaseSettings):
    """Variaveis de ambiente. Carregadas de .env na raiz do projeto."""

    model_config = SettingsConfigDict(
        env_file=str(RAIZ / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openrouter_api_key: Optional[SecretStr] = Field(default=None)

    def chave_openrouter(self) -> Optional[str]:
        return self.openrouter_api_key.get_secret_value() if self.openrouter_api_key else None


# ── config.yaml ─────────────────────────────────────────────────────────────


class Paths(BaseModel):
    banco: str = "data/hfpapers.db"
    marts: str = "marts"
    prompts: str = "prompts"
    logs: str = "logs"
    relatorios: str = "relatorios"


class HF(BaseModel):
    base_url: str = "https://huggingface.co"
    req_por_segundo: float = 5
    timeout_s: float = 30
    tentativas: int = 4
    backoff_inicial_s: float = 1


class EstagioLLM(BaseModel):
    modelo: str = "PREENCHER"
    temperatura: float = 0.0
    max_tokens: int = 1200
    # Quanto o modelo raciocina antes de responder, quando ele oferece o botao.
    # `None` nao manda o campo: modelo que nao anuncia `reasoning` sai da lista
    # de provedores sob `require_parameters` e a chamada volta 404 - a mesma
    # armadilha do `temperature` (issue #1).
    esforco_raciocinio: Optional[str] = None

    @property
    def configurado(self) -> bool:
        return bool(self.modelo) and self.modelo != "PREENCHER"


class ProviderLLM(BaseModel):
    require_parameters: bool = True


class RetryLLM(BaseModel):
    tentativas: int = 3
    backoff_inicial_s: float = 2


class LLM(BaseModel):
    base_url: str = "https://openrouter.ai/api/v1"
    referer: str = "https://github.com/samuelrochamotta/hf-papers-db"
    titulo_app: str = "hf-papers-db"
    timeout_s: float = 180
    # Quantas chamadas ao OpenRouter podem estar no ar ao mesmo tempo no
    # estagio 3. O padrao e 1 - sequencial, o caminho de sempre - porque a
    # rodada diaria classifica ~30 papers e nao ganha nada com paralelismo,
    # enquanto a rajada aumenta a chance do 429/404 da issue #1. Quem precisa
    # de concorrencia e a reclassificacao total, que a pede na linha de
    # comando (`reclassificar --concorrencia N`). Teto em
    # `classificacao.CONCORRENCIA_MAXIMA`.
    concorrencia: int = 1
    estagio_a: EstagioLLM = EstagioLLM()
    estagio_b: EstagioLLM = EstagioLLM(temperatura=0.2, max_tokens=3000)
    provider: ProviderLLM = ProviderLLM()
    retry: RetryLLM = RetryLLM()


class Refresh(BaseModel):
    janela_quente_dias: int = 30
    janela_morna_dias: int = 90
    enriquecimento_semanal: bool = True


class Guardrails(BaseModel):
    taxa_fora_min: float = 0.50
    taxa_fora_faixa_normal: tuple[float, float] = (0.60, 0.80)
    aprovados_faixa_normal: tuple[int, int] = (4, 9)
    aprovados_volume_alto: int = 12
    coletados_min_dia_util: int = 15


class Export(BaseModel):
    csv: bool = False
    faixas_upvotes: list[int] = [1, 10, 50, 100]


class Config(BaseModel):
    paths: Paths = Paths()
    hf: HF = HF()
    llm: LLM = LLM()
    refresh: Refresh = Refresh()
    guardrails: Guardrails = Guardrails()
    export: Export = Export()

    raiz: Path = RAIZ

    # ── caminhos absolutos derivados ────────────────────────────────────────

    def _abs(self, valor: str) -> Path:
        p = Path(valor)
        return p if p.is_absolute() else self.raiz / p

    @property
    def caminho_banco(self) -> Path:
        return self._abs(self.paths.banco)

    @property
    def dir_marts(self) -> Path:
        return self._abs(self.paths.marts)

    @property
    def dir_prompts(self) -> Path:
        return self._abs(self.paths.prompts)

    @property
    def dir_logs(self) -> Path:
        return self._abs(self.paths.logs)

    @property
    def dir_relatorios(self) -> Path:
        return self._abs(self.paths.relatorios)


def carregar_config(caminho: Optional[Path] = None) -> Config:
    """Le o config.yaml. Ausencia do arquivo nao e erro: os defaults valem."""
    caminho = caminho or Path(os.environ.get("HFPAPERS_CONFIG", RAIZ / "config.yaml"))
    dados: dict = {}
    if caminho.exists():
        dados = yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}
    return Config(**dados)


@lru_cache(maxsize=1)
def config() -> Config:
    load_dotenv(RAIZ / ".env", override=False)
    return carregar_config()


@lru_cache(maxsize=1)
def ambiente() -> Ambiente:
    load_dotenv(RAIZ / ".env", override=False)
    return Ambiente()
