#!/usr/bin/env python3
"""webread <url> — lê uma página web como texto, para o agente do sandbox.

Muitos sites devolvem 403 para quem não se identifica como navegador, e é
assim que o WebFetch do agente se apresenta. Aqui a página é pedida como
navegador, os redirecionamentos são seguidos e o HTML vira texto.

A central de atendimento da TOTVS (Zendesk atrás do Cloudflare) barra até
navegador quando a conexão vem de um servidor Linux. Por isso artigos de
central Zendesk (``/hc/<idioma>/articles/<id>``) vêm da API pública, que não
é barrada e traz o título e o corpo sem o resto da página.

Uso: webread <url> [--max-chars N]   (padrão 40000)
"""

from __future__ import annotations

import html
import json
import re
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urlsplit

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0 Safari/537.36"
)
ZENDESK_ARTICLE = re.compile(r"^/hc/([a-z]{2}(?:-[a-z]{2})?)/articles/(\d+)", re.IGNORECASE)
BLOCK_TAGS = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "pre", "table"}
SKIP_TAGS = {"script", "style", "noscript", "svg", "head", "nav", "footer"}


class _TextParser(HTMLParser):
    """HTML → texto simples: quebra linha em blocos, ignora script/estilo/menus."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in SKIP_TAGS:
            self._skip += 1
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")
        if tag == "li" and not self._skip:
            self.parts.append("- ")

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TAGS and self._skip:
            self._skip -= 1
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def html_to_text(markup: str) -> str:
    parser = _TextParser()
    parser.feed(markup)
    text = html.unescape("".join(parser.parts))
    text = re.sub(r"[ \t\r\f\v\xa0]+", " ", text)  # &nbsp; vira espaço comum
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def _get(url: str) -> tuple[str, str]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": BROWSER_UA, "Accept": "text/html,application/json;q=0.9,*/*;q=0.8"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.geturl(), response.read().decode(charset, errors="replace")


def zendesk_api_url(url: str) -> str | None:
    parts = urlsplit(url)
    match = ZENDESK_ARTICLE.match(parts.path)
    if not match:
        return None
    return f"{parts.scheme}://{parts.netloc}/api/v2/help_center/{match.group(1).lower()}/articles/{match.group(2)}.json"


def read(url: str) -> str:
    api = zendesk_api_url(url)
    if api:
        try:
            _, body = _get(api)
            article = json.loads(body)["article"]
            return f"# {article['title']}\nFonte: {article['html_url']}\n\n{html_to_text(article['body'])}"
        except (urllib.error.URLError, KeyError, ValueError):
            pass  # não é Zendesk de verdade (ou a API caiu): lê a página normal
    final_url, body = _get(url)
    text = body if body.lstrip().startswith(("{", "[")) else html_to_text(body)
    return f"Fonte: {final_url}\n\n{text}"


def main(argv: list[str]) -> int:
    if not argv or argv[0] in {"-h", "--help"}:
        print(__doc__)
        return 0 if argv else 2
    max_chars = 40_000
    if "--max-chars" in argv:
        index = argv.index("--max-chars")
        max_chars = int(argv[index + 1])
        argv = argv[:index] + argv[index + 2 :]
    try:
        text = read(argv[0])
    except urllib.error.HTTPError as exc:
        print(f"webread: HTTP {exc.code} em {argv[0]}", file=sys.stderr)
        return 1
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"webread: falha ao acessar {argv[0]}: {exc}", file=sys.stderr)
        return 1
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n\n[… cortado em {max_chars} caracteres; use --max-chars]"
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
