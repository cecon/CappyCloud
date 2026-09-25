"""Grafo dos workspaces: fila de reconstrução, watchdog e admin (SQLite em memória)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from typing import Any

import httpx
import pytest
import pytest_asyncio
from app.adapters.primary.http import admin_workspace_knowledge
from app.adapters.primary.http.deps import get_db_session
from app.adapters.primary.http.deps_auth import require_super_admin
from app.infrastructure.orm_models import Base, Sandbox, SandboxSyncQueue
from app.infrastructure.orm_models_workspaces import Workspace
from app.infrastructure.sandbox_watchdog import SandboxWatchdog
from app.infrastructure.workspace_knowledge import (
    enqueue_daily_builds,
    enqueue_knowledge_build,
)
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def factory() -> AsyncGenerator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    await engine.dispose()


async def _seed(factory: async_sessionmaker[AsyncSession], slug: str = "loja") -> Workspace:
    async with factory() as session:
        sandbox = await session.scalar(select(Sandbox).limit(1))
        if sandbox is None:
            sandbox = Sandbox(id=uuid.uuid4(), name="sb", host="sb", session_port=8080)
            session.add(sandbox)
            await session.flush()
        ws = Workspace(id=uuid.uuid4(), slug=slug, name=slug, sandbox_id=sandbox.id)
        session.add(ws)
        await session.commit()
        return ws


async def _queued(factory: async_sessionmaker[AsyncSession]) -> list[tuple[str, dict]]:
    async with factory() as session:
        rows = await session.scalars(select(SandboxSyncQueue).order_by(SandboxSyncQueue.created_at))
        return [(row.operation, row.payload) for row in rows]


async def test_enfileira_uma_vez_por_workspace(factory: async_sessionmaker[AsyncSession]) -> None:
    ws = await _seed(factory)
    async with factory() as session:
        assert await enqueue_knowledge_build(session, ws) is True
        await session.commit()
        assert await enqueue_knowledge_build(session, ws) is False  # já pendente

    await _seed(factory, "pdv")
    await enqueue_daily_builds(factory)

    assert await _queued(factory) == [
        ("build_knowledge", {"slug": "loja"}),
        ("build_knowledge", {"slug": "pdv"}),
    ]


async def test_watchdog_chama_o_sandbox_e_sync_reenfileira(
    factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = await _seed(factory)
    async with factory() as session:
        session.add(
            SandboxSyncQueue(
                id=uuid.uuid4(),
                sandbox_id=ws.sandbox_id,
                operation="sync_workspace",
                payload={"slug": "loja", "repos": []},
            )
        )
        await session.commit()
    posted: list[str] = []
    real_client = httpx.AsyncClient

    def client(*_args: Any, **_kwargs: Any) -> httpx.AsyncClient:
        def handler(request: httpx.Request) -> httpx.Response:
            posted.append(request.url.path)
            return httpx.Response(202 if "knowledge" in request.url.path else 200, json={})

        return real_client(transport=httpx.MockTransport(handler))

    monkeypatch.setattr("app.infrastructure.sandbox_watchdog.httpx.AsyncClient", client)
    watchdog = SandboxWatchdog(factory)

    await watchdog.run_once()  # sync_workspace → enfileira build_knowledge
    await watchdog.run_once()  # build_knowledge → POST no sandbox

    assert posted == ["/workspaces/sync", "/workspaces/loja/knowledge/build"]


async def test_admin_le_status_arquivo_e_atualiza(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    ws = await _seed(factory)
    seen: list[tuple[str, dict[str, str]]] = []

    async def fake_get(url: str, params: dict[str, str]) -> tuple[int, Any]:
        seen.append((url, params))
        if params.get("path") == "repos/x":
            return 400, {"error": "caminho fora de knowledge/ e memory/"}
        return 200, {"status": {"state": "done", "nodes": 80}, "files": []}

    async def session_dep() -> AsyncGenerator[AsyncSession]:
        async with factory() as session:
            yield session

    app = FastAPI()
    app.include_router(admin_workspace_knowledge.router, prefix="/api")
    app.dependency_overrides[get_db_session] = session_dep
    app.dependency_overrides[require_super_admin] = lambda: None
    app.dependency_overrides[admin_workspace_knowledge.get_sandbox_get] = lambda: fake_get
    base = f"/api/admin/workspaces/{ws.id}/knowledge"

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as h:
        overview = await h.get(base)
        blocked = await h.get(f"{base}/file", params={"path": "repos/x"})
        build = await h.post(f"{base}/build")
        missing = await h.get(f"/api/admin/workspaces/{uuid.uuid4()}/knowledge")
        memories = await h.get(f"{base}/memories")

    assert overview.json()["status"]["nodes"] == 80
    assert seen[0][0] == "http://sb:8080/workspaces/loja/knowledge"
    assert blocked.status_code == 400
    assert build.status_code == 202 and build.json() == {"queued": True}
    assert missing.status_code == 404
    assert memories.status_code == 200
    assert seen[-1][0] == "http://sb:8080/workspaces/loja/memory"
    assert await _queued(factory) == [("build_knowledge", {"slug": "loja"})]
