"""Importador de Skills a partir de URLs (HTML → markdown).

Estratégia:
1. Faz GET na URL com user-agent de browser comum
2. Procura o "main content" usando heurísticas simples (Confluence, GitHub,
   docs sites comuns)
3. Converte HTML → Markdown via ``markdownify``
4. Extrai um título sensato do <title> ou primeira heading
5. Gera resumo curto (primeiros ~300 chars de texto plano)
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup, Tag
from markdownify import markdownify as md

log = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
)

# Selectores comuns de "main content" por dominio/plataforma.
_MAIN_SELECTORS: list[tuple[str, str]] = [
    ("id", "main-content"),
    ("class", "wiki-content"),
    ("class", "markdown-body"),
    ("role", "main"),
    ("id", "content"),
    ("class", "content"),
    ("class", "doc"),
    ("class", "documentation"),
]


def _find_first(soup: BeautifulSoup | Tag, attr: str, value: str) -> Tag | None:
    """Encontra o primeiro Tag com determinado atributo, sem rebentar com mypy."""
    matches = soup.find_all(attrs={attr: value})
    for el in matches:
        if isinstance(el, Tag):
            return el
    return None


class ImporterError(RuntimeError):
    """Erro ao importar URL."""


def _slugify(text: str, max_len: int = 80) -> str:
    text = (text or "").lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:max_len] or "skill"


_STRIP_BY_ID: list[str] = [
    "title-heading",
    "breadcrumb-section",
    "labels-section",
    "comments-section",
    "footer",
]
_STRIP_BY_CLASS: list[str] = ["aui-page-header", "aui-sidebar", "footer-body"]


def _strip(soup: BeautifulSoup) -> None:
    """Remove elementos que não fazem parte do conteúdo (nav, footer, scripts…)."""
    for tag in soup(["script", "style", "nav", "footer", "aside", "noscript", "iframe"]):
        tag.decompose()
    for el_id in _STRIP_BY_ID:
        for el in soup.find_all(id=el_id):
            el.decompose()
    for cls in _STRIP_BY_CLASS:
        for el in soup.find_all(class_=cls):
            el.decompose()


def _pick_main(soup: BeautifulSoup) -> Tag:
    for attr, value in _MAIN_SELECTORS:
        el = _find_first(soup, attr, value)
        if el is not None and len(el.get_text(strip=True)) > 200:
            return el
    for tag_name in ("article", "main", "body"):
        el = soup.find(tag_name)
        if isinstance(el, Tag):
            return el
    body = soup.body
    return body if isinstance(body, Tag) else Tag(name="div")


def _extract_title(soup: BeautifulSoup, main: Tag) -> str:
    h1 = main.find("h1")
    if isinstance(h1, Tag) and h1.get_text(strip=True):
        return h1.get_text(strip=True)[:480]
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
        # Confluence: "Title - Space - Site" → mantém só o primeiro
        return title.split(" - ")[0][:480]
    return "Sem título"


def _summary(text: str, limit: int = 320) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "…"


async def import_url(url: str) -> dict:
    """Faz fetch + extracção e devolve dict com title/slug/summary/content/source_url."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ImporterError("URL inválido (apenas http/https)")

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
            headers={"User-Agent": _USER_AGENT, "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"},
        ) as client:
            r = await client.get(url)
            if r.status_code >= 400:
                raise ImporterError(f"HTTP {r.status_code} ao buscar URL")
            html = r.text
    except httpx.HTTPError as exc:
        raise ImporterError(f"Erro ao buscar URL: {exc}") from exc

    soup = BeautifulSoup(html, "html.parser")
    _strip(soup)
    main = _pick_main(soup)
    title = _extract_title(soup, main)

    markdown = md(str(main), heading_style="ATX", bullets="-").strip()
    # Limita tamanho (skills muito longas viram tokens demais).
    if len(markdown) > 200_000:
        markdown = markdown[:200_000] + "\n\n…(truncado)"

    text_plain = main.get_text(separator=" ", strip=True)
    summary = _summary(text_plain)
    slug = _slugify(title)

    return {
        "title": title,
        "slug": slug,
        "summary": summary,
        "content": markdown,
        "source_url": url,
    }
