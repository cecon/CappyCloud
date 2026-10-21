"""Gravação de tokens/custo do turno em ``agent_tasks`` (cappycloud_agent)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import pytest

from .agent_runtime_test_loader import task_usage as _task_usage

TASK_ID = "11111111-2222-3333-4444-555555555555"


class FakeConn:
    def __init__(self, price_row: dict[str, Any] | None = None) -> None:
        self.price_row = price_row
        self.fetchrow_calls = 0
        self.fetch_calls = 0
        self.execute_args: tuple[Any, ...] | None = None

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        self.fetch_calls += 1
        return []

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        self.fetchrow_calls += 1
        return self.price_row

    async def execute(self, query: str, *args: Any) -> None:
        self.execute_args = args


class FakePool:
    def __init__(self, conn: FakeConn) -> None:
        self.conn = conn

    @asynccontextmanager
    async def acquire(self):  # type: ignore[no-untyped-def]
        yield self.conn


async def test_reported_cost_and_cache_breakdown_are_saved_as_is() -> None:
    conn = FakeConn(price_row={"input_cost_per_1m_usd": 3, "output_cost_per_1m_usd": 15})

    await _task_usage.persist_usage(
        FakePool(conn),
        TASK_ID,
        "claude-sonnet-5",
        43382,
        130,
        cache_read_tokens=39630,
        cache_write_tokens=3732,
        cost_usd=0.0121,
    )

    # Custo do runtime já separa entrada, leitura e gravação de cache:
    # não recalcula pelo catálogo (que cobraria o cache como entrada cheia).
    assert conn.fetchrow_calls == 0
    assert conn.fetch_calls == 0
    assert conn.execute_args == ("claude-sonnet-5", 43382, 130, 0.0121, 39630, 3732, TASK_ID)


async def test_without_reported_cost_uses_catalog_and_null_cache() -> None:
    conn = FakeConn(price_row={"input_cost_per_1m_usd": 2, "output_cost_per_1m_usd": 10})

    await _task_usage.persist_usage(FakePool(conn), TASK_ID, "openai/gpt-5.4", 1_000_000, 100_000)

    assert conn.fetchrow_calls == 1
    assert conn.execute_args == ("openai/gpt-5.4", 1_000_000, 100_000, 3.0, None, None, TASK_ID)


async def test_model_missing_from_catalog_costs_zero() -> None:
    conn = FakeConn(price_row=None)

    await _task_usage.persist_usage(FakePool(conn), TASK_ID, "desconhecido", 500, 50)

    assert conn.execute_args is not None
    assert conn.execute_args[3] == 0.0


async def test_reported_zero_cost_is_kept() -> None:
    conn = FakeConn(price_row={"input_cost_per_1m_usd": 2, "output_cost_per_1m_usd": 10})

    await _task_usage.persist_usage(FakePool(conn), TASK_ID, "m", 10, 1, cost_usd=0.0)

    assert conn.fetchrow_calls == 0
    assert conn.execute_args is not None
    assert conn.execute_args[3] == 0.0


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0, 0), (900, 900), (12.0, 12), (-1, None), (None, None), ("900", None), (True, None)],
)
def test_optional_tokens(value: Any, expected: int | None) -> None:
    assert _task_usage.optional_tokens(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0, 0.0), (0.0121, 0.0121), (0.12345678, 0.123457), (-0.01, None), (None, None), ("1", None)],
)
def test_reported_cost(value: Any, expected: float | None) -> None:
    assert _task_usage.reported_cost(value) == expected
