"""Workspaces endpoint — lista os repositórios disponíveis no sandbox."""

from __future__ import annotations

import os
import subprocess
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

_SANDBOX_CONTAINER = os.getenv("SANDBOX_CONTAINER_NAME", "cappycloud-sandbox")


class WorkspaceOut(BaseModel):
    slug: str
    name: str
    url: str


class BranchesOut(BaseModel):
    branches: list[str]
    default: str


def _parse_repos() -> list[WorkspaceOut]:
    """Lê WORKSPACE_REPOS (vírgula-separado) e retorna lista de WorkspaceOut."""
    raw = os.getenv("WORKSPACE_REPOS", "").strip()
    if not raw:
        return []

    result: list[WorkspaceOut] = []
    for entry in raw.split(","):
        url = entry.strip()
        if not url:
            continue
        path = urlparse(url).path
        slug = path.rstrip("/").split("/")[-1]
        if slug.endswith(".git"):
            slug = slug[:-4]
        name = slug.replace("-", " ").replace("_", " ").title()
        result.append(WorkspaceOut(slug=slug, name=name, url=url))

    return result


@router.get("", response_model=list[WorkspaceOut])
async def list_workspaces() -> list[WorkspaceOut]:
    """Lista repositórios configurados em WORKSPACE_REPOS."""
    return _parse_repos()


@router.get("/{slug}/branches", response_model=BranchesOut)
async def list_branches(slug: str) -> BranchesOut:
    """Lista branches remotas do repositório slug via docker exec no sandbox."""
    repos = _parse_repos()
    if not any(r.slug == slug for r in repos):
        raise HTTPException(status_code=404, detail=f"Workspace '{slug}' não encontrado.")

    repo_path = f"/repos/{slug}"

    try:
        result = subprocess.run(
            [
                "docker",
                "exec",
                _SANDBOX_CONTAINER,
                "git",
                "-C",
                repo_path,
                "branch",
                "-r",
                "--format=%(refname:short)",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        raw_branches = result.stdout.strip().splitlines()
    except Exception:
        raw_branches = []

    branches: list[str] = []
    for b in raw_branches:
        b = b.strip()
        if not b or "HEAD" in b:
            continue
        # remove "origin/" prefix
        if b.startswith("origin/"):
            b = b[len("origin/"):]
        if b and b not in branches:
            branches.append(b)

    if not branches:
        branches = ["main"]

    default = next((b for b in branches if b in ("main", "master")), branches[0])

    return BranchesOut(branches=sorted(branches), default=default)
