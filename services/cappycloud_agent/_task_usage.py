"""Persistência de tokens/custo de uma AgentTask.

Extraído do ``_task_runner`` para manter o runner abaixo de
300 linhas. Lookup do pricing em ``ai_models`` + UPDATE em ``agent_tasks``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.request
from typing import Any

import asyncpg

log = logging.getLogger(__name__)

_OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
_OPENROUTER_TIMEOUT_SECONDS = 30


def _price_per_1m(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        per_token = float(value)
    except (TypeError, ValueError):
        return None
    if per_token < 0:
        return None
    return round(per_token * 1_000_000, 6)


def _fetch_openrouter_price_catalog() -> dict[str, tuple[float | None, float | None]]:
    req = urllib.request.Request(
        _OPENROUTER_MODELS_URL,
        headers={
            "Accept": "application/json",
            "User-Agent": "CappyCloud/usage-pricing",
        },
    )
    with urllib.request.urlopen(req, timeout=_OPENROUTER_TIMEOUT_SECONDS) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    catalog: dict[str, tuple[float | None, float | None]] = {}
    for item in payload.get("data") or []:
        if not isinstance(item, dict):
            continue
        model_id = item.get("id")
        pricing = item.get("pricing") or {}
        if not isinstance(model_id, str) or not isinstance(pricing, dict):
            continue
        catalog[model_id] = (
            _price_per_1m(pricing.get("prompt")),
            _price_per_1m(pricing.get("completion")),
        )
    return catalog


async def _refresh_openrouter_prices_for_configured_models(
    conn: asyncpg.Connection,
) -> int:
    """Atualiza preços dos modelos OpenRouter ativos cadastrados no ambiente."""
    rows = await conn.fetch(
        """
        SELECT m.model_id
        FROM ai_models m
        JOIN ai_providers p ON p.id = m.provider_id
        WHERE m.active = TRUE
          AND (
            lower(p.name) = 'openrouter'
            OR p.base_url ILIKE '%openrouter.ai%'
          )
        """
    )
    configured_ids = {str(row["model_id"]) for row in rows}
    if not configured_ids:
        return 0

    catalog = await asyncio.to_thread(_fetch_openrouter_price_catalog)
    updated = 0
    for model_id in configured_ids:
        prices = catalog.get(model_id)
        if prices is None:
            continue
        input_cost, output_cost = prices
        await conn.execute(
            """
            UPDATE ai_models
            SET input_cost_per_1m_usd=$1,
                output_cost_per_1m_usd=$2
            WHERE model_id=$3
              AND active = TRUE
              AND provider_id IN (
                SELECT id FROM ai_providers
                WHERE lower(name) = 'openrouter'
                   OR base_url ILIKE '%openrouter.ai%'
              )
            """,
            input_cost,
            output_cost,
            model_id,
        )
        updated += 1
    return updated


def optional_tokens(value: Any) -> int | None:
    """Tokens de cache do ``done``; ``None`` quando o runtime não informou."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return None
    return int(value)


def reported_cost(value: Any) -> float | None:
    """Custo que o runtime já calculou (Claude CLI); ``None`` quando não veio."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return None
    return round(float(value), 6)


async def persist_usage(
    pool: asyncpg.Pool | None,
    task_id: str,
    model_used: str,
    prompt_tokens: int,
    completion_tokens: int,
    *,
    cache_read_tokens: int | None = None,
    cache_write_tokens: int | None = None,
    cost_usd: float | None = None,
) -> None:
    """Grava tokens/custo do turno em ``agent_tasks``.

    ``prompt_tokens`` inclui leitura e gravação de cache; as duas parcelas vão
    em colunas próprias quando o runtime as informa (Claude CLI). Se o runtime
    mandou ``cost_usd`` (Claude CLI, que precifica cada tipo de token), ele é
    gravado como veio. Senão, o custo sai do lookup em ``ai_models``; quando o
    ``model_used`` não estiver no catálogo, gravamos ``cost_usd=0`` e logamos
    um aviso para que o admin sincronize via
    ``POST /api/ai-models/sync-from-openrouter``.
    """
    if pool is None:
        return
    try:
        async with pool.acquire() as conn:
            if cost_usd is None:
                cost_usd = await _cost_from_catalog(
                    conn, task_id, model_used, prompt_tokens, completion_tokens
                )
            await conn.execute(
                """
                UPDATE agent_tasks
                SET model_used=$1,
                    prompt_tokens=$2,
                    completion_tokens=$3,
                    cost_usd=$4,
                    cache_read_tokens=$5,
                    cache_write_tokens=$6,
                    last_event_at=NOW()
                WHERE id=$7::uuid
                """,
                model_used,
                prompt_tokens,
                completion_tokens,
                cost_usd,
                cache_read_tokens,
                cache_write_tokens,
                task_id,
            )
    except Exception as exc:
        log.error("[TaskRunner %s] persist_usage failed: %s", task_id[:8], exc)


async def _cost_from_catalog(
    conn: asyncpg.Connection,
    task_id: str,
    model_used: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    try:
        updated = await _refresh_openrouter_prices_for_configured_models(conn)
        if updated:
            log.info(
                "[TaskRunner %s] preços OpenRouter atualizados para %d modelos",
                task_id[:8],
                updated,
            )
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "[TaskRunner %s] falha ao atualizar preços OpenRouter: %s",
            task_id[:8],
            exc,
        )

    row = await conn.fetchrow(
        """
        SELECT input_cost_per_1m_usd, output_cost_per_1m_usd
        FROM ai_models
        WHERE model_id = $1 AND active = TRUE
        LIMIT 1
        """,
        model_used,
    )
    if not row:
        log.warning(
            "[TaskRunner %s] modelo '%s' não consta de ai_models — "
            "custo=0. Faça sync OpenRouter.",
            task_id[:8],
            model_used,
        )
        return 0.0
    input_cost = float(row["input_cost_per_1m_usd"] or 0)
    output_cost = float(row["output_cost_per_1m_usd"] or 0)
    return round(
        (prompt_tokens * input_cost + completion_tokens * output_cost) / 1_000_000.0,
        6,
    )
