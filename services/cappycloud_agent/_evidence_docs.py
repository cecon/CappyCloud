"""Busca de documentação externa para a coleta automática de evidências."""

from __future__ import annotations

import httpx

from ._evidence_models import _ConfluenceSource, _DocHit, _DocSearchAttempt
from ._evidence_utils import _clean_labels, _trim

_DOC_RESULTS_PER_TERM = 3
_DOC_TERMS_LIMIT = 2


async def _fetch_docs(
    client: httpx.AsyncClient,
    session_url: str,
    repos: list[dict],
    terms: list[str],
) -> tuple[list[_DocHit], list[_DocSearchAttempt]]:
    confluence_sources = _confluence_sources(repos)
    if not confluence_sources:
        return ([], [])
    primary_sources = [_without_labels(source) for source in confluence_sources]
    attempts: list[_DocSearchAttempt] = []
    hits: list[_DocHit] = []
    for source in primary_sources:
        for term in terms[:_DOC_TERMS_LIMIT]:
            attempts.append(_DocSearchAttempt(term, source))
            try:
                hits.extend(await _fetch_docs_for(client, session_url, source, term))
            except Exception:
                continue
            if hits:
                return (_unique_docs(hits)[:8], attempts)
    if not hits:
        label_sources = [source for source in confluence_sources if source.labels]
        for source in label_sources:
            for term in terms[:_DOC_TERMS_LIMIT]:
                attempts.append(_DocSearchAttempt(term, source))
                try:
                    hits.extend(await _fetch_docs_for(client, session_url, source, term))
                except Exception:
                    continue
                if hits:
                    return (_unique_docs(hits)[:8], attempts)
    return (_unique_docs(hits)[:8], attempts)


async def _fetch_docs_for(
    client: httpx.AsyncClient,
    session_url: str,
    source: _ConfluenceSource,
    term: str,
) -> list[_DocHit]:
    params = {
        "base_url": source.base_url,
        "q": term,
        "limit": str(_DOC_RESULTS_PER_TERM),
    }
    if source.space:
        params["space"] = source.space
    if source.labels:
        params["labels"] = ",".join(source.labels)
    resp = await client.get(
        f"{session_url.rstrip('/')}/confluence/search",
        params=params,
    )
    if resp.status_code != 200:
        return []
    data = resp.json()
    items = data.get("results") or data.get("items") or []
    hits: list[_DocHit] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("name") or "").strip()
        url = str(
            item.get("url") or item.get("web_url") or item.get("link") or ""
        ).strip()
        summary = str(
            item.get("summary") or item.get("excerpt") or item.get("content") or ""
        )
        if title:
            hits.append(_DocHit(term, title, url, _trim(summary)))
    return hits


def _confluence_sources(repos: list[dict]) -> list[_ConfluenceSource]:
    sources: list[_ConfluenceSource] = []
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    for repo in repos or []:
        base_url = str(repo.get("confluence_url") or "").strip().rstrip("/")
        space = str(repo.get("confluence_space") or "").strip()
        labels = tuple(_clean_labels(repo.get("confluence_labels")))
        key = (base_url, space, labels)
        if base_url and key not in seen:
            seen.add(key)
            sources.append(_ConfluenceSource(base_url, space, labels))
    return sources


def _without_labels(source: _ConfluenceSource) -> _ConfluenceSource:
    return _ConfluenceSource(source.base_url, source.space, ())


def _unique_docs(hits: list[_DocHit]) -> list[_DocHit]:
    seen: set[tuple[str, str]] = set()
    out: list[_DocHit] = []
    for hit in hits:
        key = (hit.title.lower(), hit.url)
        if key not in seen:
            seen.add(key)
            out.append(hit)
    return out
