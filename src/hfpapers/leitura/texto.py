"""Texto completo de um paper a partir do HTML do arXiv.

O arXiv publica, para a maioria dos papers recentes, uma versao HTML gerada do
LaTeX (LaTeXML) em `https://arxiv.org/html/<id>`. Ela traz o que o PDF obriga a
adivinhar: titulos de secao marcados, tabelas como tabelas e a formula com o
texto-fonte em `alttext`. Por isso a leitura parte dela, e nao do PDF.

O texto sai em Markdown simples: `## 4.2 Resultados` para cada titulo, um
paragrafo por linha em branco e cada tabela como `[Tabela 2] legenda` seguida
de linhas `a | b | c`. As referencias finais ficam de fora (nao ha nada a
extrair delas e elas pesam ate um terco do texto). O que passar do teto de
caracteres e cortado no fim, e o corte fica registrado: a extracao sabe onde
parou e o painel mostra "nao lido" em vez de "nao reportado".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Optional

import httpx

URL_HTML = "https://arxiv.org/html/{id}"

# Classes LaTeXML que encerram o corpo util do paper.
_FIM = ("ltx_bibliography",)
# Blocos que nunca viram texto.
_PULAR_TAGS = {"script", "style", "nav", "header", "footer", "button", "svg", "noscript"}
_PULAR_CLASSES = ("ltx_page_header", "ltx_page_footer", "ltx_authors", "ltx_dates",
                  "ltx_role_footnote", "ltx_note_outer", "package-alerts", "ltx_TOC")
_TITULOS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_BLOCOS = {"p", "div", "section", "li", "figcaption", "blockquote", "dd", "dt"}


@dataclass
class TextoPaper:
    arxiv_id: str
    texto: str
    fonte: str  # "html" | "abstract"
    secoes: list[str] = field(default_factory=list)
    tabelas: int = 0
    cortado_em: Optional[str] = None  # ultimo titulo inteiro antes do corte
    chegou_ao_fim: bool = True  # viu o fim do corpo (referencias ou fim do html)

    @property
    def caracteres(self) -> int:
        return len(self.texto)


class _Extrator(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.partes: list[str] = []
        self.secoes: list[str] = []
        self.tabelas = 0
        self.pilha_pular: list[str] = []  # tags abertas que estao sendo puladas
        self.fim = False
        self.no_titulo = False
        self.titulo_atual: list[str] = []
        self.tabela: Optional[list[list[str]]] = None
        self.celula: Optional[list[str]] = None
        self.legenda_tabela: Optional[str] = None
        self.no_caption = False
        self.caption: list[str] = []
        self.figura_tabela = 0  # profundidade dentro de <figure class="ltx_table">

    # ── estado ──────────────────────────────────────────────────────────────

    def _quebra(self) -> None:
        if self.partes and not self.partes[-1].endswith("\n\n"):
            self.partes.append("\n\n")

    def _escrever(self, txt: str) -> None:
        if self.celula is not None:
            self.celula.append(txt)
        elif self.no_caption:
            self.caption.append(txt)
        elif self.no_titulo:
            self.titulo_atual.append(txt)
        else:
            self.partes.append(txt)

    # ── HTMLParser ──────────────────────────────────────────────────────────

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        if self.fim:
            return
        a = dict(attrs)
        classes = a.get("class") or ""
        if self.pilha_pular:
            if tag not in _VAZIAS:
                self.pilha_pular.append(tag)
            return
        if any(c in classes for c in _FIM):
            self.fim = True
            return
        if tag in _PULAR_TAGS or any(c in classes for c in _PULAR_CLASSES):
            if tag not in _VAZIAS:
                self.pilha_pular.append(tag)
            return
        if tag == "math":
            # O texto-fonte da formula; o MathML interno e pulado.
            alt = a.get("alttext")
            if alt:
                self._escrever(f" ${alt.strip()}$ ")
            self.pilha_pular.append(tag)
            return
        if tag == "img":
            return
        if tag == "figure" and "ltx_table" in classes:
            self.figura_tabela += 1
        if tag in _TITULOS:
            self._quebra()
            self.no_titulo = True
            self.titulo_atual = []
        elif tag in ("figcaption", "caption"):
            self.no_caption = True
            self.caption = []
        elif tag == "table" and self.tabela is None:
            self.tabela = []
        elif tag == "tr" and self.tabela is not None:
            self.tabela.append([])
        elif tag in ("td", "th") and self.tabela is not None:
            self.celula = []
        elif tag == "br":
            self._escrever(" ")
        elif tag in _BLOCOS:
            self._quebra()

    def handle_endtag(self, tag: str) -> None:
        if self.fim:
            return
        if self.pilha_pular:
            # Fecha ate a tag correspondente (HTML mal formado nao trava o corte).
            while self.pilha_pular:
                if self.pilha_pular.pop() == tag:
                    break
            return
        if tag in _TITULOS and self.no_titulo:
            self.no_titulo = False
            titulo = _limpar(" ".join(self.titulo_atual))
            if titulo:
                nivel = int(tag[1])
                self.secoes.append(titulo)
                self.partes.append(f"{'#' * min(6, max(2, nivel))} {titulo}\n\n")
        elif tag in ("figcaption", "caption") and self.no_caption:
            self.no_caption = False
            legenda = _limpar(" ".join(self.caption))
            if self.figura_tabela or self.tabela is not None:
                self.legenda_tabela = legenda
            elif legenda:
                self._quebra()
                self.partes.append(f"[Figura] {legenda}\n\n")
        elif tag in ("td", "th") and self.celula is not None and self.tabela is not None:
            if self.tabela:
                self.tabela[-1].append(_limpar(" ".join(self.celula)))
            self.celula = None
        elif tag == "table" and self.tabela is not None:
            self._fechar_tabela()
        elif tag == "figure" and self.figura_tabela:
            self.figura_tabela -= 1
            if self.legenda_tabela and self.tabela is None:
                # Legenda depois da tabela (comum no LaTeXML): anexa ao ultimo bloco.
                self.partes.append(f"Legenda: {self.legenda_tabela}\n\n")
                self.legenda_tabela = None
        elif tag in _BLOCOS:
            self._quebra()

    def _fechar_tabela(self) -> None:
        linhas = [l for l in (self.tabela or []) if any(c for c in l)]
        self.tabela = None
        if not linhas:
            return
        self.tabelas += 1
        self._quebra()
        rotulo = f"[Tabela {self.tabelas}]"
        if self.legenda_tabela:
            rotulo += f" {self.legenda_tabela}"
            self.legenda_tabela = None
        self.partes.append(rotulo + "\n")
        for l in linhas:
            self.partes.append(" | ".join(l) + "\n")
        self.partes.append("\n")

    def handle_data(self, data: str) -> None:
        if self.fim or self.pilha_pular:
            return
        self._escrever(data)


_VAZIAS = {"img", "br", "hr", "meta", "link", "input", "col", "source", "wbr", "area", "base"}


def _limpar(txt: str) -> str:
    return re.sub(r"\s+", " ", txt).strip()


def html_para_texto(arxiv_id: str, html: str) -> TextoPaper:
    ext = _Extrator()
    ext.feed(html)
    ext.close()
    bruto = "".join(ext.partes)
    # Normaliza espacos dentro dos paragrafos, preserva as quebras de bloco.
    blocos = [re.sub(r"[ \t\r\f\v]+", " ", b).strip() for b in re.split(r"\n{2,}", bruto)]
    texto = "\n\n".join(b for b in blocos if b)
    return TextoPaper(arxiv_id=arxiv_id, texto=texto, fonte="html", secoes=ext.secoes,
                      tabelas=ext.tabelas, chegou_ao_fim=True)


def aplicar_teto(tp: TextoPaper, teto: int) -> TextoPaper:
    """Corta no ultimo titulo que cabe inteiro antes do teto."""
    if teto <= 0 or len(tp.texto) <= teto:
        return tp
    corte = tp.texto.rfind("\n\n#", 0, teto)
    if corte < teto // 2:
        corte = tp.texto.rfind("\n\n", 0, teto)
    corte = corte if corte > 0 else teto
    resto = tp.texto[:corte]
    titulos = re.findall(r"^#{2,6} (.+)$", resto, flags=re.M)
    tp.texto = resto
    tp.cortado_em = titulos[-1] if titulos else None
    tp.chegou_ao_fim = False
    return tp


def baixar_html(arxiv_id: str, cliente: Optional[httpx.Client] = None) -> Optional[str]:
    """HTML do arXiv, ou None quando o paper nao tem versao HTML (404)."""
    proprio = cliente is None
    http = cliente or httpx.Client(timeout=60, follow_redirects=True,
                                   headers={"User-Agent": "hf-papers-db/0.1 (leitura)"})
    try:
        r = http.get(URL_HTML.format(id=arxiv_id))
        if r.status_code == 404:
            return None
        r.raise_for_status()
        # Sem conversao o arXiv responde 200 com uma pagina de aviso.
        if "ltx_document" not in r.text and "ltx_page_main" not in r.text:
            return None
        return r.text
    finally:
        if proprio:
            http.close()


def texto_do_paper(arxiv_id: str, *, abstract: str = "", teto: int = 320_000,
                   cliente: Optional[httpx.Client] = None) -> TextoPaper:
    html = baixar_html(arxiv_id, cliente)
    if html is None:
        return TextoPaper(arxiv_id=arxiv_id, texto=abstract or "", fonte="abstract",
                          chegou_ao_fim=False)
    return aplicar_teto(html_para_texto(arxiv_id, html), teto)


# ── conferencia de trechos e numeros ────────────────────────────────────────


def normalizar(txt: str) -> str:
    """Forma usada para conferir um trecho contra o texto: sem caixa, sem
    hifenizacao, aspas e tracos unificados, espacos colapsados."""
    t = txt.lower()
    t = t.replace("­", "")
    t = re.sub(r"[‘’‛`´]", "'", t)
    t = re.sub(r"[“”„]", '"', t)
    t = re.sub(r"[‐-―−]", "-", t)
    t = re.sub(r"\$[^$]{0,80}\$", " ", t)  # formulas viram espaco nos dois lados
    t = re.sub(r"[^\w%.,;:'\"()\-+/ ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


class Conferidor:
    """Confere trechos e numeros contra o texto que o modelo recebeu."""

    def __init__(self, texto: str) -> None:
        self.norm = normalizar(texto)
        self.numeros = set(_numeros(texto))

    def trecho(self, trecho: Optional[str]) -> Optional[bool]:
        if not trecho:
            return None
        n = normalizar(trecho).strip(" .\"'")
        if len(n) < 8:
            return n in self.norm
        if n in self.norm:
            return True
        # Reticencias do modelo: cada pedaco precisa estar no texto, em ordem.
        pedacos = [normalizar(p).strip(" .\"'") for p in re.split(r"\.\.\.|…", trecho)]
        pedacos = [p for p in pedacos if len(p) >= 8]
        if len(pedacos) > 1:
            pos = 0
            for p in pedacos:
                i = self.norm.find(p, pos)
                if i < 0:
                    return False
                pos = i + len(p)
            return True
        return False

    def numero(self, valor: object) -> Optional[bool]:
        try:
            v = float(valor)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None
        return any(abs(v - n) <= 1e-9 + abs(n) * 1e-6 for n in self.numeros) or \
            any(abs(v - n * 100) < 1e-6 for n in self.numeros if abs(n) <= 1) or \
            any(abs(v * 100 - n) < 1e-6 for n in self.numeros if abs(v) <= 1)


def _numeros(texto: str) -> list[float]:
    out = []
    for m in re.finditer(r"(?<![\w.])[-−]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|(?<![\w.])[-−]?\d+(?:\.\d+)?", texto):
        s = m.group(0).replace("−", "-").replace(",", "")
        try:
            out.append(float(s))
        except ValueError:
            pass
    return out
