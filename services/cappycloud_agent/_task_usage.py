"""Persistência de tokens/custo de uma AgentTask.

Extraído de ``_task_runner._persist_usage`` para manter o runner abaixo de
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
        headers={"Accept": "application/json", "User-Agent": "CappyCloud/usage-pricing"},
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
