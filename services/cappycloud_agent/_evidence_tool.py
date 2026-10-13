"""Ferramentas de evidência do agente: a antiga busca prévia, sob demanda.

Antes, a API buscava código, documentação, memória e grafo antes de todo turno
e colava o resultado no prompt: até ~17 s e dezenas de milhares de tokens
mesmo para um "ok". Agora o modelo chama estas buscas quando precisa (servidor
MCP ``cappy`` do sandbox) e recebe só nomes: caminho do arquivo, título e URL
do documento. Ele mesmo decide o que abrir.

Sem dependências além do httpx e dos módulos ``_evidence_*``: este arquivo é
copiado para a imagem do sandbox.
"""

from __future__ import annotations

import asyncio

import httpx

from ._evidence_code import (
    _fetch_code,
    _fetch_parameter_code,
    _fetch_parameter_directories,
)
from ._evidence_docs import _fetch_docs
from ._evidence_models import _CodeHit, _DocHit
from ._evidence_terms import _parameter_numbers, _terms_for
from ._evidence_utils import _worktree_path
from ._knowledge_search import query_graph, question_text, safe, search_memory
from ._workspace_paths import workspace_root_of

_TIMEOUT_S = 50.0
_KNOWLEDGE_TIMEOUT_S = 15.0
_MAX_FILES = 20
_MAX_DOCS = 8
_EXCERPT_CHARS = 300
_MEMORY_CHARS = 300
_GRAPH_BUDGET = 400
_REPO_KEYS = (
    "slug",
    "alias",
    "worktree_path",
    "repo_id",
    "id",
    "confluence_url",
    "confluence_space",
    "confluence_labels",
)


def evidence_tool_context(repos: list[dict], session_root: str) -> dict:
    """O que o MCP ``cappy`` precisa saber da conversa, só com tipos JSON."""
    clean: list[dict] = []
    for repo in repos:
        item: dict = {}
        for key in _REPO_KEYS:
            value = repo.get(key)
            if value is None or value == "":
                continue
            item[key] = [str(v) for v in value] if isinstance(value, list | tuple) else str(value)
        clean.append(item)
    return {"repos": clean, "session_root": session_root}


async def find_evidence(
    question: str,
    *,
    session_url: str,
    repos: list[dict],
    session_root: str,
    with_excerpts: bool = False,
) -> str:
    """Arquivos de código e documentos ligados à pergunta, só pelo nome."""
    terms = _terms_for(question)
    if not terms:
        return (
            "Nenhum termo pesquisável na pergunta. Passe nomes concretos: tabela, "
            "função, parâmetro, mensagem de erro ou tela."
        )
    numbers = _parameter_numbers(question)
    parameter_dirs = []
    async with httpx.AsyncClient(timeout=httpx.Timeout(_TIMEOUT_S)) as client:
        docs_task = asyncio.create_task(
            _fetch_docs(client, session_url, repos, numbers or terms, user_message=question)
        )
        if numbers:
            parameter_dirs = await _fetch_parameter_directories(
                client, session_url, repos, session_root
            )
            code = await _fetch_parameter_code(client, session_url, parameter_dirs, numbers)
        else:
            code = await _fetch_code(client, session_url, repos, session_root, terms)
        docs, _attempts = await docs_task

    worktrees = {
        str(repo.get("slug") or repo.get("alias") or ""): _worktree_path(repo, session_root)
        for repo in repos
    }
    lines = [f"Busca por: {', '.join(numbers or terms)}"]
    if parameter_dirs:
        lines += ["", "## Diretórios de parâmetros (procure o número só aqui)"]
        lines += [f"- {directory.path}" for directory in parameter_dirs]
    lines += _code_lines(code, worktrees, with_excerpts)
    lines += _doc_lines(docs, with_excerpts)
    if not code and not docs:
        lines += ["", "Nada encontrado no código nem na documentação para esses termos."]
    elif not with_excerpts:
        lines += [
            "",
            "Abra com Read só os arquivos que importam. Documento importado não é "
            "arquivo: chame de novo com com_trechos=true para ver o conteúdo.",
        ]
    return "\n".join(lines)


def _absolute(hit: _CodeHit, worktrees: dict[str, str]) -> str:
    if hit.path.startswith("/"):
        return hit.path
    root = worktrees.get(hit.repo, "")
    return f"{root.rstrip('/')}/{hit.path}" if root else hit.path


def _code_lines(code: list[_CodeHit], worktrees: dict[str, str], excerpts: bool) -> list[str]:
    files: dict[str, list[_CodeHit]] = {}
    for hit in code:
        files.setdefault(_absolute(hit, worktrees), []).append(hit)
    if not files:
        return []
    lines = ["", f"## Código ({len(files)} arquivos)"]
    for path, hits in list(files.items())[:_MAX_FILES]:
        found = ", ".join(dict.fromkeys(hit.query for hit in hits))
        lines.append(f"- {path} (termos: {found})")
        if excerpts:
            for hit in hits[:3]:
                lines.append(f"    {hit.line}: {hit.text[:_EXCERPT_CHARS]}")
    return lines


def _doc_lines(docs: list[_DocHit], excerpts: bool) -> list[str]:
    if not docs:
        return []
    lines = ["", "## Documentação"]
    for doc in docs[:_MAX_DOCS]:
        kind = "documento importado" if doc.source == "repository_document" else "Confluence"
        where = f" — {doc.url}" if doc.url else ""
        lines.append(f"- [{kind}] {doc.title}{where}")
        if excerpts and doc.summary:
            lines.append(f"    {' '.join(doc.summary.split())[: _EXCERPT_CHARS * 4]}")
    return lines


async def find_workspace_knowledge(
    question: str,
    *,
    session_url: str,
    session_root: str,
) -> str:
    """Memórias de conversas anteriores e nós do grafo de código do workspace."""
    root = workspace_root_of(session_root)
    question = question_text(question)
    if not root:
        return "Esta conversa não está em um workspace: não há memória nem grafo."
    if not question:
        return "Pergunta vazia."
    slug = root.rsplit("/", 1)[-1]
    url = session_url.rstrip("/")
    async with httpx.AsyncClient(timeout=httpx.Timeout(_KNOWLEDGE_TIMEOUT_S)) as client:
        memories, graph = await asyncio.gather(
            safe(search_memory(client, url, slug, question), []),
            safe(query_graph(client, url, slug, question, budget=_GRAPH_BUDGET), ""),
        )
    if not memories and not graph:
        return "Nada na memória nem no grafo do workspace para esta pergunta."
    lines: list[str] = []
    if memories:
        lines.append("## Memória (confirmado em conversas anteriores; confira antes de citar)")
        for item in memories:
            content = " ".join(str(item.get("content")).split())[:_MEMORY_CHARS]
            files = ", ".join(str(f) for f in (item.get("files") or [])[:3])
            lines.append(f"- {content}" + (f" (arquivos: {files})" if files else ""))
    if graph:
        lines += ["", "## Grafo de código (branch principal)", graph]
    return "\n".join(lines)
