"""Guardrails de volume (secao 6.5) - validacao, nao decisao.

Nenhum destes altera um veredito. Todos apenas gravam aviso em
`log_execucao.avisos`. A taxa de FORA e a verificacao mais confiavel: entre 60%
e 80% o filtro opera normalmente **mesmo com muitos aprovados**.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .config import Guardrails as ConfigGuardrails


@dataclass
class Contagens:
    coletados: int = 0
    fora: int = 0
    amplo: int = 0
    estrito: int = 0
    dia_util: bool = True

    @property
    def classificados(self) -> int:
        return self.fora + self.amplo + self.estrito

    @property
    def aprovados(self) -> int:
        return self.amplo + self.estrito

    @property
    def taxa_fora(self) -> Optional[float]:
        return self.fora / self.classificados if self.classificados else None


def avaliar(c: Contagens, cfg: Optional[ConfigGuardrails] = None) -> list[str]:
    cfg = cfg or ConfigGuardrails()
    avisos: list[str] = []

    if c.dia_util and 0 < c.coletados < cfg.coletados_min_dia_util:
        avisos.append(f"coleta_suspeita:{c.coletados}")

    if not c.classificados:
        return avisos

    taxa = c.taxa_fora or 0.0
    if taxa < cfg.taxa_fora_min:
        avisos.append(f"criterio_frouxo:{taxa:.0%}")

    baixo, alto = cfg.aprovados_faixa_normal
    if not (baixo <= c.aprovados <= alto):
        avisos.append(f"volume_atipico:{c.aprovados}")
    if c.aprovados > cfg.aprovados_volume_alto:
        avisos.append(f"volume_alto:{c.aprovados}")
    if c.aprovados == 0:
        avisos.append("dia_sem_aprovados")

    return avisos
