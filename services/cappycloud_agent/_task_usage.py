"""Persistência de tokens/custo de uma AgentTask.

Extraído de ``_task_runner._persist_usage`` para manter o runner abaixo de
300 linhas. Lookup do pricing em ``ai_models`` + UPDATE em ``agent_tasks``.
"""

from __future__ import annotations

import logging

import asyncpg

log = logging.getLogger(__name__)


async def persist_usage(
    pool: asyncpg.Pool | None,
    task_id: str,
    model_used: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> None:
    """Calcula custo via lookup em ``ai_models`` e grava em ``agent_tasks``.

    Quando o ``model_used`` não estiver no catálogo, gravamos os tokens com
    ``cost_usd=0`` e logamos um aviso para que o admin sincronize via
    ``POST /api/ai-models/sync-from-openrouter``.
    """
    if pool is None:
        return
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT input_cost_per_1m_usd, output_cost_per_1m_usd
                FROM ai_models
                WHERE model_id = $1 AND active = TRUE
                LIMIT 1
                """,
                model_used,
            )
            input_cost = float(row["input_cost_per_1m_usd"] or 0) if row else 0.0
            output_cost = float(row["output_cost_per_1m_usd"] or 0) if row else 0.0
            cost_usd = round(
                (prompt_tokens * input_cost + completion_tokens * output_cost)
                / 1_000_000.0,
                6,
            )
            if not row:
                log.warning(
                    "[TaskRunner %s] modelo '%s' não consta de ai_models — "
                    "custo=0. Faça sync OpenRouter.",
                    task_id[:8],
                    model_used,
                )
            await conn.execute(
                """
                UPDATE agent_tasks
                SET model_used=$1,
                    prompt_tokens=$2,
                    completion_tokens=$3,
                    cost_usd=$4,
                    last_event_at=NOW()
                WHERE id=$5::uuid
                """,
                model_used,
                prompt_tokens,
                completion_tokens,
                cost_usd,
                task_id,
            )
    except Exception as exc:
        log.error("[TaskRunner %s] persist_usage failed: %s", task_id[:8], exc)
