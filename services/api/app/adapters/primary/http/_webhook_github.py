"""GitHub-specific webhook handling logic."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from fastapi import Request
    from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)


def verify_github_signature(secret: str, body: bytes, signature: str) -> bool:
    """Verifica o HMAC-SHA256 do GitHub (X-Hub-Signature-256)."""
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def build_github_prompt(event_type: str, payload: dict) -> str | None:
    """Gera prompt contextual para o evento GitHub. Retorna None se ignorado."""
    if event_type == "check_run":
        check = payload.get("check_run") or {}
        conclusion = check.get("conclusion", "")
        if payload.get("action") == "completed" and conclusion in (
            "failure",
            "timed_out",
            "cancelled",
        ):
            name = check.get("name", "CI")
            details_url = check.get("details_url", "")
            head_sha = check.get("head_sha", "")[:8]
            output = check.get("output") or {}
            summary = output.get("summary") or output.get("text") or ""
            return (
                f"O check '{name}' falhou no commit {head_sha}.\n"
                f"Conclusão: {conclusion}\nDetalhes: {details_url}\n{summary}\n\n"
                "Analise o erro acima e corrija o código."
            )

    elif event_type == "pull_request":
        pr = payload.get("pull_request") or {}
        if payload.get("action") == "opened":
            title = pr.get("title", "")
            body_text = pr.get("body") or ""
            number = pr.get("number", "")
            return (
                f"Foi aberto o Pull Request #{number}: '{title}'.\n{body_text}\n\n"
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
                f"O revisor {reviewer} comentou no PR #{number}:\n{body_text}\n\n"
                "Resolva os comentários acima."
            )

    elif event_type == "push":
        ref = payload.get("ref", "")
        last_commit = (payload.get("commits") or [{}])[-1]
        message = last_commit.get("message", "")[:200]
        author = (last_commit.get("author") or {}).get("name", "")
        sha = last_commit.get("id", "")[:8]
        return (
            f"Push em {ref} por {author} (commit {sha}):\n{message}\n\n"
            "Verifique se há problemas no código actualizado."
        )

    return None


def extract_pr_number(event_type: str, payload: dict) -> int | None:
    """Extrai o PR number do payload para roteamento de auto-fix."""
    if event_type == "check_run":
        prs = (payload.get("check_run") or {}).get("pull_requests") or []
        return prs[0].get("number") if prs else None
    if event_type == "pull_request_review":
        return (payload.get("pull_request") or {}).get("number")
    return None


async def handle_github_event(
    request: Request,
    db: AsyncSession,
    event_type: str,
    repo_slug: str,
    clone_url: str,
    payload: dict,
    cicd_event_id: str,
) -> dict:
    """Processa o evento GitHub: gera prompt, encontra env_slug e faz dispatch."""
    from app.adapters.primary.http.webhooks import dispatch_task, find_env_slug

    prompt = build_github_prompt(event_type, payload)
    if not prompt:
        return {"status": "ignored", "event": event_type}

    conversation_id: str | None = None
    pr_number = extract_pr_number(event_type, payload)
    if pr_number and repo_slug:
        row = await db.execute(
            text(
                "SELECT conversation_id FROM pr_subscriptions "
                "WHERE repo_slug = :slug AND pr_number = :num AND auto_fix_enabled = TRUE "
                "LIMIT 1"
            ),
            {"slug": repo_slug, "num": pr_number},
        )
        r = row.fetchone()
        if r:
            conversation_id = str(r.conversation_id)

    env_slug = await find_env_slug(db, clone_url)
    if not env_slug:
        log.warning("GitHub webhook: repo '%s' não mapeado.", clone_url)
        return {"status": "no_env", "event": event_type, "repo": clone_url}

    await _fire_github_routines(request, db, event_type, repo_slug)

    task_id = await dispatch_task(
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


async def _fire_github_routines(
    request: Request,
    db: AsyncSession,
    event_type: str,
    repo_slug: str,
) -> None:
    """Dispara routines com trigger do tipo 'github' que casam com o evento."""
    try:
        rows = await db.execute(
            text(
                "SELECT id, prompt, env_slug FROM routines "
                "WHERE enabled = TRUE AND triggers @> :filter::jsonb"
            ),
            {"filter": json.dumps([{"type": "github"}])},
        )
        for row in rows.fetchall():
            try:
                agent = request.app.state.agent
                await agent.dispatch(
                    prompt=row.prompt,
                    triggered_by="routine_github",
                    trigger_payload={
                        "routine_id": str(row.id),
                        "event": event_type,
                        "repo": repo_slug,
                    },
                )
            except Exception as exc:
                log.error("Routine %s dispatch failed: %s", row.id, exc)
    except Exception as exc:
        log.error("Error checking GitHub routines: %s", exc)
