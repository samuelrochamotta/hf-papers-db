"""Parser dos digests historicos em `seed/digests/`.

O pipeline antigo esta aposentado; estes arquivos entram so como **conjunto de
validacao** do backfill: 83 fichas ja revisadas contra as quais as fichas
regeneradas sao comparadas.

Cada digest e internamente consistente - o numero de blocos `###` bate com
`Amplo + Estrito` da sua propria tabela de Operacao. Isso e o teste do parser:
se a contagem nao fechar para algum dia, o parser esta errado, nao o arquivo.

O bloco **PADRÃO EXTRAÍDO** e condicional por desenho e pode nao existir
(`2608.12440`, de 14/08, legitimamente nao o tem).
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

RE_SECAO = re.compile(r"^##\s+(\d)\.\s*(.+?)\s*$")
RE_FICHA = re.compile(r"^###\s+(.+?)\s*$")
RE_CABECALHO = re.compile(
    r"^\*\*arXiv:\*\*\s*(?P<id>[\w.\-/]+)\s*\|\s*"
    r"\*\*Data:\*\*\s*(?P<data>[\d\-]+)\s*\|\s*"
    r"\*\*Upvotes:\*\*\s*(?P<upvotes>\d+)"
)
RE_CAMPO = re.compile(
    r"^\*\*(ACHADO|PADRÃO EXTRAÍDO|IMPLICAÇÃO PRÁTICA|EXEMPLO CONCRETO|RESSALVA):\*\*\s*(.*)$"
)
RE_PADRAO = re.compile(r"^\*\*(?P<nome>.+?)\.?\*\*\s*(?P<mecanismo>.*)$", re.DOTALL)
RE_LINHA_OPERACAO = re.compile(
    r"^\|\s*(?P<dia>\d{4}-\d{2}-\d{2})\s*\|\s*(?P<coletados>\d+)\s*\|\s*"
    r"(?P<descartados>\d+)\s*\|\s*(?P<fora>\d+)\s*\|\s*(?P<amplo>\d+)\s*\|\s*(?P<estrito>\d+)\s*\|"
)

CAMPO_ATRIBUTO = {
    "ACHADO": "achado",
    "PADRÃO EXTRAÍDO": "padrao",
    "IMPLICAÇÃO PRÁTICA": "implicacao_pratica",
    "EXEMPLO CONCRETO": "exemplo_concreto",
    "RESSALVA": "ressalva",
}


@dataclass
class FichaHistorica:
    paper_id: str
    titulo: str
    veredito: str            # 'estrito' (secao 3) | 'amplo' (secao 4)
    data: Optional[dt.date] = None
    upvotes_dia1: Optional[int] = None
    achado: str = ""
    padrao_nome: Optional[str] = None
    padrao_mecanismo: Optional[str] = None
    implicacao_pratica: str = ""
    exemplo_concreto: str = ""
    ressalva: str = ""
    arquivo: Optional[str] = None

    @property
    def tem_padrao(self) -> bool:
        return bool(self.padrao_nome)


@dataclass
class Digest:
    arquivo: str
    dia: Optional[dt.date] = None
    coletados: int = 0
    descartados_por_estado: int = 0
    fora: int = 0
    amplo: int = 0
    estrito: int = 0
    fichas: list[FichaHistorica] = field(default_factory=list)

    @property
    def aprovados_declarados(self) -> int:
        return self.amplo + self.estrito

    @property
    def consistente(self) -> bool:
        """Teste do parser: blocos `###` == Amplo + Estrito da tabela."""
        return len(self.fichas) == self.aprovados_declarados


def _fechar_campo(ficha: FichaHistorica, campo: Optional[str], buffer: list[str]) -> None:
    if not campo or ficha is None:
        return
    texto = "\n".join(buffer).strip()
    if campo == "PADRÃO EXTRAÍDO":
        m = RE_PADRAO.match(texto)
        if m:
            ficha.padrao_nome = m.group("nome").strip().rstrip(".")
            ficha.padrao_mecanismo = m.group("mecanismo").strip()
        else:
            ficha.padrao_mecanismo = texto
    else:
        setattr(ficha, CAMPO_ATRIBUTO[campo], texto)


def parse_digest(texto: str, *, arquivo: str = "") -> Digest:
    digest = Digest(arquivo=arquivo)
    secao = 0
    ficha: Optional[FichaHistorica] = None
    campo: Optional[str] = None
    buffer: list[str] = []

    def fechar_ficha() -> None:
        nonlocal ficha, campo, buffer
        if ficha is not None:
            _fechar_campo(ficha, campo, buffer)
            digest.fichas.append(ficha)
        ficha, campo, buffer = None, None, []

    for linha in texto.splitlines():
        m_secao = RE_SECAO.match(linha)
        if m_secao:
            fechar_ficha()
            secao = int(m_secao.group(1))
            continue

        if secao == 1:
            m_op = RE_LINHA_OPERACAO.match(linha)
            if m_op:
                digest.dia = dt.date.fromisoformat(m_op.group("dia"))
                digest.coletados = int(m_op.group("coletados"))
                digest.descartados_por_estado = int(m_op.group("descartados"))
                digest.fora = int(m_op.group("fora"))
                digest.amplo = int(m_op.group("amplo"))
                digest.estrito = int(m_op.group("estrito"))
            continue

        if secao not in (3, 4):
            fechar_ficha()
            continue

        m_ficha = RE_FICHA.match(linha)
        if m_ficha:
            fechar_ficha()
            ficha = FichaHistorica(
                paper_id="",
                titulo=m_ficha.group(1),
                veredito="estrito" if secao == 3 else "amplo",
                arquivo=arquivo,
            )
            continue

        if ficha is None:
            continue

        m_cab = RE_CABECALHO.match(linha)
        if m_cab:
            ficha.paper_id = m_cab.group("id")
            ficha.data = dt.date.fromisoformat(m_cab.group("data"))
            ficha.upvotes_dia1 = int(m_cab.group("upvotes"))
            continue

        m_campo = RE_CAMPO.match(linha)
        if m_campo:
            _fechar_campo(ficha, campo, buffer)
            campo = m_campo.group(1)
            buffer = [m_campo.group(2)]
            continue

        if campo:
            buffer.append(linha)

    fechar_ficha()
    return digest


def carregar_digests(diretorio: Path) -> list[Digest]:
    arquivos = sorted(Path(diretorio).glob("hf-digest-*.md"))
    return [parse_digest(a.read_text(encoding="utf-8"), arquivo=a.name) for a in arquivos]


def fichas_por_id(digests: Iterable[Digest]) -> dict[str, FichaHistorica]:
    return {f.paper_id: f for d in digests for f in d.fichas if f.paper_id}
