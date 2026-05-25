"""Busca de documentação externa para a coleta automática de evidências."""

from __future__ import annotations

import re

import httpx

from ._evidence_models import _ConfluenceSource, _DocHit, _DocSearchAttempt
from ._evidence_utils import _clean_labels, _dedupe, _trim

_DOC_RESULTS_PER_TERM = 3
_DOC_TERMS_LIMIT = 2
_REPO_DOC_RESULTS_PER_QUERY = 4
_REPO_DOC_QUERIES_LIMIT = 4
_REPO_DOC_SNIPPET_LIMIT = 2000
_REPO_DOC_EXPANSION_QUERIES_LIMIT = 4

_BARE_TABLE_RE = re.compile(
    r"(?<![\w.])(?:tg|te|tp|external_|bko[-_\w]*_tg)[A-Za-z0-9_-]*\b",
    re.IGNORECASE,
)
_TABLE_QUERY_HINTS = {
    "empresa": ("empr", "empresa"),
    "empresas": ("empr", "empresa"),
    "produto": ("prod", "prd"),
    "produtos": ("prod", "prd"),
    "imposto": ("impo", "aliq", "trib"),
    "impostos": ("impo", "aliq", "trib"),
    "tributo": ("impo", "aliq", "trib"),
    "tributos": ("impo", "aliq", "trib"),
    "venda": ("vend", "vnd", "fisvend"),
    "vendas": ("vend", "vnd", "fisvend"),
    "cliente": ("gene", "cliente"),
    "clientes": ("gene", "cliente"),
}


async def _fetch_docs(
    client: httpx.AsyncClient,
    session_url: str,
    repos: list[dict],
    terms: list[str],
    user_message: str = "",
) -> tuple[list[_DocHit], list[_DocSearchAttempt]]:
    repo_hits = await _fetch_repo_docs(client, session_url, repos, terms, user_message)
    confluence_sources = _confluence_sources(repos)
    if not confluence_sources:
        return (_unique_docs(repo_hits)[:8], [])
    primary_sources = [_without_labels(source) for source in confluence_sources]
    attempts: list[_DocSearchAttempt] = []
    hits: list[_DocHit] = list(repo_hits)
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
                    hits.extend(
                        await _fetch_docs_for(client, session_url, source, term)
                    )
                except Exception:
                    continue
                if hits:
                    return (_unique_docs(hits)[:8], attempts)
    return (_unique_docs(hits)[:8], attempts)


async def _fetch_repo_docs(
    client: httpx.AsyncClient,
    session_url: str,
    repos: list[dict],
    terms: list[str],
    user_message: str = "",
) -> list[_DocHit]:
    repo_ids = _repo_ids(repos)
    if not repo_ids:
        return []
    hits: list[_DocHit] = []
    initial_queries = _repo_doc_queries(terms, user_message)
    for query in initial_queries:
        try:
            hits.extend(
                await _fetch_repo_docs_for(client, session_url, repo_ids, query)
            )
        except Exception:
            continue
    expansion_hits: list[_DocHit] = []
    seen_queries = set(initial_queries)
    for query in _repo_doc_expansion_queries(_unique_docs(hits), user_message):
        if query in seen_queries:
            continue
        seen_queries.add(query)
        try:
            expansion_hits.extend(
                await _fetch_repo_docs_for(client, session_url, repo_ids, query)
            )
        except Exception:
            continue
    return _unique_docs(expansion_hits + hits)


async def _fetch_repo_docs_for(
    client: httpx.AsyncClient,
    session_url: str,
    repo_ids: list[str],
    query: str,
) -> list[_DocHit]:
    params: list[tuple[str, str]] = [
        ("q", query[:512]),
        ("limit", str(_REPO_DOC_RESULTS_PER_QUERY)),
    ]
    params.extend(("repo_id", repo_id) for repo_id in repo_ids)
    resp = await client.get(
        f"{session_url.rstrip('/')}/skills/search",
        params=params,
    )
    if resp.status_code != 200:
        return []
    data = resp.json()
    items = (
        data
        if isinstance(data, list)
        else data.get("results") or data.get("items") or []
    )
    hits: list[_DocHit] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("name") or "").strip()
        source_url = str(item.get("source_url") or item.get("url") or "").strip()
        raw_summary = str(item.get("summary") or item.get("content") or "")
        if not _matches_mentioned_table(raw_summary, query):
            continue
        summary = _focus_repo_doc_summary(raw_summary, query)
        if title:
            hits.append(
                _DocHit(
                    query=query,
                    title=title,
                    url=source_url,
                    summary=_trim(summary, _REPO_DOC_SNIPPET_LIMIT),
                    source="repository_document",
                )
            )
    return hits


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


