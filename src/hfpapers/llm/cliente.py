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
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, Optional

import httpx
from openai import OpenAI

from .. import db
from ..config import Config, ambiente, config
from ..log import logger

log = logger("llm")

# Uma trava so, do modulo, para todos os clientes. Ela existe por causa do
# estagio 3 com `llm.concorrencia > 1`: varias chamadas rodam em threads e
# somam no mesmo `self.uso` e no mesmo buffer de `log_llm`. Ser do modulo, e
# nao da instancia, e deliberado - `somente_precos` e os dubles de teste montam
# o objeto sem passar por `__init__`, e uma trava global dispensa a pergunta
# "esta instancia tem trava?".
#
# Quase tudo que ela protege sao secoes de microssegundos (somar quatro
# inteiros, empilhar um dict). A excecao sao `precos` e `parametros`: eles
# fazem um `httpx.get` cada, com `timeout=30 s`, e sao preenchidos sob a trava
# de proposito - assim o catalogo e buscado uma vez, e nao uma por thread. O
# preco disso e que o primeiro lote de uma rodada concorrente pode ficar
# serializado por ate ~60 s enquanto a primeira thread busca os dois catalogos.
# E o negocio certo (uma busca em vez de oito), mas nao e uma secao curta -
# quem for mexer aqui precisa saber.
#
# `RLock` porque `_contabilizar` chama `self.preco`, que tambem a toma.
_TRAVA = threading.RLock()

# Sentinela de `drenar_registros`: drenar o buffer inteiro, e nao so as linhas
# de um paper. `None` nao serve - e `paper_id` legitimo de chamada sem paper.
_TODOS = object()


class ErroLLM(RuntimeError):
    pass


class ErroTruncado(RuntimeError):
    """`finish_reason == 'length'`: o JSON veio cortado no meio.

    Retentar com o mesmo teto so repete o corte, entao a retentativa dobra
    `max_tokens`. Modelos que emitem raciocinio antes da resposta (os Claude 5,
    por exemplo) consomem o orcamento de saida antes de comecar o JSON.
    """


class ErroProvedor(RuntimeError):
    """O OpenRouter devolveu corpo de erro no lugar da resposta.

    Acontece com HTTP 200: `{"error": {"message": "Provider returned error",
    "code": 429}}` e `choices` nulo. O SDK nao levanta nada, entao sem esta
    checagem `r.choices[0]` estoura `TypeError` e o operador ve um bug nosso
    onde ha um provedor fora do ar (2026-09-08: 7 chamadas numa rodada de 57).
    Herda de `RuntimeError` para cair na retentativa generica de rede.
    """


def _escolha_unica(resposta: Any) -> Any:
    """A primeira escolha, ou o erro do provedor com a mensagem dele."""
    escolhas = getattr(resposta, "choices", None)
    if escolhas:
        return escolhas[0]
    erro = getattr(resposta, "error", None) or {}
    detalhe = erro.get("message") if isinstance(erro, dict) else str(erro)
    raise ErroProvedor(f"resposta sem choices: {detalhe or 'sem detalhe do provedor'}")


class ErroPrazo(RuntimeError):
    """A chamada passou do prazo total e foi abandonada.

    Existe porque `llm.timeout_s` nao protege: ele e read timeout do httpx, e o
    keep-alive do OpenRouter (`: OPENROUTER PROCESSING`) o reinicia a cada
    linha. Medido em 2026-09-08: uma chamada de 409,8 s atravessou inteira um
    teto de 180 s sem erro, sem retentativa e sem linha em `log_llm`, e ela
    **foi** a parede de uma rodada de 30 papers - a rodada durou 409 s, e as
    outras 29 chamadas rodaram inteiras por baixo dela.

    Herda de `RuntimeError` para cair na retentativa generica de rede - que e o
    ponto: a instancia seguinte costuma responder em segundos.
    """


