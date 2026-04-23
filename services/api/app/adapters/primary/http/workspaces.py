"""Workspaces endpoint — lista os repositórios disponíveis no sandbox."""

from __future__ import annotations

import logging
import os
from typing import Annotated
from urllib.parse import quote, urlparse, urlunparse

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.adapters.primary.http.deps import get_authenticated_user, get_db_session
from app.domain.entities import User
from app.infrastructure.encryption import get_encryptor
from app.infrastructure.orm_models import Repository

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

log = logging.getLogger(__name__)

# HTTP sidecar do sandbox (session_server.js) — é lá que o `git` corre, não no container da API.
_SANDBOX_HOST = os.getenv("SANDBOX_HOST", "cappycloud-sandbox")
_SANDBOX_SESSION_PORT = os.getenv("SANDBOX_SESSION_PORT", "8080")


def _sandbox_session_base() -> str:
    return f"http://{_SANDBOX_HOST}:{_SANDBOX_SESSION_PORT}"


async def _sandbox_post_json(path: str, payload: dict) -> dict | None:
    """POST JSON ao session_server do sandbox; devolve o corpo JSON ou None em falha."""
    url = f"{_sandbox_session_base()}{path}"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            r = await client.post(url, json=payload)
            if r.status_code >= 400:
                log.warning("sandbox %s → HTTP %s: %s", path, r.status_code, (r.text or "")[:300])
                return None
            data = r.json()
            return data if isinstance(data, dict) else None
    except Exception as exc:
        log.warning("sandbox %s falhou: %s", path, exc)
        return None


class WorkspaceOut(BaseModel):
    slug: str
    name: str
    url: str
    sandbox_status: str


class BranchesOut(BaseModel):
    branches: list[str]
    default: str


class BranchesFromUrlBody(BaseModel):
    clone_url: str


def _parse_branches(raw_output: str) -> list[str]:
    """Extrai nomes de branch da saída de `git ls-remote --heads` ou `git branch -r`."""
    branches: list[str] = []
    for line in raw_output.splitlines():
        line = line.strip()
        if "\t" in line:
            ref = line.split("\t", 1)[1]
            if ref.startswith("refs/heads/"):
                name = ref[len("refs/heads/") :]
                if name and name not in branches:
                    branches.append(name)
        elif line.startswith("origin/"):
            name = line[len("origin/") :]
            if " -> " in name:
                continue
            if name and name not in branches:
                branches.append(name)
    return branches


def _make_branches_out(branches: list[str], default_hint: str = "") -> BranchesOut:
    """Monta BranchesOut escolhendo a branch default de forma inteligente."""
    if not branches:
        branches = [default_hint or "master"]
    default = (
        default_hint
        if default_hint and default_hint in branches
        else next((b for b in branches if b in ("main", "master")), branches[0])
    )
    return BranchesOut(branches=sorted(branches), default=default)


def _build_auth_url(clone_url: str, provider_type: str, token: str) -> str:
    """Injeta o token na URL de clone para autenticação git."""
    if not token:
        return clone_url
    safe = quote(token, safe="")
    parsed = urlparse(clone_url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return clone_url

    if provider_type == "azure_devops" and "dev.azure.com" in parsed.hostname:
        host = parsed.hostname
        netloc = f"pat:{safe}@{host}:{parsed.port}" if parsed.port else f"pat:{safe}@{host}"
        return urlunparse((parsed.scheme, netloc, parsed.path, "", parsed.query, parsed.fragment))

    if provider_type in ("github", "") and parsed.hostname and "github.com" in parsed.hostname:
        host = parsed.hostname
        netloc = f"x-token:{safe}@{host}:{parsed.port}" if parsed.port else f"x-token:{safe}@{host}"
        return urlunparse((parsed.scheme, netloc, parsed.path, "", parsed.query, parsed.fragment))

    if "://" in clone_url:
        netloc = (
            f"pat:{safe}@{parsed.hostname}:{parsed.port}"
            if parsed.port
            else f"pat:{safe}@{parsed.hostname}"
        )
        return urlunparse((parsed.scheme, netloc, parsed.path, "", parsed.query, parsed.fragment))
    return clone_url


@router.get("", response_model=list[WorkspaceOut])
async def list_workspaces(
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[WorkspaceOut]:
    """Lista repositórios cadastrados no banco de dados."""
    rows = await session.execute(
        select(Repository).where(Repository.active.is_(True)).order_by(Repository.name)
    )
    return [
        WorkspaceOut(slug=r.slug, name=r.name, url=r.clone_url, sandbox_status=r.sandbox_status)
        for r in rows.scalars()
    ]


@router.post("/branches-from-url", response_model=BranchesOut)
async def branches_from_url(
    body: BranchesFromUrlBody,
    _current: Annotated[User, Depends(get_authenticated_user)],
) -> BranchesOut:
    """Lista branches remotas via sandbox (git ls-remote)."""
    data = await _sandbox_post_json("/git/ls-remote-branches", {"url": body.clone_url})
    if data:
        branches = _parse_branches(data.get("stdout") or "")
        if branches:
            return _make_branches_out(branches)
    return BranchesOut(branches=["master"], default="master")


@router.get("/{slug}/branches", response_model=BranchesOut)
async def list_branches(
    slug: str,
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> BranchesOut:
    """Lista branches reais: pedido HTTP ao sandbox (git), não executa git na API.

    Ordem:
    1. ``git ls-remote --heads`` com URL autenticada (PAT do GitProvider)
    2. ``git branch -r`` no clone em ``/repos/<slug>`` (fallback shallow)
    3. ``default_branch`` do registo no banco
    """
    result = await session.execute(
        select(Repository).where(Repository.slug == slug).options(selectinload(Repository.provider))
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail=f"Workspace '{slug}' não encontrado.")

    auth_url = repo.clone_url
    if repo.provider and repo.provider.token_encrypted:
        try:
            token = get_encryptor().decrypt(repo.provider.token_encrypted)
            auth_url = _build_auth_url(repo.clone_url, repo.provider.provider_type, token)
        except Exception:
            pass

    repo_path = f"/repos/{slug}"
    default_hint = repo.default_branch or ""
    hint_data = await _sandbox_post_json("/git/origin-head-branch", {"repo_path": repo_path})
    if hint_data and isinstance(hint_data.get("branch"), str) and hint_data["branch"]:
        default_hint = hint_data["branch"]

    remote_data = await _sandbox_post_json("/git/ls-remote-branches", {"url": auth_url})
    if remote_data:
        branches = _parse_branches(remote_data.get("stdout") or "")
        if branches:
            return _make_branches_out(branches, default_hint)
        err = (remote_data.get("stderr") or "").strip()
        if err:
            log.warning("git ls-remote (sandbox) slug=%s: %s", slug, err[:400])

    local_data = await _sandbox_post_json("/git/branch-r", {"repo_path": repo_path})
    if local_data:
        branches = _parse_branches(local_data.get("stdout") or "")
        if branches:
            return _make_branches_out(branches, default_hint)

    fallback = default_hint or "master"
    return BranchesOut(branches=[fallback], default=fallback)
