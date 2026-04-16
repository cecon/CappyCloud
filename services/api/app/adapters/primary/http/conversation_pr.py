"""HTTP endpoints for PR creation and PR auto-fix subscriptions."""

from __future__ import annotations

import re
import uuid
from typing import Annotated, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.deps import get_authenticated_user, get_db_session
from app.domain.entities import User

router = APIRouter(prefix="/conversations", tags=["conversations"])


class CreatePrBody(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
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
        text(
            "SELECT cs.worktree_path, c.base_branch, re.slug AS env_slug, re.repo_url "
            "FROM conversations c "
            "LEFT JOIN cappy_sessions cs ON cs.chat_id = c.id::text "
            "LEFT JOIN repo_environments re ON re.id = c.environment_id "
            "WHERE c.id = :cid AND c.user_id = :uid"
        ),
        {"cid": str(conversation_id), "uid": str(current.id)},
    )
    conv = row.fetchone()
    if not conv or not conv.worktree_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversa ou worktree não encontrado."
        )

    env_row = await db.execute(
        text("SELECT container_id FROM cappy_env_containers WHERE env_slug = :slug"),
        {"slug": conv.env_slug},
    )
    env = env_row.fetchone()
    if not env:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Ambiente não encontrado."
        )

    head_branch = _get_current_branch(env.container_id, conv.worktree_path)

    m = re.search(r"github\.com[:/](.+?/.+?)(?:\.git)?$", conv.repo_url or "")
    if not m:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL do repositório não é um repo GitHub válido.",
        )
    owner_repo = m.group(1)
    base = conv.base_branch or "main"
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


def _get_current_branch(container_id: str, worktree_path: str) -> str:
    """Obtém o branch actual do worktree via docker exec."""
    import docker

    try:
        client = docker.from_env()
        container = client.containers.get(container_id)
        container.exec_run(
            ["git", "-C", worktree_path, "push", "--set-upstream", "origin",
             "HEAD", "--quiet"]
        )
        exit_code, output = container.exec_run(
            ["git", "-C", worktree_path, "rev-parse", "--abbrev-ref", "HEAD"]
        )
        branch = output.decode("utf-8", errors="replace").strip() if output else ""
        if exit_code != 0 or not branch:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Não foi possível determinar o branch actual.",
            )
        return branch
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Erro ao obter branch: {exc}",
        ) from exc


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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada.")
    if not conv.github_pr_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conversa não tem PR associado. Crie um PR primeiro.",
        )

    sub_id = str(uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO pr_subscriptions (id, conversation_id, repo_slug, pr_number, auto_fix_enabled) "
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
