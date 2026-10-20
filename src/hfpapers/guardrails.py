"""Guardrails de volume (secao 6.5) - validacao, nao decisao.

Nenhum destes altera um veredito. Todos apenas gravam aviso em
`log_execucao.avisos`.

As faixas de taxa de FORA e de aprovados/dia foram calibradas no regime
anterior ao ADR 004, que descartava treino e relatorio tecnico. No regime novo
elas sao provisorias (ver `config.yaml`) ate a recalibracao com a distribuicao
da reclassificacao total. O aviso de distribuicao por degrau e novo: se
`nenhum` domina os aprovados, o eixo de pre-requisito perdeu o sentido.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .config import Guardrails as ConfigGuardrails


@dataclass
class Contagens:
    coletados: int = 0
    fora: int = 0
    aprovados: int = 0
    por_prerequisito: dict[str, int] = field(default_factory=dict)
    nao_classificados: int = 0
    dia_util: bool = True

    @property
    def classificados(self) -> int:
        return self.fora + self.aprovados

    @property
    def taxa_fora(self) -> Optional[float]:
        return self.fora / self.classificados if self.classificados else None


def _avisos_volume(c: Contagens, cfg: ConfigGuardrails) -> list[str]:
    avisos: list[str] = []

    baixo, alto = cfg.aprovados_faixa_normal
    if not (baixo <= c.aprovados <= alto):
        # Desde que o Estagio B parou de fabricar `amplo` na falha (issue #1),
        # um dia com falhas some da conta de aprovados sem que o dia tenha
        # sido fraco. O aviso precisa do denominador, nao de silencio - e
        # justamente no dia em que algo deu errado que ele nao pode sumir.
        pend = f" (+{c.nao_classificados} pendentes)" if c.nao_classificados else ""
        avisos.append(f"volume_atipico:{c.aprovados}{pend}")
    if c.aprovados > cfg.aprovados_volume_alto:
        avisos.append(f"volume_alto:{c.aprovados}")
    if c.aprovados == 0:
        avisos.append("dia_sem_aprovados")

    # Distribuicao por degrau: com poucos aprovados a fracao e ruido, entao so
    # le a partir de um minimo.
    nenhum = c.por_prerequisito.get("nenhum", 0)
    if c.aprovados >= cfg.prerequisito_min_aprovados and nenhum / c.aprovados > cfg.prerequisito_nenhum_max:
        avisos.append(f"prerequisito_nenhum_alto:{nenhum / c.aprovados:.0%}")

    return avisos


def avaliar(c: Contagens, cfg: Optional[ConfigGuardrails] = None) -> list[str]:
    cfg = cfg or ConfigGuardrails()
    avisos: list[str] = []

    if c.dia_util and 0 < c.coletados < cfg.coletados_min_dia_util:
        avisos.append(f"coleta_suspeita:{c.coletados}")

    # Dia sem nada classificado E sem pendente: nao houve o que avaliar (fila
    # vazia, por exemplo). So aqui o guardrail fica mudo. Se houver pendente
    # (Estagio B falhou em todos os candidatos), classificados pode chegar a
    # zero sem que o dia tenha sido vazio - e e exatamente o dia em que o
    # guardrail nao pode calar (issue #1, criterio 5).
    if not c.classificados and not c.nao_classificados:
        return avisos

    # taxa_fora so tem leitura quando algo foi classificado. Sem classificado
    # nenhum ela cai para 0.0 e dispararia `criterio_frouxo:0%` por acidente -
    # frouxo descreve um filtro que deixou passar demais, nao a ausencia de
    # filtro. Os avisos de volume abaixo continuam rodando, porque esses
    # tratam `aprovados == 0` como leitura valida (e e o caso).
    if c.classificados:
        taxa = c.taxa_fora or 0.0
        if taxa < cfg.taxa_fora_min:
            avisos.append(f"criterio_frouxo:{taxa:.0%}")

    avisos.extend(_avisos_volume(c, cfg))

    return avisos
