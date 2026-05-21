"""Coleta automática de evidências antes de chamar o LLM."""

from __future__ import annotations

import asyncio

import httpx

from ._agent_context import inject_section_before_user_message
from ._evidence_code import (
    _active_parameter_dirs,
    _fetch_code,
    _fetch_parameter_code,
    _fetch_parameter_directories,
    _parameter_dirs_from_files,
)
from ._evidence_docs import _confluence_sources, _fetch_docs
from ._evidence_models import (
    _ConfluenceSource,
    _DocHit,
    _DocSearchAttempt,
)
from ._evidence_render import (
    _parameter_doc_result_lines,
    _parameter_lookup_guard,
    _render_section,
)
from ._evidence_terms import _parameter_numbers, _terms_for

__all__ = [
    "_ConfluenceSource",
    "_DocHit",
    "_DocSearchAttempt",
    "_active_parameter_dirs",
    "_confluence_sources",
    "_parameter_dirs_from_files",
    "_parameter_doc_result_lines",
    "_parameter_lookup_guard",
    "_parameter_numbers",
    "_render_section",
    "_terms_for",
    "inject_evidence_prefetch",
]


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

    parameter_numbers = _parameter_numbers(user_message)
    doc_terms = parameter_numbers or terms
    async with httpx.AsyncClient(timeout=httpx.Timeout(50.0)) as client:
        docs_task = asyncio.create_task(
            _fetch_docs(client, sandbox_session_url, repos, doc_terms)
        )
        if parameter_numbers:
            parameter_dirs = await _fetch_parameter_directories(
                client,
                sandbox_session_url,
                repos,
                session_root,
            )
            docs, doc_attempts = await docs_task
            code = await _fetch_parameter_code(
                client,
                sandbox_session_url,
                parameter_dirs,
                parameter_numbers,
            )
            parameter_guard = _parameter_lookup_guard(
                user_message,
                repos,
                session_root,
                parameter_dirs,
                docs,
                doc_attempts,
            )
        else:
            code_task = asyncio.create_task(
                _fetch_code(client, sandbox_session_url, repos, session_root, terms)
            )
            (docs, doc_attempts), code = await asyncio.gather(docs_task, code_task)
            parameter_guard = ""

    evidence_section = _render_section(docs, code, doc_attempts)
    section = "\n\n".join(part for part in (parameter_guard, evidence_section) if part)
    if not section:
        return prompt
    return inject_section_before_user_message(prompt, section)
