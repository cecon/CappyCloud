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


@dataclass(frozen=True)
class _DocSearchAttempt:
    query: str
    source: _ConfluenceSource


@dataclass(frozen=True)
class _ConfluenceSource:
    base_url: str
    space: str
    labels: tuple[str, ...] = ()


@dataclass(frozen=True)
class _ParameterDirectory:
    repo: str
    path: str
    preferred: bool = False


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
    async with httpx.AsyncClient(timeout=httpx.Timeout(12.0)) as client:
        docs_task = asyncio.create_task(_fetch_docs(client, sandbox_session_url, repos, doc_terms))
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


def _terms_for(message: str) -> list[str]:
    marker = "## Mensagem do utilizador"
    if marker in message:
        message = message.split(marker, 1)[1]
    raw = message.lower()
    terms: list[str] = []

    quoted = re.findall(r'"([^"]{3,60})"', message)
    terms.extend(q.strip() for q in quoted)

    for token in re.findall(r"[a-zA-Z_][\w_]{3,}", message):
        token_lower = token.lower()
        if "_" in token and token_lower not in _STOP_TERMS:
            terms.append(token)

    phrase_candidates = re.findall(
        r"[a-zA-ZÀ-ÿ0-9_][\wÀ-ÿ_]*(?:[\s\-/]+[a-zA-ZÀ-ÿ0-9_][\wÀ-ÿ_]*){1,3}",
        message,
    )
    for phrase in phrase_candidates:
        phrase = " ".join(phrase.split())
        if 4 <= len(phrase) <= 60 and phrase.lower() in raw:
            terms.append(phrase)

    # Tokens técnicos úteis: identificadores, palavras acentuadas normalizadas
    # e termos de domínio com tamanho suficiente.
    for token in re.findall(r"\b\d{2,12}\b", message):
        terms.append(token)

    for token in re.findall(r"[a-zA-Z_][\w_]{3,}", message):
        if token.lower() in _STOP_TERMS:
            continue
        terms.append(token)

    return _dedupe(terms)[:_MAX_TERMS]


def _parameter_lookup_guard(
    message: str,
    repos: list[dict],
    session_root: str,
    parameter_dirs: list[_ParameterDirectory] | None = None,
    docs: list[_DocHit] | None = None,
    doc_attempts: list[_DocSearchAttempt] | None = None,
) -> str:
    numbers = _parameter_numbers(message)
    if not numbers:
        return ""

    quoted_numbers = ", ".join(f"`{number}`" for number in numbers)
    active_dirs = _active_parameter_dirs(parameter_dirs or [])
    if active_dirs:
        path_lines = "\n".join(
            f"- `{directory.path}`" + (" (preferencial)" if directory.preferred else "")
            for directory in active_dirs
        )
        lookup_instruction = (
            "Procure o número, chave ou nome citado apenas nesses diretórios. "
            "Eles foram localizados nos arquivos rastreados do repo selecionado."
        )
    else:
        fallback_paths: list[str] = []
        for repo in repos or []:
            worktree = _worktree_path(repo, session_root)
            if worktree:
                fallback_paths.append(f"{worktree.rstrip('/')}/Parametros")
                fallback_paths.append(f"{worktree.rstrip('/')}/parameters")
        fallback_paths = _dedupe(fallback_paths)
        if not fallback_paths:
            return ""
        path_lines = "\n".join(f"- `{path}`" for path in fallback_paths)
        lookup_instruction = (
            "Primeiro tente localizar diretórios `*/Parametros` ou `*/parameters` "
            "dentro do repo selecionado e procure o número apenas nesses candidatos. "
            "Não pesquise o número na raiz inteira do repo."
        )

    lines = [
        "## Regra obrigatória para parâmetro numérico",
        f"A pergunta cita parâmetro numérico ({quoted_numbers}). Antes de responder, "
        "verifique a definição do parâmetro nos diretórios de parâmetros do repo:",
        path_lines,
        lookup_instruction,
        "Use `test -d`, `find` ou `Grep` com `path` apontando para esses diretórios. "
        "É permitido descobrir diretórios `Parametros`/`parameters`; não é permitido "
        "fazer busca ampla por `630` na raiz do repo.",
        "Se usar busca ampla por nomes de diretórios de parâmetros para descobrir "
        "candidatos, descreva isso como descoberta de diretórios, não como busca por "
        "`630` em todo o repositório.",
        "Se os diretórios não existirem ou se o número não for encontrado neles, diga que "
        "a definição do parâmetro não foi encontrada nesta cópia/branch.",
        "Nesse caso, não faça busca ampla no repositório para tentar inferir significado; "
        "buscas fora desse diretório só servem depois de encontrar a definição real do parâmetro.",
        "Não conclua o significado do parâmetro a partir de ocorrências soltas em NCM, "
        "CNPJ, Código IBGE, GUID, arquivos `.sln`, seeds ou outros dados que apenas "
        "contêm a sequência numérica.",
    ]
    doc_lines = _parameter_doc_result_lines(docs or [], doc_attempts or [])
    if doc_lines:
        lines.extend(doc_lines)
    lines.extend(
        [
            "Combine essa checagem com a seção de evidências automáticas. Se ela indicar "
            "Confluence sem resultados, diga isso na resposta final em vez de orientar o "
            "utilizador a consultar documentação oficial como se ela ainda não tivesse "
            "sido consultada.",
            "Depois de encontrar a definição real do parâmetro, aí sim procure usos no restante "
            "do repo para explicar impacto e comportamento.",
        ]
    )
    return "\n".join(lines)


