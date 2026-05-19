"""Busca de código para a coleta automática de evidências."""

from __future__ import annotations

import asyncio

import httpx

from ._evidence_models import _CodeHit, _ParameterDirectory
from ._evidence_utils import _trim, _worktree_path

_CODE_MATCHES_PER_TERM = 8


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
        json={
            "worktree_path": directory.path,
            "query": number,
            "limit": _CODE_MATCHES_PER_TERM,
        },
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
            tasks.append(
                _fetch_code_for(client, session_url, worktree, repo_name, term)
            )
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
        json={
            "worktree_path": worktree,
            "query": term,
            "limit": _CODE_MATCHES_PER_TERM,
        },
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
                _CodeHit(term, repo_name, path, int(item.get("line") or 0), _trim(text))
            )
    return hits


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
            if segment.lower() not in {"parametros", "parameters"}:
                continue
            rel_dir = "/".join(segments[: index + 1])
            abs_dir = f"{worktree.rstrip('/')}/{rel_dir}"
            key = abs_dir.lower()
            if key in seen:
                continue
            seen.add(key)
            candidates.append(_ParameterDirectory(repo_name, abs_dir))
    return _sort_parameter_dirs(candidates)


def _active_parameter_dirs(
    directories: list[_ParameterDirectory],
) -> list[_ParameterDirectory]:
    preferred = [directory for directory in directories if directory.preferred]
    return _sort_parameter_dirs(preferred or directories)


def _sort_parameter_dirs(
    directories: list[_ParameterDirectory],
) -> list[_ParameterDirectory]:
    return sorted(directories, key=lambda item: (not item.preferred, item.path.lower()))


def _unique_code(hits: list[_CodeHit]) -> list[_CodeHit]:
    seen: set[tuple[str, int, str]] = set()
    out: list[_CodeHit] = []
    for hit in hits:
        key = (hit.path, hit.line, hit.text)
        if key not in seen:
            seen.add(key)
            out.append(hit)
    return out