def _com_prazo(chamada: Callable[[], Any], prazo_s: float) -> Any:
    """Executa `chamada` numa thread e desiste dela ao fim de `prazo_s`.

    Nao existe cancelamento de verdade: a thread abandonada segue presa no I/O
    ate o OpenRouter responder, e a resposta dela e paga e descartada. E barato
    perto do que se evita - a chamada abandonada custa ~US$ 0,0004, e esperar
    por ela custou 409 s de uma rodada.

    O custo dela tambem nao entra em `log_llm`: a linha do corte sai com uso
    zero, porque a resposta que traria os tokens nunca foi lida. `log_llm`
    subestima o gasto exatamente nas chamadas cortadas - conte-as pelo
    `erro LIKE 'ErroPrazo%'` quando for conferir a fatura.

    `daemon=True` e obrigatorio: `ThreadPoolExecutor` faz join das suas threads
    no fim do interpretador, entao uma orfa penduraria a saida do processo -
    trocando uma rodada travada por um processo que nao termina.
    """
    caixa: dict[str, Any] = {}
    pronto = threading.Event()

    def alvo() -> None:
        try:
            caixa["valor"] = chamada()
        except BaseException as e:  # noqa: BLE001 - reerguida no chamador, intacta
            caixa["erro"] = e
        finally:
            pronto.set()

    threading.Thread(target=alvo, daemon=True, name="llm-prazo").start()
    if not pronto.wait(prazo_s):
        raise ErroPrazo(f"prazo de {prazo_s:g}s estourado; chamada abandonada")
    if "erro" in caixa:
        raise caixa["erro"]
    return caixa["valor"]


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
    # Quanto de `tokens_entrada` veio do cache do provedor - so diagnostico,
    # nao entra em `custo_usd` porque a tabela de precos (`tabela_precos`) so
    # tem o preco cheio de entrada/saida, sem a tarifa de leitura de cache.
    tokens_cache_leitura: int = 0

    def somar(self, outro: "Uso") -> None:
        self.tokens_entrada += outro.tokens_entrada
        self.tokens_saida += outro.tokens_saida
        self.custo_usd += outro.custo_usd
        self.chamadas += outro.chamadas
        self.tokens_cache_leitura += outro.tokens_cache_leitura


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
    # Default de classe, nao so de `__init__`: dubles de teste e clientes
    # montados por `__new__` tambem precisam responder "nao estou bufferizando".
    # Ligar o buffer atribui uma lista *na instancia*, sem vazar entre elas.
    _buffer: Optional[list[dict]] = None

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
        self._buffer: Optional[list[dict]] = None

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
        obj._buffer = None
        obj.openai = None  # type: ignore[assignment]
        return obj

    # ── precos ──────────────────────────────────────────────────────────────

    @property
    def precos(self) -> dict[str, Preco]:
        # Sob a trava porque o preenchimento e preguicoso: com concorrencia > 1,
        # a primeira chamada de cada thread cairia aqui ao mesmo tempo e faria
        # N requisicoes ao catalogo em vez de uma.
        with _TRAVA:
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
        with _TRAVA:  # mesmo motivo de `precos`
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
        esforco_raciocinio: Optional[str] = None,
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
            # Reiniciado a cada volta: a tentativa que morre antes da resposta
            # nao tem provedor, e herdar o da anterior seria acusar inocente.
            provedor: Optional[str] = None
            try:
                mensagens = []
                if sistema:
                    mensagens.append({"role": "system", "content": sistema})
                mensagens.append({"role": "user", "content": prompt_atual})

                provedores: dict[str, Any] = {
                    "require_parameters": self.cfg.llm.provider.require_parameters
                }
                if self.cfg.llm.provider.preferidos:
                    provedores["order"] = list(self.cfg.llm.provider.preferidos)
                    # Preferencia, nao exclusividade: se os preferidos estiverem
                    # fora do ar ou saturados, o resto do catalogo atende.
                    provedores["allow_fallbacks"] = True
                corpo_extra: dict[str, Any] = {"provider": provedores}
                # Medido em 2026-09-08, 140 papers e 420 chamadas: sem esta
                # linha o GLM 5.3 flash gasta 2.343 tokens de rascunho para
                # produzir 540 caracteres de JSON, e a chamada passa de 13 s
                # para 174 s. Desligar o raciocinio nao e opcao (`enabled:
                # false` volta HTTP 400, "Reasoning is mandatory"); baixar o
                # esforco e, e nao muda a classificacao - `low` e `medium`
                # concordam mais entre si (87%) do que `low` consigo mesmo
                # (82%).
                if esforco_raciocinio:
                    corpo_extra["reasoning"] = {"effort": esforco_raciocinio}

                extras: dict[str, Any] = {}
                # `temperature` so vai se o modelo a anunciar: com
                # `require_parameters` ligado, um parametro nao suportado zera a
                # lista de provedores e a chamada volta 404.
                if self.aceita(modelo, "temperature"):
                    extras["temperature"] = temperatura

                def _criar() -> Any:
                    return self.openai.chat.completions.create(
                        model=modelo,
                        messages=mensagens,
                        max_tokens=teto_saida,
                        response_format=response_format,
                        extra_body=corpo_extra,
                        **extras,
                    )

                prazo = self.cfg.llm.prazo_total_s
                r = _com_prazo(_criar, prazo) if prazo > 0 else _criar()
                provedor = getattr(r, "provider", None)
                escolha = _escolha_unica(r)
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
                self._registrar(etapa, modelo, paper_id, uso, tentativa, str(e),
                                provedor=provedor)
                teto_saida *= 2
                log.warning(
                    "resposta truncada (%s, tentativa %s); novo teto de saida: %s",
                    paper_id, tentativa, teto_saida,
                )
            except ErroValidacao as e:
                ultimo_erro = e
                self._registrar(etapa, modelo, paper_id, uso, tentativa, str(e),
                                provedor=provedor)
                log.warning("validacao falhou (%s, tentativa %s): %s", paper_id, tentativa, e)
                prompt_atual = (
                    f"{prompt}\n\n---\n\n"
                    f"A resposta anterior foi rejeitada pela validacao: {e}\n"
                    "Corrija e responda de novo, respeitando o schema e a ordem dos campos."
                )
            except json.JSONDecodeError as e:
                ultimo_erro = e
                self._registrar(etapa, modelo, paper_id, uso, tentativa,
                                f"json invalido: {e}", provedor=provedor)
                log.warning("json invalido (%s, tentativa %s)", paper_id, tentativa)
            except Exception as e:  # noqa: BLE001 - erro de rede/provedor
                ultimo_erro = e
                self._registrar(
                    etapa, modelo, paper_id, Uso(), tentativa, f"{type(e).__name__}: {e}",
                    provedor=provedor,
                )
                log.warning("chamada falhou (%s, tentativa %s): %s", paper_id, tentativa, type(e).__name__)
            else:
                latencia = int((time.monotonic() - t0) * 1000)
                self._registrar(etapa, modelo, paper_id, uso, tentativa, None, latencia,
                                provedor=provedor)
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
        detalhes = getattr(u, "prompt_tokens_details", None)
        cache_leitura = int(getattr(detalhes, "cached_tokens", 0) or 0)
        with _TRAVA:  # `self.uso` e acumulador compartilhado entre as threads
            uso = Uso(entrada, saida, self.preco(modelo).custo(entrada, saida), 1, cache_leitura)
            self.uso.somar(uso)
        return uso

    # ── registro em `log_llm` ───────────────────────────────────────────────
    #
    # O paralelismo do estagio 3 e so do I/O do OpenRouter: nenhuma thread
    # trabalhadora toca o banco. Quando `registros_adiados` esta ativo,
    # `_registrar` empilha a linha num buffer e quem a grava e a thread
    # principal, em `drenar_registros`.
    #
    # Por que assim e nao com `check_same_thread=False` + trava na conexao: a
    # conexao do projeto e aberta com `isolation_level=None` e transacao
    # explicita (`db.transacao`). Um INSERT disparado por uma thread enquanto a
    # principal esta entre o BEGIN e o COMMIT de uma gravacao de triagem entra
    # naquela transacao alheia - e some no ROLLBACK se ela falhar. Uma trava na
    # conexao nao resolve isso: teria de cobrir a transacao inteira da thread
    # principal, o que serializaria justamente o que se quer paralelo. Buffer e
    # a rota que nao esconde esse risco.

    @contextmanager
    def registros_adiados(self) -> Iterator[None]:
        """Enquanto ativo, `log_llm` vai para um buffer em vez do banco.

        Ao sair, o que sobrou e drenado - inclusive quando a saida e por
        excecao, para que uma rodada interrompida nao perca a contabilidade das
        chamadas que ja pagou.
        """
        with _TRAVA:
            self._buffer = []
        try:
            yield
        finally:
            self.drenar_registros()
            with _TRAVA:
                self._buffer = None

    def drenar_registros(self, paper_id: Any = _TODOS) -> int:
        """Grava as linhas empilhadas. **So a thread principal chama.**

        Drenar por paper, e nao o buffer inteiro de uma vez, e o que mantem
        `log_llm` deterministico: as linhas saem na ordem original dos papers,
        e nao na ordem em que as threads terminaram. Dentro de um paper a ordem
        ja e a das chamadas, porque um paper e sempre de uma thread so.
        """
        with _TRAVA:
            buffer = self._buffer
            if not buffer:
                return 0
            if paper_id is _TODOS:
                linhas, self._buffer = buffer, []
            else:
                linhas = [x for x in buffer if x["paper_id"] == paper_id]
                self._buffer = [x for x in buffer if x["paper_id"] != paper_id]
        for linha in linhas:
            db.registrar_llm(self.conn, linha)
        return len(linhas)

    def _registrar(
        self,
        etapa: str,
        modelo: str,
        paper_id: Optional[str],
        uso: Uso,
        tentativa: int,
        erro: Optional[str],
        latencia_ms: Optional[int] = None,
        provedor: Optional[str] = None,
    ) -> None:
        if self.conn is None:
            return
        linha = {
            "run_id": self.run_id,
            "paper_id": paper_id,
            "etapa": etapa,
            "modelo": modelo,
            "tokens_entrada": uso.tokens_entrada,
            "tokens_saida": uso.tokens_saida,
            "tokens_cache_leitura": uso.tokens_cache_leitura,
            "custo_usd": uso.custo_usd,
            "latencia_ms": latencia_ms,
            "tentativas": tentativa,
            "erro": erro,
            "provedor": provedor,
            "criado_em": db.agora(),
        }
        with _TRAVA:
            if self._buffer is not None:
                self._buffer.append(linha)
                return
        db.registrar_llm(self.conn, linha)


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
