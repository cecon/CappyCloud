"""GitHub / GitLab webhook adapter — recebe eventos CI/CD e dispara AgentTasks.

Verificação de autenticidade:
  - GitHub: HMAC-SHA256 via cabeçalho X-Hub-Signature-256
  - GitLab: token fixo via X-Gitlab-Token

Após verificação:
  1. INSERT cicd_events
  2. Mapeia repository.clone_url → env_slug via repo_environments.repo_url
  3. Gera prompt contextual
  4. Chama TaskDispatcher.dispatch() (via Pipeline.pipe() com body especial)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.deps import get_db_session

log = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# ── Helpers ───────────────────────────────────────────────────────────────────


def _verify_github_signature(secret: str, body: bytes, signature: str) -> bool:
    """Verifica o HMAC-SHA256 do GitHub (X-Hub-Signature-256)."""
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _extract_repo_slug(payload: dict) -> str:
    """Extrai o slug owner/repo do payload."""
    repo = payload.get("repository") or {}
    return repo.get("full_name", "")


def _extract_clone_url(payload: dict) -> str:
    repo = payload.get("repository") or {}
    return repo.get("clone_url") or repo.get("git_url") or repo.get("ssh_url") or ""


def _build_github_prompt(event_type: str, payload: dict) -> str | None:
    """Gera prompt contextual para o evento GitHub. Retorna None se ignorado."""

    if event_type == "check_run":
        action = payload.get("action", "")
        check = payload.get("check_run") or {}
        conclusion = check.get("conclusion", "")
        if action == "completed" and conclusion in ("failure", "timed_out", "cancelled"):
            name = check.get("name", "CI")
            details_url = check.get("details_url", "")
            head_sha = check.get("head_sha", "")[:8]
            output = check.get("output") or {}
            summary = output.get("summary") or output.get("text") or ""
            return (
                f"O check '{name}' falhou no commit {head_sha}.\n"
                f"Conclusão: {conclusion}\n"
                f"Detalhes: {details_url}\n"
                f"{summary}\n\n"
                "Analise o erro acima e corrija o código."
            )

    elif event_type == "pull_request":
        action = payload.get("action", "")
        pr = payload.get("pull_request") or {}
        if action == "opened":
            title = pr.get("title", "")
            body_text = pr.get("body") or ""
            number = pr.get("number", "")
            return (
                f"Foi aberto o Pull Request #{number}: '{title}'.\n"
                f"{body_text}\n\n"
                "Revise o PR acima e deixe comentários ou faça ajustes se necessário."
            )

    elif event_type == "pull_request_review":
        review = payload.get("review") or {}
        pr = payload.get("pull_request") or {}
        body_text = review.get("body") or ""
        state = review.get("state", "")
        number = pr.get("number", "")
        reviewer = (review.get("user") or {}).get("login", "reviewer")
        if state in ("changes_requested", "commented") and body_text:
            return (
                f"O revisor {reviewer} comentou no PR #{number}:\n"
                f"{body_text}\n\n"
                "Resolva os comentários acima."
            )

    elif event_type == "push":
        ref = payload.get("ref", "")
        head_commit = (payload.get("commits") or [{}])[-1]
        message = head_commit.get("message", "")[:200]
        author = (head_commit.get("author") or {}).get("name", "")
        sha = head_commit.get("id", "")[:8]
        return (
            f"Push no branch {ref} por {author} (commit {sha}):\n"
            f"{message}\n\n"
            "Indexe o código actualizado e verifique se há problemas introduzidos."
        )

    return None


async def _find_env_slug(db: AsyncSession, clone_url: str) -> str | None:
    """Encontra o env_slug pelo repo_url na tabela repo_environments."""
    # Normalize URL: remove .git suffix for comparison
    clean_url = clone_url.rstrip("/").removesuffix(".git")
    row = await db.execute(
        text(
            "SELECT slug FROM repo_environments "
            "WHERE REPLACE(REPLACE(repo_url, '.git', ''), 'git@github.com:', 'https://github.com/') "
            "LIKE :url_pattern"
        ),
        {"url_pattern": f"%{clean_url.split('github.com/')[-1]}%"},
    )
    r = row.fetchone()
    return r.slug if r else None


async def _find_conversation_for_pr(
    db: AsyncSession, repo_slug: str, pr_number: int
) -> str | None:
    """Retorna conversation_id da pr_subscription que casa com o PR."""
    row = await db.execute(
        text(
            "SELECT conversation_id FROM pr_subscriptions "
            "WHERE repo_slug = :slug AND pr_number = :num AND auto_fix_enabled = TRUE "
            "LIMIT 1"
        ),
        {"slug": repo_slug, "num": pr_number},
    )
    r = row.fetchone()
    return str(r.conversation_id) if r else None


async def _insert_cicd_event(
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


async def _dispatch_task(
    request: Request,
    db: AsyncSession,
    prompt: str,
    env_slug: str,
    conversation_id: str | None,
    triggered_by: str,
    trigger_payload: dict,
    cicd_event_id: str | None = None,
) -> str | None:
    """Dispara task via agent Pipeline. Retorna task_id ou None em caso de erro."""
    try:
        agent = request.app.state.agent
        task_id = await agent.dispatch(
            prompt=prompt,
            env_slug=env_slug,
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
        return task_id
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
    """Recebe eventos do GitHub Webhook.

    Configuração no GitHub:
      - Payload URL: https://<host>/api/webhooks/github
      - Content type: application/json
      - Secret: GITHUB_WEBHOOK_SECRET
      - Events: pull_request, check_run, push, pull_request_review
    """
    body = await request.body()

    # Verify signature if secret is configured
    secret = os.getenv("GITHUB_WEBHOOK_SECRET", "")
    if secret:
        if not x_hub_signature_256:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="X-Hub-Signature-256 em falta.",
            )
        if not _verify_github_signature(secret, body, x_hub_signature_256):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Assinatura inválida.",
            )

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payload inválido.")

    event_type = x_github_event or "unknown"
    repo_slug = _extract_repo_slug(payload)
    clone_url = _extract_clone_url(payload)

    # Store the event
    cicd_event_id = await _insert_cicd_event(db, "github", event_type, repo_slug, payload)

    # Build prompt
    prompt = _build_github_prompt(event_type, payload)
    if not prompt:
        return {"status": "ignored", "event": event_type}

    # Auto-fix routing: check if there's a pr_subscription for this PR
    conversation_id: str | None = None
    if event_type in ("check_run", "pull_request_review"):
        pr_number = _extract_pr_number_from_event(event_type, payload)
        if pr_number and repo_slug:
            conversation_id = await _find_conversation_for_pr(db, repo_slug, pr_number)

    # Find env_slug
    env_slug = await _find_env_slug(db, clone_url)
    if not env_slug:
        log.warning("GitHub webhook: repo '%s' não mapeado para nenhum env_slug.", clone_url)
        return {"status": "no_env", "event": event_type, "repo": clone_url}

    # Check routines with GitHub triggers
    await _fire_github_routines(request, db, event_type, repo_slug, payload)

    task_id = await _dispatch_task(
        request=request,
        db=db,
        prompt=prompt,
        env_slug=env_slug,
        conversation_id=conversation_id,
        triggered_by="github",
        trigger_payload={"event": event_type, "repo": repo_slug},
        cicd_event_id=cicd_event_id,
    )

    return {"status": "dispatched", "task_id": task_id, "event": event_type}


def _extract_pr_number_from_event(event_type: str, payload: dict) -> int | None:
    if event_type == "check_run":
        check = payload.get("check_run") or {}
        pr_list = check.get("pull_requests") or []
        if pr_list:
            return pr_list[0].get("number")
    elif event_type == "pull_request_review":
        pr = payload.get("pull_request") or {}
        return pr.get("number")
    return None


async def _fire_github_routines(
    request: Request,
    db: AsyncSession,
    event_type: str,
    repo_slug: str,
    payload: dict,
) -> None:
    """Verifica e dispara routines com GitHub trigger que casam com o evento."""
    try:
        rows = await db.execute(
            text(
                "SELECT id, prompt, env_slug FROM routines "
                "WHERE enabled = TRUE AND triggers @> :trigger_filter::jsonb"
            ),
            {"trigger_filter": json.dumps([{"type": "github"}])},
        )
        for row in rows.fetchall():
            try:
                agent = request.app.state.agent
                await agent.dispatch(
                    prompt=row.prompt,
                    env_slug=row.env_slug,
                    triggered_by="routine_github",
                    trigger_payload={"routine_id": str(row.id), "event": event_type, "repo": repo_slug},
                )
            except Exception as exc:
                log.error("Routine %s dispatch failed: %s", row.id, exc)
    except Exception as exc:
        log.error("Error checking GitHub routines: %s", exc)


# ── GitLab webhook ────────────────────────────────────────────────────────────


@router.post("/gitlab")
async def gitlab_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    x_gitlab_token: Annotated[str | None, Header()] = None,
    x_gitlab_event: Annotated[str | None, Header()] = None,
) -> dict:
    """Recebe eventos do GitLab Webhook.

    Configuração no GitLab:
      - URL: https://<host>/api/webhooks/gitlab
      - Secret Token: GITLAB_WEBHOOK_SECRET
      - Trigger: Push events, Pipeline events, Merge request events
    """
    # Verify token if secret is configured
    secret = os.getenv("GITLAB_WEBHOOK_SECRET", "")
    if secret and x_gitlab_token != secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido.",
        )

    body = await request.body()
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payload inválido.")

    event_type = x_gitlab_event or payload.get("object_kind", "unknown")

    # Extract repo info for GitLab
    project = payload.get("project") or payload.get("repository") or {}
    clone_url = project.get("http_url") or project.get("url") or project.get("git_http_url") or ""
    repo_slug = project.get("path_with_namespace") or project.get("name", "")

    cicd_event_id = await _insert_cicd_event(db, "gitlab", event_type, repo_slug, payload)

    # Build prompt for GitLab events
    prompt = _build_gitlab_prompt(event_type, payload)
    if not prompt:
        return {"status": "ignored", "event": event_type}

    env_slug = await _find_env_slug(db, clone_url)
    if not env_slug:
        log.warning("GitLab webhook: repo '%s' não mapeado.", clone_url)
        return {"status": "no_env", "event": event_type, "repo": clone_url}

    task_id = await _dispatch_task(
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


def _build_gitlab_prompt(event_type: str, payload: dict) -> str | None:
    """Gera prompt para evento GitLab."""
    if "Pipeline Hook" in event_type or event_type == "pipeline":
        obj = payload.get("object_attributes") or {}
        status_val = obj.get("status", "")
        if status_val in ("failed",):
            builds = payload.get("builds") or []
            failed = [b.get("name") for b in builds if b.get("status") == "failed"]
            return (
                f"Pipeline GitLab falhou. Jobs com falha: {', '.join(failed or ['desconhecido'])}.\n"
                "Analise os logs e corrija o problema."
            )
    elif "Merge Request Hook" in event_type or event_type == "merge_request":
        obj = payload.get("object_attributes") or {}
        action = obj.get("action", "")
        if action == "open":
            title = obj.get("title", "")
            description = obj.get("description") or ""
            iid = obj.get("iid", "")
            return (
                f"Foi aberto o Merge Request !{iid}: '{title}'.\n"
                f"{description}\n\n"
                "Revise o MR acima."
            )
    elif "Push Hook" in event_type or event_type == "push":
        commits = payload.get("commits") or []
        last = commits[-1] if commits else {}
        message = last.get("message", "")[:200]
        ref = payload.get("ref", "")
        return (
            f"Push em {ref}: {message}\n\n"
            "Verifique se há problemas no código actualizado."
        )
    return None
