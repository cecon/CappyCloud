"""Coleta automática de evidências antes de chamar o LLM.

O objetivo é reduzir dependência de disciplina do modelo. Para perguntas de
suporte, o coordenador deve receber uma amostra inicial de documentação e código
mesmo quando ele não escolhe chamar as tools corretas.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass

import httpx

from ._agent_context import inject_section_before_user_message

_MAX_TERMS = 6
_CODE_MATCHES_PER_TERM = 8
_DOC_RESULTS_PER_TERM = 3
_TEXT_LIMIT = 220


@dataclass(frozen=True)
class _CodeHit:
    query: str
    repo: str
    path: str
    line: int
    text: str


@dataclass(frozen=True)
class _DocHit:
    query: str
    title: str
    url: str
    summary: str


async def inject_evidence_prefetch(
    prompt: str,
    *,
    user_message: str,
    sandbox_session_url: str,
    repos: list[dict],
    session_root: str,
) -> str:
    """Busca evidências em documentação e código e injeta antes da mensagem.

    Falha de rede, Confluence ou busca local nunca bloqueia a execução do
    agente; nesse caso apenas não injeta a seção.
    """
    terms = _terms_for(user_message)
    if not terms or not sandbox_session_url:
        return prompt

    async with httpx.AsyncClient(timeout=httpx.Timeout(12.0)) as client:
        docs_task = asyncio.create_task(_fetch_docs(client, sandbox_session_url, terms))
        code_task = asyncio.create_task(
            _fetch_code(client, sandbox_session_url, repos, session_root, terms)
        )
        docs, code = await asyncio.gather(docs_task, code_task)

    section = _render_section(docs, code)
    if not section:
        return prompt
    return inject_section_before_user_message(prompt, section)


def _terms_for(message: str) -> list[str]:
    marker = "## Mensagem do utilizador"
    if marker in message:
        message = message.split(marker, 1)[1]
    raw = message.lower()
    terms: list[str] = []

    quoted = re.findall(r'"([^"]{3,60})"', message)
    terms.extend(q.strip() for q in quoted)

    domain_pairs = [
        "shell select",
        "shell box",
        "promoção",
        "promocao",
        "bloqueio",
        "bloqueado",
        "permite_venda_dist",
        "data_bloq_venda",
        "pdv",
        "venda",
    ]
    for term in domain_pairs:
        if term in raw:
            terms.append(term)

    # Tokens técnicos úteis: identificadores, palavras acentuadas normalizadas
    # e termos de domínio com tamanho suficiente.
    for token in re.findall(r"[a-zA-Z_][\w_]{3,}", message):
        if token.lower() in {"autosystem", "investigue", "evidência", "documentação"}:
            continue
        terms.append(token)

    return _dedupe(terms)[:_MAX_TERMS]


async def _fetch_docs(
    client: httpx.AsyncClient,
    session_url: str,
    terms: list[str],
) -> list[_DocHit]:
    tasks = [_fetch_docs_for(client, session_url, term) for term in terms[:4]]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    hits: list[_DocHit] = []
    for result in results:
        if isinstance(result, list):
            hits.extend(result)
    return _unique_docs(hits)[:8]


async def _fetch_docs_for(
    client: httpx.AsyncClient,
    session_url: str,
    term: str,
) -> list[_DocHit]:
    resp = await client.get(
        f"{session_url.rstrip('/')}/confluence/search",
        params={"q": term, "limit": str(_DOC_RESULTS_PER_TERM)},
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
        url = str(item.get("url") or item.get("web_url") or item.get("link") or "").strip()
        summary = str(item.get("summary") or item.get("excerpt") or item.get("content") or "")
        if title:
            hits.append(_DocHit(term, title, url, _trim(summary)))
    return hits


async def _fetch_code(
    client: httpx.AsyncClient,
    session_url: str,
    repos: list[dict],
    session_root: str,
    terms: list[str],
) -> list[_CodeHit]:
    tasks = []
    for repo in repos:
        worktree = _worktree_path(repo, session_root)
        if not worktree:
            continue
        repo_name = str(repo.get("slug") or repo.get("alias") or worktree)
        for term in terms:
            tasks.append(_fetch_code_for(client, session_url, worktree, repo_name, term))
    results = await asyncio.gather(*tasks, return_exceptions=True)
    hits: list[_CodeHit] = []
    for result in results:
        if isinstance(result, list):
            hits.extend(result)
    return _unique_code(hits)[:18]


async def _fetch_code_for(
    client: httpx.AsyncClient,
    session_url: str,
    worktree: str,
    repo_name: str,
    term: str,
) -> list[_CodeHit]:
    resp = await client.post(
        f"{session_url.rstrip('/')}/worktree/search",
        json={"worktree_path": worktree, "query": term, "limit": _CODE_MATCHES_PER_TERM},
    )
    if resp.status_code != 200:
        return []
    hits: list[_CodeHit] = []
    for item in resp.json().get("matches") or []:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip()
        text = str(item.get("text") or "").strip()
        if path and text:
            hits.append(_CodeHit(term, repo_name, path, int(item.get("line") or 0), _trim(text)))
    return hits


def _render_section(docs: list[_DocHit], code: list[_CodeHit]) -> str:
    if not docs and not code:
        return ""
    parts = [
        "## Evidências coletadas automaticamente",
        "Use esta amostra como ponto de partida obrigatório. Se ela for insuficiente, "
        "continue investigando com Confluence, Grep e Read antes da resposta final. "
        "Não cite itens abaixo como conclusão sem validar o conteúdo relevante.",
    ]
    if docs:
        parts.append("### Documentação encontrada")
        parts.extend(
            f"- `{hit.query}` → {hit.title}"
            + (f" ({hit.url})" if hit.url else "")
            + (f": {hit.summary}" if hit.summary else "")
            for hit in docs
        )
    if code:
        parts.append("### Código encontrado")
        parts.extend(
            f"- `{hit.query}` → {hit.repo}:{hit.path}:{hit.line}: {hit.text}"
            for hit in code
        )
    return "\n".join(parts)


def _worktree_path(repo: dict, session_root: str) -> str:
    wt = str(repo.get("worktree_path") or "").strip()
    if wt:
        return wt
    alias = str(repo.get("alias") or repo.get("slug") or "").strip()
    return f"{session_root.rstrip('/')}/{alias}" if session_root and alias else ""


def _trim(text: str) -> str:
    one_line = " ".join(str(text).split())
    return one_line[:_TEXT_LIMIT]


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        value = item.strip()
        key = value.lower()
        if value and key not in seen:
            seen.add(key)
            out.append(value)
    return out


def _unique_docs(hits: list[_DocHit]) -> list[_DocHit]:
    seen: set[tuple[str, str]] = set()
    out: list[_DocHit] = []
    for hit in hits:
        key = (hit.title.lower(), hit.url)
        if key not in seen:
            seen.add(key)
            out.append(hit)
    return out


def _unique_code(hits: list[_CodeHit]) -> list[_CodeHit]:
    seen: set[tuple[str, int, str]] = set()
    out: list[_CodeHit] = []
    for hit in hits:
        key = (hit.path, hit.line, hit.text)
        if key not in seen:
            seen.add(key)
            out.append(hit)
    return out
