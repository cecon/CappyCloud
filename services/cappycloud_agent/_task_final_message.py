"""Persist final assistant messages for background agent tasks."""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from decimal import Decimal

import asyncpg

from ._assistant_output import clean_assistant_text

log = logging.getLogger(__name__)

FINAL_MESSAGE_SAVE_GRACE_S = float(os.getenv("FINAL_MESSAGE_SAVE_GRACE_S", "2"))


async def persist_final_message_if_missing(
    pool: asyncpg.Pool | None,
    *,
    task_id: str,
    conversation_id: str | None,
    raw_text: str,
    error_message: str | None,
) -> None:
    """Save or clean the assistant message produced by a completed AgentTask.

    HTTP streaming can be interrupted by browser refreshes or tunnel drops while
    the background task keeps running. This helper makes the task itself the
    source of truth for final message persistence.
    """
    if pool is None or not conversation_id:
        return
    try:
        conv_id = uuid.UUID(conversation_id)
    except ValueError:
        return

    content = clean_assistant_text(raw_text)
    if not content and error_message:
        content = "**Erro:** " + error_message.strip()
    if not content:
        content = (
            "**Erro:** O agente terminou sem produzir uma resposta final útil. "
            "Tente novamente ou selecione outro modelo."
        )

    if FINAL_MESSAGE_SAVE_GRACE_S > 0:
        await asyncio.sleep(FINAL_MESSAGE_SAVE_GRACE_S)

    try:
        async with pool.acquire() as conn:
            task = await conn.fetchrow(
                """
                SELECT
                    created_at, completed_at, model_used, prompt_tokens,
                    completion_tokens, cost_usd
                FROM agent_tasks
                WHERE id = $1::uuid
                """,
                task_id,
            )
            if task is None:
                return
            existing = await _find_existing_response_message(conn, conv_id, content, task)
            if existing:
                await _clean_existing_message(conn, existing, content, task)
                return
            await conn.execute(
                """
                INSERT INTO messages (
                    id, conversation_id, role, content, model_used,
                    prompt_tokens, completion_tokens, cost_usd
                )
                VALUES (
                    gen_random_uuid(), $1, 'assistant', $2, $3, $4, $5, $6
                )
                """,
                conv_id,
                content,
                task["model_used"],
                int(task["prompt_tokens"] or 0),
                int(task["completion_tokens"] or 0),
                _decimal_cost(task["cost_usd"]),
            )
    except Exception as exc:
        log.warning("[TaskRunner %s] final message persistence failed: %s", task_id[:8], exc)


async def _find_existing_response_message(
    conn: asyncpg.Connection,
    conversation_id: uuid.UUID,
    content: str,
    task: asyncpg.Record,
) -> asyncpg.Record | None:
    """Find a message already saved by the HTTP stream for this task.

    SQLAlchemy sessions may keep a transaction open during SSE streaming, and
    PostgreSQL's ``now()`` then stamps the assistant row with the transaction
    start time. That can be before ``agent_tasks.created_at`` even when the
    row was inserted at the end of the stream. Use the latest user turn as the
    search floor so the TaskRunner does not create a duplicate final answer.
    """
    latest_user = await conn.fetchrow(
        """
        SELECT created_at
        FROM messages
        WHERE conversation_id = $1
          AND role = 'user'
          AND created_at <= $2::timestamptz + INTERVAL '30 seconds'
        ORDER BY created_at DESC
        LIMIT 1
        """,
        conversation_id,
        task["created_at"],
    )
    search_start = latest_user["created_at"] if latest_user else task["created_at"]
    candidates = await conn.fetch(
        """
        SELECT id, content
        FROM messages
        WHERE conversation_id = $1
          AND role = 'assistant'
          AND created_at >= $2
        ORDER BY created_at DESC
        LIMIT 10
        """,
        conversation_id,
        search_start,
    )
    if not candidates:
        return None

    for candidate in candidates:
        if clean_assistant_text(str(candidate["content"] or "")) == content:
            return candidate
    return candidates[0]


async def _clean_existing_message(
    conn: asyncpg.Connection,
    existing: asyncpg.Record,
    content: str,
    task: asyncpg.Record,
) -> None:
    cleaned_existing = clean_assistant_text(str(existing["content"] or ""))
    if cleaned_existing and cleaned_existing == existing["content"]:
        await _update_message_metadata(conn, existing["id"], task)
        return
    replacement = cleaned_existing or content
    await conn.execute(
        """
        UPDATE messages
        SET content = $1,
            model_used = COALESCE(model_used, $2),
            prompt_tokens = GREATEST(prompt_tokens, $3),
            completion_tokens = GREATEST(completion_tokens, $4),
            cost_usd = GREATEST(cost_usd, $5::numeric)
        WHERE id = $6
        """,
        replacement,
        task["model_used"],
        int(task["prompt_tokens"] or 0),
        int(task["completion_tokens"] or 0),
        _decimal_cost(task["cost_usd"]),
        existing["id"],
    )


async def _update_message_metadata(
    conn: asyncpg.Connection,
    message_id: object,
    task: asyncpg.Record,
) -> None:
    await conn.execute(
        """
        UPDATE messages
        SET model_used = COALESCE(model_used, $1),
            prompt_tokens = GREATEST(prompt_tokens, $2),
            completion_tokens = GREATEST(completion_tokens, $3),
            cost_usd = GREATEST(cost_usd, $4::numeric)
        WHERE id = $5
        """,
        task["model_used"],
        int(task["prompt_tokens"] or 0),
        int(task["completion_tokens"] or 0),
        _decimal_cost(task["cost_usd"]),
        message_id,
    )


def _decimal_cost(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value or "0"))
