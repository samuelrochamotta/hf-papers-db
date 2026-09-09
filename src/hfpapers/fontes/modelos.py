"""Modelos pydantic dos payloads do HF.

Tudo o que a secao 2.1 do PROMPT mediu como faltante (`ai_summary`,
`organization`, `githubRepo`, `projectPage`) e `Optional`. Tratar esses campos
como obrigatorios quebra a ingestao em ~1 dia a cada 3.

`extra="ignore"`: o HF acrescenta campo sem avisar e isso nao pode derrubar a
coleta.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

RE_VERSAO = re.compile(r"v\d+$")


def id_base(paper_id: str) -> str:
    """`2608.03451v2` e `2608.03451` sao o mesmo paper. A chave e sempre a base."""
    return RE_VERSAO.sub("", (paper_id or "").strip())


def _data(valor: Any) -> Optional[dt.date]:
    """ISO do HF (`2026-08-24T00:00:00.000Z`) -> date. Nunca levanta."""
    if valor is None:
        return None
    if isinstance(valor, dt.datetime):
        return valor.date()
    if isinstance(valor, dt.date):
        return valor
    texto = str(valor).strip()
    if not texto:
        return None
    try:
        return dt.date.fromisoformat(texto[:10])
    except ValueError:
        return None


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class Usuario(_Base):
    name: Optional[str] = None
    fullname: Optional[str] = None
    user: Optional[str] = None

    @property
    def login(self) -> Optional[str]:
        return self.user or self.name


class Organizacao(_Base):
    name: Optional[str] = None
    fullname: Optional[str] = None


class Autor(_Base):
    name: Optional[str] = None
    hidden: bool = False
    status: Optional[str] = None          # 'claimed_verified' no endpoint por-paper
    user: Optional[Usuario] = None

    @property
    def verificado(self) -> bool:
        return self.status == "claimed_verified"

    @property
    def hf_user(self) -> Optional[str]:
        return self.user.login if self.user else None


class Paper(_Base):
    """`item["paper"]` do daily_papers, e tambem o corpo de `/api/papers/{id}`."""

    id: str
    title: str
    summary: Optional[str] = None
    authors: list[Autor] = Field(default_factory=list)
    publishedAt: Optional[dt.date] = None          # data informada pelo HF; pode corresponder a uma revisao, nao v1
    submittedOnDailyAt: Optional[dt.date] = None   # entrada na lista diaria do HF
    submittedOnDailyBy: Optional[Usuario] = None
    upvotes: Optional[int] = None
    githubStars: Optional[int] = None
    githubRepo: Optional[str] = None
    githubRepoAddedBy: Optional[str] = None
    projectPage: Optional[str] = None
    discussionId: Optional[str] = None
    ai_summary: Optional[str] = None
    ai_keywords: list[str] = Field(default_factory=list)
    ai_summary_model: Optional[str] = None
    organization: Optional[Organizacao] = None

    # so no endpoint por-paper
    numTotalModels: Optional[int] = None
    numTotalDatasets: Optional[int] = None
    numTotalSpaces: Optional[int] = None

    @field_validator("publishedAt", "submittedOnDailyAt", mode="before")
    @classmethod
    def _parse_data(cls, v: Any) -> Any:
        return _data(v)

    @field_validator("ai_keywords", mode="before")
    @classmethod
    def _keywords(cls, v: Any) -> Any:
        return v or []

    @field_validator("id", mode="before")
    @classmethod
    def _id(cls, v: Any) -> Any:
        return id_base(str(v))

    @property
    def paper_id(self) -> str:
        return self.id

    @property
    def qtd_autores_verificados(self) -> int:
        return sum(1 for a in self.authors if a.verificado)


class ItemDiario(_Base):
    """Envelope externo do daily_papers.

    `publishedAt` daqui tem deslocamento de fuso e nao e exposto de proposito -
    quem precisa de data usa `paper.publishedAt` / `paper.submittedOnDailyAt`.
    `numComments` so existe neste nivel.
    """

    paper: Paper
    numComments: Optional[int] = None
    thumbnail: Optional[str] = None
    submittedBy: Optional[Usuario] = None
    organization: Optional[Organizacao] = None
    isAuthorParticipating: Optional[bool] = None


def paper_para_dim(
    paper: Paper,
    *,
    item: Optional[ItemDiario] = None,
    primeiro_visto_em: Optional[str] = None,
    enriquecido_em: Optional[str] = None,
) -> dict[str, Any]:
    """Achata Paper (+ envelope, quando houver) na linha de `dim_paper`."""
    org = paper.organization or (item.organization if item else None)
    submetido = paper.submittedOnDailyBy or (item.submittedBy if item else None)
    return {
        "paper_id": paper.paper_id,
        "titulo": paper.title,
        "abstract": paper.summary,
        "ai_summary": paper.ai_summary,
        "ai_summary_model": paper.ai_summary_model,
        "data_arxiv": paper.publishedAt,  # alias legado
        "data_arxiv_informada_hf": paper.publishedAt,
        "data_hf_daily": paper.submittedOnDailyAt,
        "url_arxiv": f"https://arxiv.org/abs/{paper.paper_id}",
        "url_hf": f"https://huggingface.co/papers/{paper.paper_id}",
        "project_page": paper.projectPage,
        "github_repo": paper.githubRepo,
        "github_repo_added_by": paper.githubRepoAddedBy,
        "tem_codigo_aberto": int(bool(paper.githubRepo)),
        "discussion_id": paper.discussionId,
        "thumbnail_url": item.thumbnail if item else None,
        "organizacao": org.name if org else None,
        "organizacao_nome_longo": org.fullname if org else None,
        "submetido_por": submetido.login if submetido else None,
        "submetido_por_nome": submetido.fullname if submetido else None,
        "autor_participa": (
            int(item.isAuthorParticipating) if item and item.isAuthorParticipating is not None else None
        ),
        "qtd_autores": len(paper.authors) or None,
        "qtd_autores_verificados": paper.qtd_autores_verificados,
        "primeiro_visto_em": primeiro_visto_em,
        "enriquecido_em": enriquecido_em,
    }


def paper_para_metrica(
    paper: Paper,
    *,
    data_snapshot: dt.date,
    origem: str,
    comentarios: Optional[int] = None,
) -> dict[str, Any]:
    return {
        "paper_id": paper.paper_id,
        "data_snapshot": data_snapshot,
        "upvotes": paper.upvotes,
        "comentarios": comentarios,
        "github_stars": paper.githubStars,
        "qtd_modelos": paper.numTotalModels,
        "qtd_datasets": paper.numTotalDatasets,
        "qtd_spaces": paper.numTotalSpaces,
        "origem": origem,
    }
