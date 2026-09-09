"""Submissao v1 via Atom published; updated nunca e usado como data inicial."""
from __future__ import annotations

import datetime as dt
import email.utils
import time
import xml.etree.ElementTree as ET

import httpx

from .hf_client import LimitadorTaxa
from .modelos import id_base

URL = "https://export.arxiv.org/api/query"
NS = {"a": "http://www.w3.org/2005/Atom"}


class ClienteArxiv:
    def __init__(self, cliente=None):
        self.http = cliente or httpx.Client(timeout=30, follow_redirects=True,
            headers={"User-Agent": "hf-papers-db/0.1 (arxiv-v1-metadata)"})
        self.proprio = cliente is None
        self.limitador = LimitadorTaxa(1 / 3)

    def fechar(self):
        if self.proprio:
            self.http.close()

    def consultar(self, ids):
        erro = None
        for tentativa in range(3):
            espera = 3 * 2 ** tentativa
            self.limitador.esperar()
            try:
                response = self.http.get(URL, params={"id_list": ",".join(ids), "max_results": len(ids)})
                if response.status_code == 429 or response.status_code >= 500:
                    espera = 3 * 2 ** tentativa
                    retry = response.headers.get("Retry-After", "")
                    if retry:
                        try:
                            espera = max(espera, float(retry))
                        except ValueError:
                            try:
                                espera = max(espera, (email.utils.parsedate_to_datetime(retry) - dt.datetime.now(dt.timezone.utc)).total_seconds())
                            except (TypeError, ValueError):
                                pass
                    response.raise_for_status()
                else:
                    espera = 3 * 2 ** tentativa
                    response.raise_for_status()
                root = ET.fromstring(response.content)
                if root.tag != '{http://www.w3.org/2005/Atom}feed':
                    raise ValueError('resposta nao e um feed Atom')
                resultados = {}
                for entry in root.findall('a:entry', NS):
                    pid = id_base((entry.findtext('a:id', '', NS)).split('/abs/')[-1])
                    if pid not in ids:
                        continue
                    raw = entry.findtext('a:published', '', NS)
                    try:
                        data = dt.datetime.fromisoformat(raw.replace('Z', '+00:00')).date().isoformat()
                    except ValueError:
                        continue
                    resultados[pid] = data
                return resultados
            except (httpx.HTTPError, ET.ParseError, ValueError) as exc:
                erro = exc
                if isinstance(exc, httpx.HTTPStatusError) and 400 <= exc.response.status_code < 500 and exc.response.status_code != 429:
                    break
                if tentativa < 2:
                    time.sleep(espera)
        raise RuntimeError(f'arxiv_consulta_falhou: {erro}')
