"""Read-only Confluence helpers for the stdio MCP server."""

from __future__ import annotations

import base64
import html
import os
import re
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

import requests

SERVER_NAME = "cappycloud-confluence"
SERVER_VERSION = "0.1.0"
MAX_TEXT_CHARS = 18_000


def _base_url() -> str:
    base = os.getenv("CONFLUENCE_BASE_URL", "").strip().rstrip("/")
    if not base:
        raise RuntimeError("CONFLUENCE_BASE_URL não configurada")
    return base


def _rest_base() -> str:
    base = _base_url()
    if base.endswith("/rest/api"):
        return base
    return f"{base}/rest/api"


def _headers() -> dict[str, str]:
    headers = {"Accept": "application/json", "User-Agent": f"{SERVER_NAME}/{SERVER_VERSION}"}
    pat = os.getenv("CONFLUENCE_PAT", "").strip()
    email = os.getenv("CONFLUENCE_EMAIL", "").strip()
    token = os.getenv("CONFLUENCE_API_TOKEN", "").strip()
    if pat:
        headers["Authorization"] = f"Bearer {pat}"
    elif email and token:
        raw = base64.b64encode(f"{email}:{token}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {raw}"
    return headers


def _strip_html(value: str) -> str:
    value = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", value or "")
    value = re.sub(r"(?i)<br\s*/?>", "\n", value)
    value = re.sub(r"(?i)</(p|div|h[1-6]|li|tr)>", "\n", value)
    value = re.sub(r"(?s)<[^>]+>", " ", value)
    value = html.unescape(value)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _clip(value: str, limit: int = MAX_TEXT_CHARS) -> str:
    value = value.strip()
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + "\n...[truncado]"


def _page_id_from_url(url_or_id: str) -> str:
    value = str(url_or_id or "").strip()
    if not value:
        raise ValueError("Informe page_id ou URL da página")
    if re.fullmatch(r"\d+", value):
        return value

    parsed = urlparse(value)
    if parsed.netloc:
        configured = urlparse(_base_url())
        if configured.netloc and parsed.netloc != configured.netloc:
            raise ValueError("URL fora do Confluence configurado")
        qs = parse_qs(parsed.query)
        if qs.get("pageId"):
            return qs["pageId"][0]
        match = re.search(r"/pages/(\d+)", parsed.path)
        if match:
            return match.group(1)
    raise ValueError("Não consegui extrair page_id da URL")


def _page_id_from_display_url(url: str) -> str:
    parsed = urlparse(url)
    configured = urlparse(_base_url())
    if configured.netloc and parsed.netloc != configured.netloc:
        raise ValueError("URL fora do Confluence configurado")
    resp = requests.get(url, headers=_headers(), timeout=20)
    if resp.status_code >= 400:
        raise RuntimeError(f"Confluence HTTP {resp.status_code}: {resp.text[:500]}")
    match = re.search(r'<meta\s+name="ajs-page-id"\s+content="(\d+)"', resp.text, re.I)
    if not match:
        raise ValueError("Não consegui extrair page_id da página HTML")
    return match.group(1)


def _resolve_page_id(url_or_id: str) -> str:
    try:
        return _page_id_from_url(url_or_id)
    except ValueError:
        value = str(url_or_id or "").strip()
        if not value:
            raise
        return _page_id_from_display_url(value)


def _get_json(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    resp = requests.get(url, headers=_headers(), params=params, timeout=20)
    if resp.status_code == 401:
        raise RuntimeError("Confluence retornou 401. Verifique email/token/PAT.")
    if resp.status_code == 403:
        raise RuntimeError("Confluence retornou 403. Credencial sem permissão para esta página/space.")
    if resp.status_code >= 400:
        raise RuntimeError(f"Confluence HTTP {resp.status_code}: {resp.text[:500]}")
    return resp.json()


def _site_search(query: str, limit: int, space: str = "") -> tuple[int | None, list[dict[str, Any]]]:
    resp = requests.get(
        f"{_base_url()}/dosearchsite.action",
        headers={**_headers(), "Accept": "text/html,application/xhtml+xml"},
        params={"queryString": query},
        timeout=20,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Confluence HTTP {resp.status_code}: {resp.text[:500]}")

    total_match = re.search(r'data-totalsize="(\d+)"', resp.text)
    total = int(total_match.group(1)) if total_match else None
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    expected_space = (space or "").strip().lower()
    for item_match in re.finditer(r"(?is)<li\b.*?</li>", resp.text):
        item = item_match.group(0)
        link_match = re.search(
            r'(?is)<a\b[^>]*class="[^"]*\bsearch-result-link\b[^"]*"[^>]*href="([^"]+)"[^>]*data-type="([^"]+)"[^>]*>(.*?)</a>',
            item,
        )
        if not link_match:
            continue
        href, content_type, raw_title = link_match.groups()
        if content_type != "page":
            continue
        space_match = re.search(r'(?is)<a class="container"[^>]*>(.*?)</a>', item)
        result_space = _strip_html(space_match.group(1)) if space_match else None
        if expected_space and expected_space != "all" and result_space and result_space.lower() not in {
            expected_space,
            "postos",
        }:
            continue
        result_url = href.replace("&amp;", "&")
        if result_url.startswith("/"):
            result_url = f"{_base_url()}{result_url}"
        if result_url in seen:
            continue
        seen.add(result_url)

        highlight_match = re.search(r'(?is)<div class="highlights">(.*?)</div>', item)
        results.append(
            {
                "id": None,
                "title": _strip_html(raw_title),
                "space": result_space,
                "url": result_url,
                "excerpt": _clip(_strip_html(highlight_match.group(1)) if highlight_match else "", 900),
            }
        )
        if len(results) >= limit:
            break
    return total, results


def _content_text(page: dict[str, Any]) -> str:
    body = page.get("body") or {}
    storage = body.get("storage") or {}
    view = body.get("view") or {}
    storage_text = _strip_html(storage.get("value") or "")
    view_text = _strip_html(view.get("value") or "")
    return view_text if len(view_text) > len(storage_text) else storage_text


def _page_url(page: dict[str, Any]) -> str:
    links = page.get("_links") or {}
    webui = links.get("webui") or ""
    base = links.get("base") or _base_url()
    return f"{base.rstrip('/')}{webui}" if webui.startswith("/") else webui


def confluence_search(arguments: dict[str, Any]) -> dict[str, Any]:
    query = str(arguments.get("query") or "").strip()
    limit = max(1, min(int(arguments.get("limit") or 5), 10))
    space = str(arguments.get("space") or "").strip()
    if not query:
        raise ValueError("query é obrigatório")

    cql = f'type=page AND text ~ "{query.replace(chr(34), chr(92) + chr(34))}"'
    if space:
        cql = f'space="{space}" AND {cql}'
    data = _get_json(
        f"{_rest_base()}/content/search",
        {"cql": cql, "limit": limit, "expand": "body.storage,body.view,version,space"},
    )
    results = [
        {
            "id": item.get("id"),
            "title": item.get("title"),
            "space": (item.get("space") or {}).get("key"),
            "url": _page_url(item),
            "excerpt": _clip(_content_text(item), 900),
        }
        for item in data.get("results", [])
    ]
    source = "rest-cql"
    total: int | None = data.get("size")
    if not results:
        total, results = _site_search(query, limit, space)
        source = "site-search"
    return {"query": query, "source": source, "total": total, "count": len(results), "results": results}


def confluence_get_page(arguments: dict[str, Any]) -> dict[str, Any]:
    page_id = _resolve_page_id(str(arguments.get("page_id") or arguments.get("url") or ""))
    data = _get_json(
        f"{_rest_base()}/content/{quote(page_id)}",
        {"expand": "body.storage,body.view,version,space,ancestors"},
    )
    return {
        "id": data.get("id"),
        "title": data.get("title"),
        "space": (data.get("space") or {}).get("key"),
        "url": _page_url(data),
        "version": (data.get("version") or {}).get("number"),
        "ancestors": [
            {"id": a.get("id"), "title": a.get("title"), "url": _page_url(a)}
            for a in data.get("ancestors", [])
        ],
        "text": _clip(_content_text(data)),
    }


def confluence_get_main_menu(_: dict[str, Any]) -> dict[str, Any]:
    url = os.getenv("CONFLUENCE_MAIN_MENU_URL", "").strip()
    if not url:
        raise RuntimeError("CONFLUENCE_MAIN_MENU_URL não configurada")
    return confluence_get_page({"url": url})
