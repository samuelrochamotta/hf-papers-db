"""Cliente do OpenRouter: saida estruturada, retry, contabilidade de custo.

OpenRouter e compativel com a API da OpenAI, entao o SDK `openai` serve - so
muda a base e os headers de atribuicao.

`provider.require_parameters = true` no corpo evita que a requisicao caia num
provedor que ignore o `response_format` e devolva texto livre.

Precos vem sempre de `/api/v1/models` (a tabela viva), nunca de constante no
codigo. A chave nunca aparece em log, nem em mensagem de erro.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import httpx
from openai import OpenAI

from .. import db
from ..config import Config, ambiente, config
from ..log import logger

log = logger("llm")


class ErroLLM(RuntimeError):
    pass


class ErroTruncado(RuntimeError):
    """`finish_reason == 'length'`: o JSON veio cortado no meio.

    Retentar com o mesmo teto so repete o corte, entao a retentativa dobra
    `max_tokens`. Modelos que emitem raciocinio antes da resposta (os Claude 5,
    por exemplo) consomem o orcamento de saida antes de comecar o JSON.
    """


class ErroValidacao(ValueError):
    """Resposta bem formada pelo schema, mas invalida pelas regras da secao 4.4.

    Dispara uma retentativa com a mensagem anexada ao prompt.
    """


@dataclass
class Uso:
    tokens_entrada: int = 0
    tokens_saida: int = 0
    custo_usd: float = 0.0
    chamadas: int = 0

    def somar(self, outro: "Uso") -> None:
        self.tokens_entrada += outro.tokens_entrada
        self.tokens_saida += outro.tokens_saida
        self.custo_usd += outro.custo_usd
        self.chamadas += outro.chamadas


@dataclass
class Resposta:
    dados: dict[str, Any]
    uso: Uso
    modelo: str
    tentativas: int = 1
    latencia_ms: int = 0


# ── catalogo de modelos / precos ────────────────────────────────────────────


@dataclass
class Preco:
    entrada_por_token: float = 0.0
    saida_por_token: float = 0.0

    def custo(self, tokens_entrada: int, tokens_saida: int) -> float:
        return tokens_entrada * self.entrada_por_token + tokens_saida * self.saida_por_token


def catalogo_modelos(cfg: Optional[Config] = None, *, timeout: float = 30.0) -> list[dict]:
    cfg = cfg or config()
    chave = ambiente().chave_openrouter()
    headers = {"Authorization": f"Bearer {chave}"} if chave else {}
    r = httpx.get(f"{cfg.llm.base_url}/models", headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.json().get("data", [])


def suporta_saida_estruturada(modelo: dict) -> bool:
    sp = modelo.get("supported_parameters") or []
    return "structured_outputs" in sp or "response_format" in sp


def tabela_precos(cfg: Optional[Config] = None) -> dict[str, Preco]:
    precos: dict[str, Preco] = {}
    for m in catalogo_modelos(cfg):
        p = m.get("pricing") or {}
        try:
            precos[m["id"]] = Preco(float(p.get("prompt") or 0), float(p.get("completion") or 0))
        except (TypeError, ValueError):
            continue
    return precos


def tabela_parametros(cfg: Optional[Config] = None) -> dict[str, set[str]]:
    """Quais parametros cada modelo aceita, segundo o proprio OpenRouter.

    Isto importa por causa do `require_parameters`: ele roteia so para provedor
    que aceite **todos** os parametros enviados. Mandar `temperature` para um
    modelo que nao a anuncia (os Claude 5, por exemplo) zera a lista de
    provedores e a chamada volta 404 'No endpoints found'.
    """
    return {
        m["id"]: set(m.get("supported_parameters") or []) for m in catalogo_modelos(cfg)
    }


# ── cliente ─────────────────────────────────────────────────────────────────


class ClienteLLM:
    def __init__(
        self,
        cfg: Optional[Config] = None,
        *,
        conn: Optional[sqlite3.Connection] = None,
        run_id: str = "sem-run",
        cliente: Optional[OpenAI] = None,
        precos: Optional[dict[str, Preco]] = None,
        parametros: Optional[dict[str, set[str]]] = None,
    ) -> None:
        self.cfg = cfg or config()
        self.conn = conn
        self.run_id = run_id
        self.uso = Uso()
        self._precos = precos
        self._parametros = parametros

        if cliente is not None:
            self.openai = cliente
        else:
            chave = ambiente().chave_openrouter()
            if not chave:
                raise ErroLLM("OPENROUTER_API_KEY ausente - veja o .env.example")
            self.openai = OpenAI(
                base_url=self.cfg.llm.base_url,
                api_key=chave,
                # timeout explicito: sem ele uma conexao pendurada trava a rodada
                # inteira em silencio (visto em producao: 53 min parado numa
                # unica chamada). max_retries=0 porque o retry e nosso, e o do
                # SDK esconderia a tentativa de `log_llm`.
                timeout=self.cfg.llm.timeout_s,
                max_retries=0,
                default_headers={
                    "HTTP-Referer": self.cfg.llm.referer,
                    "X-Title": self.cfg.llm.titulo_app,
                },
            )

    @classmethod
    def somente_precos(
        cls, cfg: Optional[Config] = None, *, precos: Optional[dict[str, Preco]] = None
    ) -> "ClienteLLM":
        """Instancia sem cliente de chat, para o `--dry-run`: le a tabela de
        precos e nao e capaz de gastar token."""
        obj = cls.__new__(cls)
        obj.cfg = cfg or config()
        obj.conn = None
        obj.run_id = "dry-run"
        obj.uso = Uso()
        obj._precos = precos
        obj._parametros = {}
        obj.openai = None  # type: ignore[assignment]
        return obj

    # ── precos ──────────────────────────────────────────────────────────────

    @property
    def precos(self) -> dict[str, Preco]:
        if self._precos is None:
            try:
                self._precos = tabela_precos(self.cfg)
            except Exception as e:  # noqa: BLE001 - custo desconhecido nao trava a rodada
                log.warning("tabela de precos indisponivel: %s", type(e).__name__)
                self._precos = {}
        return self._precos

    def preco(self, modelo: str) -> Preco:
        return self.precos.get(modelo, Preco())

    @property
    def parametros(self) -> dict[str, set[str]]:
        if self._parametros is None:
            try:
                self._parametros = tabela_parametros(self.cfg)
            except Exception as e:  # noqa: BLE001
                log.warning("catalogo de parametros indisponivel: %s", type(e).__name__)
                self._parametros = {}
        return self._parametros

    def aceita(self, modelo: str, parametro: str) -> bool:
        """Sem catalogo, assume que aceita - o retry cuida do resto."""
        suportados = self.parametros.get(modelo)
        return True if suportados is None else parametro in suportados

    def estimar(self, modelo: str, tokens_entrada: int, tokens_saida: int) -> float:
        return self.preco(modelo).custo(tokens_entrada, tokens_saida)

    # ── chamada ─────────────────────────────────────────────────────────────

    def chamar(
        self,
        *,
        etapa: str,
        modelo: str,
        prompt: str,
        sistema: Optional[str] = None,
        response_format: dict[str, Any],
        temperatura: float = 0.0,
        max_tokens: int = 1200,
        paper_id: Optional[str] = None,
        validar: Optional[Callable[[dict], None]] = None,
    ) -> Resposta:
        """Uma chamada com saida estruturada, com retentativa.

        `validar` roda depois do parse: se levantar `ErroValidacao`, a mensagem
        volta anexada ao prompt na tentativa seguinte. E o mecanismo da secao
        4.4 - o schema sozinho nao garante as regras cruzadas.
        """
        tentativas = max(1, self.cfg.llm.retry.tentativas)
        espera = self.cfg.llm.retry.backoff_inicial_s
        prompt_atual = prompt
        teto_saida = max_tokens
        ultimo_erro: Optional[Exception] = None
        t0 = time.monotonic()

        for tentativa in range(1, tentativas + 1):
            uso = Uso()
            try:
                mensagens = []
                if sistema:
                    mensagens.append({"role": "system", "content": sistema})
                mensagens.append({"role": "user", "content": prompt_atual})

                extras: dict[str, Any] = {}
                # `temperature` so vai se o modelo a anunciar: com
                # `require_parameters` ligado, um parametro nao suportado zera a
                # lista de provedores e a chamada volta 404.
                if self.aceita(modelo, "temperature"):
                    extras["temperature"] = temperatura

                r = self.openai.chat.completions.create(
                    model=modelo,
                    messages=mensagens,
                    max_tokens=teto_saida,
                    response_format=response_format,
                    extra_body={
                        "provider": {
                            "require_parameters": self.cfg.llm.provider.require_parameters
                        }
                    },
                    **extras,
                )
                escolha = r.choices[0]
                conteudo = escolha.message.content or ""
                uso = self._contabilizar(r, modelo)
                if getattr(escolha, "finish_reason", None) == "length":
                    raise ErroTruncado(
                        f"resposta cortada em {teto_saida} tokens de saida"
                    )
                dados = json.loads(conteudo)
                if validar:
                    validar(dados)
            except ErroTruncado as e:
                ultimo_erro = e
                self._registrar(etapa, modelo, paper_id, uso, tentativa, str(e))
                teto_saida *= 2
                log.warning(
                    "resposta truncada (%s, tentativa %s); novo teto de saida: %s",
                    paper_id, tentativa, teto_saida,
                )
            except ErroValidacao as e:
                ultimo_erro = e
                self._registrar(etapa, modelo, paper_id, uso, tentativa, str(e))
                log.warning("validacao falhou (%s, tentativa %s): %s", paper_id, tentativa, e)
                prompt_atual = (
                    f"{prompt}\n\n---\n\n"
                    f"A resposta anterior foi rejeitada pela validacao: {e}\n"
                    "Corrija e responda de novo, respeitando o schema e a ordem dos campos."
                )
            except json.JSONDecodeError as e:
                ultimo_erro = e
                self._registrar(etapa, modelo, paper_id, uso, tentativa, f"json invalido: {e}")
                log.warning("json invalido (%s, tentativa %s)", paper_id, tentativa)
            except Exception as e:  # noqa: BLE001 - erro de rede/provedor
                ultimo_erro = e
                self._registrar(
                    etapa, modelo, paper_id, Uso(), tentativa, f"{type(e).__name__}: {e}"
                )
                log.warning("chamada falhou (%s, tentativa %s): %s", paper_id, tentativa, type(e).__name__)
            else:
                latencia = int((time.monotonic() - t0) * 1000)
                self._registrar(etapa, modelo, paper_id, uso, tentativa, None, latencia)
                return Resposta(dados, uso, modelo, tentativa, latencia)

            if tentativa < tentativas:
                time.sleep(espera)
                espera *= 2

        raise ErroLLM(f"{etapa} falhou apos {tentativas} tentativas: {ultimo_erro}")

    # ── apoio ───────────────────────────────────────────────────────────────

    def _contabilizar(self, resposta: Any, modelo: str) -> Uso:
        u = getattr(resposta, "usage", None)
        entrada = int(getattr(u, "prompt_tokens", 0) or 0)
        saida = int(getattr(u, "completion_tokens", 0) or 0)
        uso = Uso(entrada, saida, self.preco(modelo).custo(entrada, saida), 1)
        self.uso.somar(uso)
        return uso

    def _registrar(
        self,
        etapa: str,
        modelo: str,
        paper_id: Optional[str],
        uso: Uso,
        tentativa: int,
        erro: Optional[str],
        latencia_ms: Optional[int] = None,
    ) -> None:
        if self.conn is None:
            return
        db.registrar_llm(
            self.conn,
            {
                "run_id": self.run_id,
                "paper_id": paper_id,
                "etapa": etapa,
                "modelo": modelo,
                "tokens_entrada": uso.tokens_entrada,
                "tokens_saida": uso.tokens_saida,
                "custo_usd": uso.custo_usd,
                "latencia_ms": latencia_ms,
                "tentativas": tentativa,
                "erro": erro,
                "criado_em": db.agora(),
            },
        )


# ── estimativa de custo (--dry-run) ─────────────────────────────────────────


@dataclass
class Estimativa:
    itens: list[dict] = field(default_factory=list)
    total_usd: float = 0.0

    def acrescentar(
        self, etapa: str, modelo: str, papers: int, tok_entrada: int, tok_saida: int, preco: Preco
    ) -> None:
        custo = preco.custo(tok_entrada * papers, tok_saida * papers)
        self.itens.append(
            {
                "etapa": etapa,
                "modelo": modelo,
                "papers": papers,
                "tokens_entrada": tok_entrada * papers,
                "tokens_saida": tok_saida * papers,
                "custo_usd": custo,
            }
        )
        self.total_usd += custo


def estimar_tokens(texto: str) -> int:
    """Aproximacao suficiente para uma estimativa de custo: ~4 caracteres/token."""
    return max(1, len(texto) // 4)
