"""Pools do agente sobrevivem a conexões derrubadas pela rede quando ociosas."""

from __future__ import annotations

from typing import Any

import asyncpg
import pytest

from tests.unit.agent_runtime_test_loader import ROOT, load_agent_module

_db_pool = load_agent_module(
    "services.cappycloud_agent._db_pool",
    ROOT / "services/cappycloud_agent/_db_pool.py",
)


@pytest.mark.asyncio
async def test_create_pool_sets_keepalive_and_idle_lifetime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}

    async def fake_create_pool(dsn: str, **kwargs: Any) -> str:
        seen.update(kwargs, dsn=dsn)
        return "pool"

    monkeypatch.setattr(_db_pool.asyncpg, "create_pool", fake_create_pool)

    pool = await _db_pool.create_pool("postgresql://db/x", min_size=1, max_size=3)

    assert pool == "pool"
    assert seen["dsn"] == "postgresql://db/x"
    assert (seen["min_size"], seen["max_size"]) == (1, 3)
    assert seen["max_inactive_connection_lifetime"] == 60.0
    assert seen["server_settings"]["tcp_keepalives_idle"] == "30"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        asyncpg.exceptions.ConnectionDoesNotExistError(
            "connection was closed in the middle of operation"
        ),
        ConnectionResetError(104, "Connection reset by peer"),
    ],
)
async def test_retry_read_repeats_once_after_disconnect(error: BaseException) -> None:
    calls = 0

    async def op() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise error
        return "row"

    assert await _db_pool.retry_read(op) == "row"
    assert calls == 2


@pytest.mark.asyncio
async def test_retry_read_gives_up_after_second_failure() -> None:
    calls = 0

    async def op() -> str:
        nonlocal calls
        calls += 1
        raise ConnectionResetError(104, "Connection reset by peer")

    with pytest.raises(ConnectionResetError):
        await _db_pool.retry_read(op)
    assert calls == 2


@pytest.mark.asyncio
async def test_retry_read_does_not_retry_other_errors() -> None:
    calls = 0

    async def op() -> str:
        nonlocal calls
        calls += 1
        raise ValueError("bad query")

    with pytest.raises(ValueError):
        await _db_pool.retry_read(op)
    assert calls == 1
