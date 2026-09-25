"""Chat não pode ficar bloqueado por um container_status velho com a sandbox de pé."""

from __future__ import annotations

import io
import json
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import httpx
import pytest
import pytest_asyncio
from app.adapters.primary.http import conversation_sandbox_guard as guard
from app.adapters.secondary.sandbox_runtime import docker_sidecar
from app.domain.entities import ContainerStatus
from app.domain.entities import Sandbox as SandboxEntity
from app.domain.value_objects import AgentRuntime, SandboxRuntime
from app.infrastructure.orm_models import Base, Sandbox
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def session() -> AsyncGenerator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
        yield s
    await engine.dispose()


async def _sandbox(session: AsyncSession, container_status: str, runtime: str) -> Sandbox:
    row = Sandbox(
        id=uuid.uuid4(),
        name="cappycloud-sandbox",
        host="sb",
        session_port=8080,
        container_status=container_status,
        agent_runtime=runtime,
    )
    session.add(row)
    await session.commit()
    return row


def _health(monkeypatch: pytest.MonkeyPatch, reply: Any) -> None:
    real_client = httpx.AsyncClient

    def handler(request: httpx.Request) -> httpx.Response:
        if isinstance(reply, Exception):
            raise reply
        return httpx.Response(200, json=reply)

    monkeypatch.setattr(
        guard.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler)),
    )


async def test_sandbox_com_status_velho_que_responde_libera_o_chat(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = await _sandbox(session, "error", "claude_cli")
    _health(monkeypatch, {"status": "ok", "openclaude": "stopped"})

    await guard.ensure_sandbox_ready_for_chat(session, row.id)

    await session.refresh(row)
    assert row.container_status == "configured"


async def test_sandbox_que_nao_responde_continua_bloqueada(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = await _sandbox(session, "error", "claude_cli")
    _health(monkeypatch, httpx.ConnectError("fora"))

    with pytest.raises(HTTPException) as exc:
        await guard.ensure_sandbox_ready_for_chat(session, row.id)

    assert exc.value.status_code == 409
    assert "não está respondendo" in exc.value.detail


async def test_openclaude_parado_so_bloqueia_quem_usa_openclaude(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = await _sandbox(session, "stopped", "openclaude")
    _health(monkeypatch, {"status": "ok", "openclaude": "stopped"})

    with pytest.raises(HTTPException):
        await guard.ensure_sandbox_ready_for_chat(session, row.id)


def _entity(runtime: AgentRuntime) -> SandboxEntity:
    return SandboxEntity(
        id=uuid.uuid4(),
        name="sb",
        host="sb",
        runtime=SandboxRuntime.COMPOSE,
        image="",
        container_status=ContainerStatus.CONFIGURED,
        agent_runtime=runtime,
    )


@pytest.mark.parametrize(
    ("runtime", "expected"),
    [
        (AgentRuntime.CLAUDE_CLI, ContainerStatus.CONFIGURED),
        (AgentRuntime.OPENCLAUDE, ContainerStatus.STOPPED),
    ],
)
def test_probe_so_marca_parada_quando_o_chat_usa_openclaude(
    monkeypatch: pytest.MonkeyPatch, runtime: AgentRuntime, expected: ContainerStatus
) -> None:
    class Response(io.BytesIO):
        status = 200

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    payload = json.dumps({"status": "ok", "openclaude": "stopped"}).encode()
    monkeypatch.setattr(
        docker_sidecar.urllib.request, "urlopen", lambda url, timeout: Response(payload)
    )

    probe = docker_sidecar.probe_session_server(_entity(runtime))

    assert probe is not None and probe.status is expected
