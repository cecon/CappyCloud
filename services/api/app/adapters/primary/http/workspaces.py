"""Workspaces endpoint — lista os repositórios disponíveis no sandbox."""

from __future__ import annotations

import os
import subprocess
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.deps import get_authenticated_user, get_db_session
from app.domain.entities import User
from app.infrastructure.orm_models import Repository

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

_SANDBOX_CONTAINER = os.getenv("SANDBOX_CONTAINER_NAME", "cappycloud-sandbox")


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


def _parse_branches_from_ls_remote(raw_output: str) -> BranchesOut:
    """Extrai nomes de branch da saída de `git ls-remote --heads`."""
    branches: list[str] = []
    for line in raw_output.splitlines():
        parts = line.strip().split("\t")
        if len(parts) != 2:
            continue
        ref = parts[1]  # ex.: refs/heads/main
        if ref.startswith("refs/heads/"):
            name = ref[len("refs/heads/") :]
            if name and name not in branches:
                branches.append(name)
    if not branches:
        branches = ["main"]
    default = next((b for b in branches if b in ("main", "master")), branches[0])
    return BranchesOut(branches=sorted(branches), default=default)


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
    """Lista branches remotas de qualquer URL via git ls-remote no sandbox."""
    try:
        proc = subprocess.run(
            [
                "docker",
                "exec",
                _SANDBOX_CONTAINER,
                "git",
                "ls-remote",
                "--heads",
                body.clone_url,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return _parse_branches_from_ls_remote(proc.stdout)
    except Exception:
        return BranchesOut(branches=["main"], default="main")


@router.get("/{slug}/branches", response_model=BranchesOut)
async def list_branches(
    slug: str,
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> BranchesOut:
    """Lista branches remotas do repositório slug via docker exec no sandbox."""
    result = await session.execute(select(Repository).where(Repository.slug == slug))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail=f"Workspace '{slug}' não encontrado.")

    try:
        proc = subprocess.run(
            [
                "docker",
                "exec",
                _SANDBOX_CONTAINER,
                "git",
                "ls-remote",
                "--heads",
                repo.clone_url,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return _parse_branches_from_ls_remote(proc.stdout)
    except Exception:
        return BranchesOut(branches=["main"], default="main")
