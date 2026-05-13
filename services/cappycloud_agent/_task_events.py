"""Persistência pequena de task/eventos do agente."""

from __future__ import annotations

import json

import asyncpg


async def insert_task(
    pool: asyncpg.Pool | None,
    task_id: str,
    conversation_id: str | None,
    prompt: str,
    triggered_by: str,
    trigger_payload: dict,
) -> None:
    if not pool:
        return
    await pool.execute(
        """
        INSERT INTO agent_tasks
            (id, conversation_id, env_slug, prompt, triggered_by, trigger_payload)
        VALUES
            ($1::uuid, $2::uuid, $3, $4, $5, $6::jsonb)
        """,
        task_id,
        conversation_id,
        "default",
        prompt,
        triggered_by,
        json.dumps(trigger_payload),
    )


async def update_task_status(
    pool: asyncpg.Pool | None, task_id: str, status: str
) -> None:
    if not pool:
        return
    await pool.execute(
        "UPDATE agent_tasks SET status=$1, last_event_at=NOW() WHERE id=$2::uuid",
        status,
        task_id,
    )


async def insert_event(
    pool: asyncpg.Pool | None, task_id: str, event_type: str, data: dict
) -> None:
    if not pool:
        return
    await pool.execute(
        "INSERT INTO agent_events (task_id, event_type, data) VALUES ($1::uuid, $2, $3::jsonb)",
        task_id,
        event_type,
        json.dumps(data),
    )


async def insert_error_event(
    pool: asyncpg.Pool | None, task_id: str, message: str
) -> None:
    await insert_event(pool, task_id, "error", {"message": message})


async def insert_status_event(
    pool: asyncpg.Pool | None,
    task_id: str,
    message: str,
    stage: str,
    mode: str,
) -> None:
    await insert_event(
        pool,
        task_id,
        "status",
        {"message": message, "stage": stage, "mode": mode},
    )


async def emit_session_setup_events(
    pool: asyncpg.Pool | None,
    task_id: str,
    repos: list | None,
    is_created: bool,
    working_directory: str,
) -> None:
    mode = "initializing" if is_created else "resuming"
    repo_slugs = ", ".join(str(r.get("slug") or r.get("alias") or "?") for r in repos) if repos else ""
    
    if repo_slugs:
        await insert_status_event(pool, task_id, f"Preparando: {repo_slugs}", "indexing_start", "initializing")

    await insert_status_event(pool, task_id, "Sessão preparada.", "session", mode)

    if repo_slugs:
        msg = "Repositório preparado" if is_created else "Repositório sincronizado"
        await insert_status_event(pool, task_id, f"{msg}: {repo_slugs}.", "repository", mode)
        await insert_status_event(pool, task_id, f"Repositórios prontos: {repo_slugs}", "indexing_ready", mode)

    msg_sess = "Sessão criada" if is_created else "Sessão retomada"
    await insert_status_event(pool, task_id, f"{msg_sess} em {working_directory}", "ready", mode)
