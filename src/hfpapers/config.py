"""Configuracao: config.yaml (parametros) + .env (segredos).

Regra: a chave da API vive so no ambiente e nunca aparece em log nem em repr.
Por isso `Ambiente.openrouter_api_key` e um SecretStr.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

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

    openrouter_api_key: SecretStr | None = Field(default=None)

    def chave_openrouter(self) -> str | None:
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
    esforco_raciocinio: str | None = None

    @property
    def configurado(self) -> bool:
        return bool(self.modelo) and self.modelo != "PREENCHER"


class ProviderLLM(BaseModel):
    require_parameters: bool = True
    # Endpoints tentados primeiro, na ordem. Vazio deixa o balanceador do
    # OpenRouter escolher, que e o padrao. A lista existe porque os endpoints do
    # mesmo modelo nao se comportam igual e a diferenca nao aparece no catalogo:
    # em 2026-09-08, 171 chamadas medidas deram Together com 3,3 s de media e
    # 13,8 s de pior caso, contra 14,6 s de media e 55,5 s de pior do Sail
    # Research - e foi a cauda deste que pendurou a rodada 1 do ticket 07 com
    # quatro threads paradas. Uma sonda fora do pipeline pegou o Sail em 195 s;
    # esse valor nao esta em `log_llm`, que so ganhou a coluna `provedor` depois.
    #
    # O fallback fica sempre ligado: preferencia nao e exclusividade, e uma lista
    # de um nome so sem fallback recria a armadilha do provedor unico (o 429 do
    # pool compartilhado sem para onde ir, que ja custou um dia de operacao).
    preferidos: list[str] = Field(default_factory=list)


class RetryLLM(BaseModel):
    tentativas: int = 3
    backoff_inicial_s: float = 2


class LLM(BaseModel):
    base_url: str = "https://openrouter.ai/api/v1"
    referer: str = "https://github.com/samuelrochamotta/hf-papers-db"
    titulo_app: str = "hf-papers-db"
    timeout_s: float = 180
    # Teto de ponta a ponta por chamada, em segundos. Nao e o mesmo que
    # `timeout_s`: aquele e read timeout do httpx, e o keep-alive do OpenRouter
    # (`: OPENROUTER PROCESSING`) o reinicia a cada linha, entao uma chamada de
    # 409,8 s atravessa um teto de 180 s sem erro, sem retentativa e sem linha
    # em `log_llm`. Foi assim que a rodada 1 do ticket 07 parou.
    #
    # 90 s vem da medicao de 2026-09-08, ja sob `esforco_raciocinio`: em 201
    # chamadas com provedor registrado (as validacoes de 15:06-15:12 mais a
    # rodada que expos a cauda), o pior caso legitimo foi 55,5 s no estagio A e
    # 13,8 s no estagio B, e o proximo valor depois de 55,5 era 409,8 s. O teto cai no
    # vazio entre os dois. `0` desliga, e a escotilha para quando o modelo
    # mudar e a distribuicao junto.
    prazo_total_s: float = 90
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
    # Calibrados na reclassificacao total do ADR 004: ver config.yaml.
    taxa_fora_min: float = 0.20
    taxa_fora_faixa_normal: tuple[float, float] = (0.25, 0.47)
    aprovados_faixa_normal: tuple[int, int] = (13, 40)
    aprovados_volume_alto: int = 45
    coletados_min_dia_util: int = 15
    prerequisito_nenhum_max: float = 0.15
    prerequisito_min_aprovados: int = 10


class Perfil(BaseModel):
    """Um perfil de leitura: o conjunto de degraus de pre-requisito em que o
    leitor consegue agir. Fica fora do paper (ADR 004): mudar aqui nao
    reclassifica nada, so muda o filtro."""

    perfil: str
    rotulo: str
    prerequisitos: list[str]


PERFIS_PADRAO = [
    Perfil(perfil="produto", rotulo="Produto", prerequisitos=["nenhum", "implementar"]),
    Perfil(
        perfil="pesquisa_treino",
        rotulo="Treino/pesquisa",
        prerequisitos=["acesso_interno", "treino", "sem_acao"],
    ),
]


class Leitura(BaseModel):
    """Leitura do texto completo para o painel v2 (ADR 007)."""

    # Pelo OpenRouter, como os estagios A e B. O catalogo (2026-11-14) anuncia
    # `structured_outputs` e `response_format` para este modelo.
    modelo: str = "anthropic/claude-haiku-5.5"
    # Extracao e copia de trechos e escolha em listas fechadas: `low` basta e
    # gasta menos tokens de raciocinio. Suba so com medicao no conjunto-ouro.
    esforco: str = "low"
    max_tokens: int = 16000
    # O Haiku 5.5 cobra o dobro acima de 100 mil tokens de prompt. ~4 caracteres
    # por token: 320 mil caracteres ficam perto de 80 mil tokens, com folga para
    # o esquema e as instrucoes. O que passar disso e cortado no fim (apendices
    # primeiro, porque o texto ja chega sem as referencias).
    teto_caracteres: int = 320_000
    # Prazo de ponta a ponta por chamada (o `llm.prazo_total_s` dos estagios,
    # 90 s, e curto para 80 mil tokens de entrada e 6 mil de saida).
    prazo_s: float = 300
    # Janela padrao do comando `ler`, em dias de HF Daily, e piso de votos.
    dias: int = 7
    min_votos: int = 0
    versao_esquema: str = "v1"


class Export(BaseModel):
    csv: bool = False


class Config(BaseModel):
    paths: Paths = Paths()
    hf: HF = HF()
    llm: LLM = LLM()
    refresh: Refresh = Refresh()
    guardrails: Guardrails = Guardrails()
    export: Export = Export()
    leitura: Leitura = Leitura()
    perfis: list[Perfil] = PERFIS_PADRAO

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


def carregar_config(caminho: Path | None = None) -> Config:
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
