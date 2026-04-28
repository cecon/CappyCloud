"""HTTP endpoints for PR creation and PR auto-fix subscriptions."""

from __future__ import annotations

import re
import uuid
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.conversation_worktree_paths import (
    CREATE_PR_FROM_CONVERSATION,
    repo_url_from_create_pr_row,
    resolve_git_paths_from_worktree_row,
)
from app.adapters.primary.http.deps import get_authenticated_user, get_db_session
from app.domain.entities import User
from app.infrastructure.sandbox_worktree_client import (
    SandboxWorktreeError,
    resolve_head_branch_for_pr,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


class CreatePrBody(BaseModel):
    title: str | None = None
    body: str | None = None
    draft: bool = False


@router.post("/{conversation_id}/create-pr")
async def create_pull_request(
    conversation_id: uuid.UUID,
    pr_body: CreatePrBody,
    current: Annotated[User, Depends(get_authenticated_user)],
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """Cria um Pull Request no GitHub a partir do branch actual do worktree."""
    import os

    github_token = os.getenv("GITHUB_TOKEN", "")
    if not github_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GITHUB_TOKEN não configurado.",
        )

    row = await db.execute(
        text(CREATE_PR_FROM_CONVERSATION),
        {"cid": str(conversation_id), "uid": str(current.id)},
    )
    conv = row.fetchone()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversa ou worktree não encontrado."
        )

    worktree_path, _, base_branch_resolved = resolve_git_paths_from_worktree_row(
        conv, conversation_id
    )
    repo_url = repo_url_from_create_pr_row(conv)

    try:
        head_branch = await resolve_head_branch_for_pr(worktree_path)
    except SandboxWorktreeError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    m = re.search(r"github\.com[:/](.+?/.+?)(?:\.git)?$", repo_url or "")
    if not m:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL do repositório não é um repo GitHub válido.",
        )
    owner_repo = m.group(1)
    base = base_branch_resolved or "main"
    pr_title = pr_body.title or f"Agent changes from branch {head_branch}"
    pr_description = (
        pr_body.body or f"Changes made by CappyCloud agent in conversation {conversation_id}."
    )

    async with httpx.AsyncClient() as http:
        resp = await http.post(
            f"https://api.github.com/repos/{owner_repo}/pulls",
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github+json",
            },
            json={
                "title": pr_title,
                "body": pr_description,
                "head": head_branch,
                "base": base,
                "draft": pr_body.draft,
            },
        )

    if resp.status_code not in (200, 201):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"GitHub API error {resp.status_code}: {resp.text[:500]}",
        )

    data = resp.json()
    pr_url = data.get("html_url", "")
    pr_number = data.get("number")

    await db.execute(
        text(
            "UPDATE conversations SET github_pr_number = :num, github_repo_slug = :slug "
            "WHERE id = :cid"
        ),
        {"num": pr_number, "slug": owner_repo, "cid": str(conversation_id)},
    )
    await db.commit()
    return {"pr_url": pr_url, "pr_number": pr_number, "head_branch": head_branch}


# ── PR subscriptions ──────────────────────────────────────────────────────────


@router.post("/{conversation_id}/pr-subscriptions", status_code=status.HTTP_201_CREATED)
async def create_pr_subscription(
    conversation_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """Activa auto-fix para o PR associado a esta conversa."""
    row = await db.execute(
        text(
            "SELECT github_pr_number, github_repo_slug FROM conversations "
            "WHERE id = :cid AND user_id = :uid"
        ),
        {"cid": str(conversation_id), "uid": str(current.id)},
    )
    conv = row.fetchone()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada")
    if not conv.github_pr_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conversa não tem PR associado. Crie um PR primeiro.",
        )

    sub_id = str(uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO pr_subscriptions "
            "(id, conversation_id, repo_slug, pr_number, auto_fix_enabled) "
            "VALUES (:id, :cid, :slug, :num, TRUE)"
        ),
        {
            "id": sub_id,
            "cid": str(conversation_id),
            "slug": conv.github_repo_slug,
            "num": conv.github_pr_number,
        },
    )
    await db.commit()
    return {
        "id": sub_id,
        "conversation_id": str(conversation_id),
        "pr_number": conv.github_pr_number,
        "repo_slug": conv.github_repo_slug,
        "auto_fix_enabled": True,
    }
