"""Issue #1, criterio 5: guardrails de volume ganham o denominador de pendentes.

`Contagens.nao_classificados` alimenta `_avisos_volume` - quando > 0, o aviso
`volume_atipico` mostra o denominador (`volume_atipico:3 (+3 pendentes)`);
quando 0, o formato antigo e preservado literalmente. `avaliar` tambem deixa
de ficar mudo no dia em que tudo falhou (classificados == 0 mas ha pendentes).
"""

from hfpapers.config import Guardrails as CfgGuard
from hfpapers.guardrails import Contagens, _avisos_volume, avaliar

# ── _avisos_volume: os dois formatos ────────────────────────────────────────


def test_avisos_volume_sem_pendentes_preserva_formato_antigo():
    """nao_classificados == 0: o aviso continua sem sufixo, byte a byte."""
    c = Contagens(coletados=30, fora=27, aprovados=3)   # fora da faixa normal 13-40
    assert _avisos_volume(c, CfgGuard()) == ["volume_atipico:3"]


def test_avisos_volume_com_pendentes_mostra_denominador():
    """nao_classificados > 0: o aviso ganha o sufixo com o denominador."""
    c = Contagens(coletados=30, fora=24, aprovados=3, nao_classificados=3)
    assert _avisos_volume(c, CfgGuard()) == ["volume_atipico:3 (+3 pendentes)"]


def test_avisos_volume_dentro_da_faixa_nao_gera_aviso_mesmo_com_pendentes():
    """Pendente so aparece pendurado no `volume_atipico` - nao cria aviso
    novo quando os aprovados estao dentro da faixa normal."""
    c = Contagens(coletados=40, fora=23, aprovados=15, nao_classificados=2)
    avisos = _avisos_volume(c, CfgGuard())
    assert avisos == []


# ── avaliar: classificados == 0 mas ha pendentes nao pode ficar mudo ───────


def test_avaliar_nao_fica_mudo_quando_classificados_zero_mas_ha_pendentes():
    """Antes da issue #1, um dia em que o Estagio B falhou em todos os
    candidatos tinha classificados == 0 e o guardrail devolvia [] - mudo
    justamente no dia em que algo deu errado. Agora ele fala."""
    c = Contagens(coletados=10, nao_classificados=3)
    avisos = avaliar(c)
    assert avisos != []
    assert "volume_atipico:0 (+3 pendentes)" in avisos
    assert "dia_sem_aprovados" in avisos
    # sem classificado nenhum, taxa_fora nao tem leitura - nao pode acusar
    # "criterio_frouxo:0%" por acidente
    assert not any(a.startswith("criterio_frouxo") for a in avisos)


def test_avaliar_continua_mudo_quando_nao_ha_nada_para_avaliar():
    """classificados == 0 e nao_classificados == 0 (fila vazia, por exemplo):
    nao ha o que avaliar - continua mudo, como antes da issue #1."""
    assert avaliar(Contagens(coletados=0)) == []
