"""GitHub / GitLab webhook adapter — recebe eventos CI/CD e dispara AgentTasks."""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http._webhook_github import (
    handle_github_event,
    verify_github_signature,
)
from app.adapters.primary.http._webhook_gitlab import (
    build_gitlab_prompt,
)
from app.adapters.primary.http.deps import get_db_session

log = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# ── Shared helpers ────────────────────────────────────────────────────────────


async def insert_cicd_event(
    db: AsyncSession, source: str, event_type: str, repo_slug: str | None, payload: dict
) -> str:
    event_id = str(uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO cicd_events (id, source, event_type, repo_slug, payload) "
            "VALUES (:id, :src, :etype, :slug, :payload::jsonb)"
        ),
        {
            "id": event_id,
            "src": source,
            "etype": event_type,
            "slug": repo_slug,
            "payload": json.dumps(payload),
        },
    )
    await db.commit()
    return event_id


async def find_env_slug(db: AsyncSession, clone_url: str) -> str | None:
    """Encontra o env_slug pelo repo_url na tabela repo_environments."""
    clean_url = clone_url.rstrip("/").removesuffix(".git")
    row = await db.execute(
        text(
            "SELECT slug FROM repo_environments "
            "WHERE REPLACE(REPLACE(repo_url, '.git', ''), "
            "'git@github.com:', 'https://github.com/') LIKE :url_pattern"
        ),
        {"url_pattern": f"%{clean_url.split('github.com/')[-1]}%"},
    )
    r = row.fetchone()
    return r.slug if r else None


async def dispatch_task(
    request: Request,
    db: AsyncSession,
    prompt: str,
    env_slug: str,
    conversation_id: str | None,
    triggered_by: str,
    trigger_payload: dict,
    cicd_event_id: str | None = None,
) -> str | None:
    try:
        agent = request.app.state.agent
        task_id = await agent.dispatch(
            prompt=prompt,
            conversation_id=conversation_id,
            triggered_by=triggered_by,
            trigger_payload=trigger_payload,
        )
        if cicd_event_id and task_id:
            await db.execute(
                text("UPDATE cicd_events SET task_id = :tid, processed_at = NOW() WHERE id = :eid"),
                {"tid": task_id, "eid": cicd_event_id},
            )
            await db.commit()
        return task_id if isinstance(task_id, str) else None
    except Exception as exc:
        log.error("Erro ao fazer dispatch de task via webhook: %s", exc)
        return None


# ── GitHub webhook ────────────────────────────────────────────────────────────


@router.post("/github")
async def github_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    x_hub_signature_256: Annotated[str | None, Header()] = None,
    x_github_event: Annotated[str | None, Header()] = None,
) -> dict:
    """Recebe eventos do GitHub Webhook (HMAC-SHA256 via X-Hub-Signature-256)."""
    body = await request.body()
    secret = os.getenv("GITHUB_WEBHOOK_SECRET", "")
    if secret:
        if not x_hub_signature_256:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="X-Hub-Signature-256 em falta.",
            )
        if not verify_github_signature(secret, body, x_hub_signature_256):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Assinatura inválida."
            )

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Payload inválido."
        ) from exc

    event_type = x_github_event or "unknown"
    repo = payload.get("repository") or {}
    repo_slug = repo.get("full_name", "")
    clone_url = repo.get("clone_url") or repo.get("git_url") or repo.get("ssh_url") or ""

    cicd_event_id = await insert_cicd_event(db, "github", event_type, repo_slug, payload)
    return await handle_github_event(
        request, db, event_type, repo_slug, clone_url, payload, cicd_event_id
    )


# ── GitLab webhook ────────────────────────────────────────────────────────────


@router.post("/gitlab")
async def gitlab_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    x_gitlab_token: Annotated[str | None, Header()] = None,
    x_gitlab_event: Annotated[str | None, Header()] = None,
) -> dict:
    """Recebe eventos do GitLab Webhook."""
    secret = os.getenv("GITLAB_WEBHOOK_SECRET", "")
    if secret and x_gitlab_token != secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido.")

    body = await request.body()
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Payload inválido."
        ) from exc

    event_type = x_gitlab_event or payload.get("object_kind", "unknown")
    project = payload.get("project") or payload.get("repository") or {}
    clone_url = project.get("http_url") or project.get("url") or project.get("git_http_url") or ""
    repo_slug = project.get("path_with_namespace") or project.get("name", "")

    cicd_event_id = await insert_cicd_event(db, "gitlab", event_type, repo_slug, payload)
    prompt = build_gitlab_prompt(event_type, payload)
    if not prompt:
        return {"status": "ignored", "event": event_type}

    env_slug = await find_env_slug(db, clone_url)
    if not env_slug:
        log.warning("GitLab webhook: repo '%s' não mapeado.", clone_url)
        return {"status": "no_env", "event": event_type, "repo": clone_url}

    task_id = await dispatch_task(
        request=request,
        db=db,
        prompt=prompt,
        env_slug=env_slug,
        conversation_id=None,
        triggered_by="gitlab",
        trigger_payload={"event": event_type, "repo": repo_slug},
        cicd_event_id=cicd_event_id,
    )
    return {"status": "dispatched", "task_id": task_id, "event": event_type}
