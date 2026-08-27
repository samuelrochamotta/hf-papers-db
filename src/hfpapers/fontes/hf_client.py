"""Cliente do huggingface.co: rate limit, retry com backoff, sem autenticacao.

Duas rotas so:

* `daily_papers(data)`  - lista do dia. Re-consultar uma data antiga devolve
  metricas ATUAIS, nao congeladas (secao 2.3). E o que torna o refresh barato:
  1 requisicao por data em vez de 1 por paper.
* `paper(id)`           - detalhe. Unico lugar com `numTotal*` e
  `authors[].status`.
"""

from __future__ import annotations

import datetime as dt
import time
from typing import Optional

import httpx

from ..config import Config, config
from ..log import logger
from .modelos import ItemDiario, Paper, id_base

log = logger("hf")


class ErroHF(RuntimeError):
    pass


class LimitadorTaxa:
    """Espacamento simples entre requisicoes. Sem rate limit documentado no HF,
    o teto de 5 req/s vem da secao 2 do PROMPT."""

    def __init__(self, req_por_segundo: float) -> None:
        self.intervalo = 1.0 / req_por_segundo if req_por_segundo > 0 else 0.0
        self._proximo = 0.0

    def esperar(self) -> None:
        if not self.intervalo:
            return
        agora = time.monotonic()
        if agora < self._proximo:
            time.sleep(self._proximo - agora)
        self._proximo = max(agora, self._proximo) + self.intervalo


class ClienteHF:
    def __init__(
        self,
        cfg: Optional[Config] = None,
        *,
        cliente: Optional[httpx.Client] = None,
    ) -> None:
        self.cfg = (cfg or config()).hf
        self._proprio = cliente is None
        self.http = cliente or httpx.Client(
            base_url=self.cfg.base_url,
            timeout=self.cfg.timeout_s,
            headers={"User-Agent": "hf-papers-db/0.1 (+pipeline diario)"},
            follow_redirects=True,
        )
        self.limitador = LimitadorTaxa(self.cfg.req_por_segundo)
        self.requisicoes = 0

    def __enter__(self) -> "ClienteHF":
        return self

    def __exit__(self, *exc: object) -> None:
        self.fechar()

    def fechar(self) -> None:
        if self._proprio:
            self.http.close()

    # ── transporte ──────────────────────────────────────────────────────────

    def _get(self, url: str, params: Optional[dict] = None) -> httpx.Response:
        espera = self.cfg.backoff_inicial_s
        ultimo: Optional[Exception] = None
        for tentativa in range(1, self.cfg.tentativas + 1):
            self.limitador.esperar()
            self.requisicoes += 1
            try:
                r = self.http.get(url, params=params)
            except httpx.HTTPError as e:
                ultimo = e
            else:
                if r.status_code == 404:
                    raise ErroHF(f"404 em {url}")
                if r.status_code == 429 or r.status_code >= 500:
                    ultimo = ErroHF(f"HTTP {r.status_code} em {url}")
                    espera_hdr = r.headers.get("retry-after")
                    if espera_hdr and espera_hdr.isdigit():
                        espera = float(espera_hdr)
                else:
                    r.raise_for_status()
                    return r
            if tentativa < self.cfg.tentativas:
                log.warning("retry %s/%s em %s apos %.1fs (%s)",
                            tentativa, self.cfg.tentativas, url, espera, ultimo)
                time.sleep(espera)
                espera *= 2
        raise ErroHF(f"falhou apos {self.cfg.tentativas} tentativas: {ultimo}")

    # ── rotas ───────────────────────────────────────────────────────────────

    def daily_papers(self, data: dt.date) -> list[ItemDiario]:
        r = self._get("/api/daily_papers", {"date": data.isoformat()})
        bruto = r.json()
        if not isinstance(bruto, list):
            raise ErroHF(f"resposta inesperada em daily_papers({data}): {type(bruto)}")
        itens: list[ItemDiario] = []
        for cru in bruto:
            try:
                itens.append(ItemDiario.model_validate(cru))
            except Exception as e:  # noqa: BLE001 - um item ruim nao derruba o dia
                log.warning("item invalido em %s: %s", data, e)
        return itens

    def paper(self, paper_id: str) -> Paper:
        pid = id_base(paper_id)
        r = self._get(f"/api/papers/{pid}")
        return Paper.model_validate(r.json())