def _parameter_numbers(message: str) -> list[str]:
    marker = "## Mensagem do utilizador"
    if marker in message:
        message = message.split(marker, 1)[1]
    lower = message.lower()
    if not re.search(r"\b(?:par[aâ]metro|parametro|param|parametros|par[aâ]metros)\b", lower):
        return []
    return _dedupe(re.findall(r"\b\d{1,12}\b", message))


def _parameter_doc_result_lines(
    docs: list[_DocHit],
    doc_attempts: list[_DocSearchAttempt],
) -> list[str]:
    if docs or not doc_attempts:
        return []
    lines = [
        "Documentação externa já consultada automaticamente para esta pergunta:",
    ]
    for attempt in doc_attempts[:4]:
        lines.append(
            f"- Confluence para `{attempt.query}`: sem resultados retornados"
            + _format_doc_filters(attempt.source)
            + "."
        )
    lines.append(
        "Na resposta final, cite essa ausência documental como fato confirmado; "
        "não escreva 'caso o Confluence não traga resultados' ou equivalente."
    )
    return lines


async def _fetch_docs(
    client: httpx.AsyncClient,
    session_url: str,
    repos: list[dict],
    terms: list[str],
) -> tuple[list[_DocHit], list[_DocSearchAttempt]]:
    confluence_sources = _confluence_sources(repos)
    if not confluence_sources:
        return ([], [])
    attempts = [
        _DocSearchAttempt(term, source) for source in confluence_sources for term in terms[:4]
    ]
    tasks = [
        _fetch_docs_for(client, session_url, source, term)
        for source in confluence_sources
        for term in terms[:4]
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    hits: list[_DocHit] = []
    for result in results:
        if isinstance(result, list):
            hits.extend(result)
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
        url = str(item.get("url") or item.get("web_url") or item.get("link") or "").strip()
        summary = str(item.get("summary") or item.get("excerpt") or item.get("content") or "")
        if title:
            hits.append(_DocHit(term, title, url, _trim(summary)))
    return hits


async def _fetch_parameter_directories(
    client: httpx.AsyncClient,
    session_url: str,
    repos: list[dict],
    session_root: str,
) -> list[_ParameterDirectory]:
    tasks = []
    repo_context: list[tuple[str, str]] = []
    for repo in repos:
        worktree = _worktree_path(repo, session_root)
        if not worktree:
            continue
        repo_name = str(repo.get("slug") or repo.get("alias") or worktree)
        repo_context.append((repo_name, worktree))
        tasks.append(_fetch_ls_files(client, session_url, worktree))
    results = await asyncio.gather(*tasks, return_exceptions=True)
    directories: list[_ParameterDirectory] = []
    for (repo_name, worktree), result in zip(repo_context, results, strict=False):
        if isinstance(result, list):
            directories.extend(_parameter_dirs_from_files(repo_name, worktree, result))
    return _active_parameter_dirs(directories)


async def _fetch_ls_files(
    client: httpx.AsyncClient,
    session_url: str,
    worktree: str,
) -> list[str]:
    resp = await client.post(
        f"{session_url.rstrip('/')}/worktree/ls-files",
        json={"worktree_path": worktree},
    )
    if resp.status_code != 200:
        return []
    return [str(item) for item in (resp.json().get("files") or [])]


async def _fetch_parameter_code(
    client: httpx.AsyncClient,
    session_url: str,
    parameter_dirs: list[_ParameterDirectory],
    numbers: list[str],
) -> list[_CodeHit]:
    tasks = [
        _fetch_code_for_parameter_dir(client, session_url, directory, number)
        for directory in parameter_dirs
        for number in numbers
    ]
    if not tasks:
        return []
    results = await asyncio.gather(*tasks, return_exceptions=True)
    hits: list[_CodeHit] = []
    for result in results:
        if isinstance(result, list):
            hits.extend(result)
    return _unique_code(hits)[:18]


async def _fetch_code_for_parameter_dir(
    client: httpx.AsyncClient,
    session_url: str,
    directory: _ParameterDirectory,
    number: str,
) -> list[_CodeHit]:
    resp = await client.post(
        f"{session_url.rstrip('/')}/worktree/search",
        json={"worktree_path": directory.path, "query": number, "limit": _CODE_MATCHES_PER_TERM},
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
            hits.append(
                _CodeHit(
                    number,
                    directory.repo,
                    f"{directory.path.rstrip('/')}/{path}",
                    int(item.get("line") or 0),
                    _trim(text),
                )
            )
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


def _render_section(
    docs: list[_DocHit],
    code: list[_CodeHit],
    doc_attempts: list[_DocSearchAttempt] | None = None,
) -> str:
    if not docs and not code and not doc_attempts:
        return ""
    parts = [
        "## Evidências coletadas automaticamente",
        "Use esta amostra como ponto de partida obrigatório. As consultas de documentação "
        "listadas aqui já foram executadas pelo CappyCloud nesta conversa. Se a seção "
        "informar Confluence sem resultados, mencione essa ausência de evidência direta "
        "na resposta final; não diga apenas que o utilizador deve consultar documentação "
        "oficial. Se a amostra for insuficiente, continue investigando com Confluence, "
        "Grep e Read antes da resposta final. Não cite itens abaixo como conclusão sem "
        "validar o conteúdo relevante.",
    ]
    if docs:
        parts.append("### Documentação encontrada")
        parts.extend(
            f"- `{hit.query}` → {hit.title}"
            + (f" ({hit.url})" if hit.url else "")
            + (f": {hit.summary}" if hit.summary else "")
            for hit in docs
        )
    elif doc_attempts:
        parts.append("### Documentação consultada automaticamente sem resultados")
        parts.append(
            "Resultado documental já verificado: as buscas abaixo foram executadas e "
            "retornaram zero páginas. Na resposta final, trate isso como fato "
            "confirmado, não como hipótese. Não escreva 'caso a documentação não "
            "traga resultados'; escreva que o Confluence foi consultado com esses "
            "filtros e não trouxe evidência direta."
        )
        parts.extend(
            f"- `{attempt.query}` → Confluence sem resultados retornados"
            + _format_doc_filters(attempt.source)
            for attempt in doc_attempts[:8]
        )
    if code:
        parts.append("### Código encontrado")
        parts.extend(
            f"- `{hit.query}` → {hit.repo}:{hit.path}:{hit.line}: {hit.text}" for hit in code
        )
    return "\n".join(parts)


def _format_doc_filters(source: _ConfluenceSource) -> str:
    filters: list[str] = []
    if source.space:
        filters.append(f"space `{source.space}`")
    if source.labels:
        filters.append("labels " + ", ".join(f"`{label}`" for label in source.labels))
    return f" ({'; '.join(filters)})" if filters else ""


def _parameter_dirs_from_files(
    repo_name: str,
    worktree: str,
    files: list[str],
) -> list[_ParameterDirectory]:
    candidates: list[_ParameterDirectory] = []
    seen: set[str] = set()
    for raw in files:
        rel_path = str(raw).replace("\\", "/").strip("/")
        if not rel_path:
            continue
        segments = [segment for segment in rel_path.split("/") if segment]
        for index, segment in enumerate(segments):
            segment_lower = segment.lower()
            is_parameter_dir = segment_lower in {"parametros", "parameters"}
            if not is_parameter_dir:
                continue
            end = index + 1
            rel_dir = "/".join(segments[:end])
            abs_dir = f"{worktree.rstrip('/')}/{rel_dir}"
            key = abs_dir.lower()
            if key in seen:
                continue
            seen.add(key)
            candidates.append(_ParameterDirectory(repo_name, abs_dir))
    return _sort_parameter_dirs(candidates)


def _active_parameter_dirs(directories: list[_ParameterDirectory]) -> list[_ParameterDirectory]:
    preferred = [directory for directory in directories if directory.preferred]
    return _sort_parameter_dirs(preferred or directories)


def _sort_parameter_dirs(directories: list[_ParameterDirectory]) -> list[_ParameterDirectory]:
    return sorted(directories, key=lambda item: (not item.preferred, item.path.lower()))


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


def _clean_labels(raw_labels: object) -> list[str]:
    if isinstance(raw_labels, str):
        values = raw_labels.split(",")
    elif isinstance(raw_labels, (list, tuple)):
        values = raw_labels
    else:
        return []
    labels: list[str] = []
    seen: set[str] = set()
    for raw in values:
        label = str(raw).strip()
        key = label.lower()
        if label and key not in seen:
            seen.add(key)
            labels.append(label)
    return labels


_STOP_TERMS = {
    "analise",
    "análise",
    "codigo",
    "código",
    "documentacao",
    "documentação",
    "evidencia",
    "evidência",
    "investigue",
    "mapeie",
    "mostre",
    "procure",
    "repo",
    "repositorio",
    "repositório",
    "sobre",
}


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
