"""HTTP endpoints for PR creation and PR auto-fix subscriptions."""

from __future__ import annotations

import logging
import os
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.conversation_repos import (
    ConversationRepo,
    load_conversation_repos,
)
from app.adapters.primary.http.deps import get_authenticated_user, get_db_session
from app.domain.entities import User
from app.infrastructure.encryption import get_encryptor
from app.infrastructure.git_pull_requests import (
    PullRequestError,
    open_pull_request,
    parse_pr_target,
)
from app.infrastructure.orm_models_platform import GitProvider
from app.infrastructure.sandbox_worktree_client import (
    SandboxWorktreeError,
    resolve_head_branch_for_pr,
    worktree_diff_against_base,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/conversations", tags=["conversations"])


class CreatePrBody(BaseModel):
    title: str | None = None
    body: str | None = None
    draft: bool = False


async def _provider_token(db: AsyncSession, repo: ConversationRepo, provider: str) -> str:
    """Token do git provider do repositório; GitHub ainda aceita o GITHUB_TOKEN global."""
    if repo.provider_id:
        git_provider = await db.get(GitProvider, repo.provider_id)
        if git_provider and git_provider.token_encrypted:
            try:
                return get_encryptor().decrypt(git_provider.token_encrypted)
            except Exception:
                log.warning("token do git provider %s ilegível", repo.provider_id)
    return os.getenv("GITHUB_TOKEN", "") if provider == "github" else ""


async def _open_repo_pr(
    db: AsyncSession, repo: ConversationRepo, pr_body: CreatePrBody, conversation_id: uuid.UUID
) -> dict | None:
    """PR de um repositório; ``None`` se ele não tem alterações."""
    out: dict = {"alias": repo.alias, "slug": repo.slug}
    try:
        if not (await worktree_diff_against_base(repo.worktree_path, repo.base_branch)).strip():
            return None
        target = parse_pr_target(repo.clone_url)
        token = await _provider_token(db, repo, target.provider)
        head = await resolve_head_branch_for_pr(repo.worktree_path)
        result = await open_pull_request(
            target,
            token=token,
            head=head,
            base=repo.base_branch,
            title=pr_body.title or f"Agent changes from branch {head}",
            body=pr_body.body
            or f"Changes made by CappyCloud agent in conversation {conversation_id}.",
            draft=pr_body.draft,
        )
    except (SandboxWorktreeError, PullRequestError) as exc:
        return {**out, "error": str(exc)}
    return {
        **out,
        "provider": result.provider,
        "repo_path": result.repo_path,
        "pr_url": result.url,
        "pr_number": result.number,
        "head_branch": head,
    }


@router.post("/{conversation_id}/create-pr")
async def create_pull_request(
    conversation_id: uuid.UUID,
    pr_body: CreatePrBody,
    current: Annotated[User, Depends(get_authenticated_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """Abre um PR em cada repositório editável da conversa que tem alterações.

    Repositórios somente leitura ficam de fora. ``prs`` traz o resultado (ou o
    erro) de cada repositório; os campos de topo repetem o primeiro PR aberto.
    """
    conv = await load_conversation_repos(db, conversation_id, current.id)
    prs = [
        pr
        for repo in conv.editable
        if (pr := await _open_repo_pr(db, repo, pr_body, conversation_id)) is not None
    ]
    if not prs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhum repositório editável tem alterações para PR.",
        )
    opened = [pr for pr in prs if "error" not in pr]
    if not opened:
        detail = "; ".join(f"{pr['alias'] or pr['slug']}: {pr['error']}" for pr in prs)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)

    # Auto-fix de PR (pr_subscriptions) só conhece GitHub: guarda o primeiro.
    github = next((pr for pr in opened if pr["provider"] == "github"), None)
    if github:
        await db.execute(
            text(
                "UPDATE conversations SET github_pr_number = :num, github_repo_slug = :slug "
                "WHERE id = :cid"
            ),
            {"num": github["pr_number"], "slug": github["repo_path"], "cid": str(conversation_id)},
        )
        await db.commit()
    first = opened[0]
    return {
        "pr_url": first["pr_url"],
        "pr_number": first["pr_number"],
        "head_branch": first["head_branch"],
        "prs": prs,
    }


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