def _repo_ids(repos: list[dict]) -> list[str]:
    values: list[str] = []
    for repo in repos or []:
        raw = str(repo.get("repo_id") or repo.get("id") or "").strip()
        if raw:
            values.append(raw)
    return _dedupe(values)


def _repo_doc_queries(terms: list[str], user_message: str) -> list[str]:
    candidates: list[str] = []
    user_query = _user_query(user_message)
    if user_query:
        candidates.append(user_query)
        candidates.extend(_table_terms(user_query))
    if terms:
        candidates.append(" ".join(terms))
    candidates.extend(terms)
    return [
        query for query in _dedupe(candidates) if query and len(query.strip()) >= 3
    ][:_REPO_DOC_QUERIES_LIMIT]


def _repo_doc_expansion_queries(hits: list[_DocHit], user_message: str) -> list[str]:
    user_query = _user_query(user_message)
    tables = _ranked_table_mentions(hits, user_query)
    return tables[:_REPO_DOC_EXPANSION_QUERIES_LIMIT]


def _ranked_table_mentions(hits: list[_DocHit], user_query: str) -> list[str]:
    scored: dict[str, tuple[int, int, str]] = {}
    position = 0
    for hit in hits:
        for table in _table_mentions(hit.summary):
            key = table.lower()
            score = _table_query_score(table, user_query)
            current = scored.get(key)
            if current is None or (score, -position) > (current[0], -current[1]):
                scored[key] = (score, position, table)
            position += 1
    ordered = sorted(
        scored.values(),
        key=lambda item: (-item[0], item[1], item[2]),
    )
    return [table for _, _, table in ordered]


def _table_mentions(text: str) -> list[str]:
    candidates = _table_terms(text)
    for raw in _BARE_TABLE_RE.findall(text):
        table = raw.rstrip("*.,;:)")
        if table.lower().startswith("dbo."):
            candidates.append(table)
        else:
            candidates.append(f"dbo.{table}")
    return _dedupe(candidates)


def _table_query_score(table: str, user_query: str) -> int:
    table_lower = table.lower()
    query_lower = user_query.lower()
    score = 0
    for keyword, fragments in _TABLE_QUERY_HINTS.items():
        if keyword not in query_lower:
            continue
        if any(fragment in table_lower for fragment in fragments):
            score += 20
    if table_lower in query_lower:
        score += 50
    return score


def _user_query(user_message: str) -> str:
    marker = "## Mensagem do utilizador"
    if marker in user_message:
        user_message = user_message.split(marker, 1)[1]
    return " ".join(user_message.split())


def _focus_repo_doc_summary(summary: str, query: str) -> str:
    for table in _table_terms(query):
        match = _table_heading_match(summary, table)
        if not match:
            continue
        start = match.start()
        end = summary.find("\n#### ", match.end())
        return summary[start : end if end != -1 else len(summary)]
    return summary


def _matches_mentioned_table(summary: str, query: str) -> bool:
    tables = _table_terms(query)
    if not tables:
        return True
    return any(_table_heading_match(summary, table) for table in tables)


def _table_heading_match(summary: str, table: str) -> re.Match[str] | None:
    return re.search(
        rf"^####\s+{re.escape(table)}\b.*$", summary, re.IGNORECASE | re.MULTILINE
    )


def _table_terms(query: str) -> list[str]:
    return _dedupe(re.findall(r"\bdbo\.[A-Za-z0-9_-]+\b", query))


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
    seen: set[tuple[str, str, str]] = set()
    out: list[_DocHit] = []
    for hit in hits:
        key = (hit.source, hit.title.lower(), hit.url)
        if key not in seen:
            seen.add(key)
            out.append(hit)
    return out
