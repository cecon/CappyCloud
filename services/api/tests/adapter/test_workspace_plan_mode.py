"""Modo de planejamento por workspace (SQLite em memória)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import pytest_asyncio
from app.adapters.primary.http.workspace_plan_mode import allowed_permission_mode
from app.infrastructure.orm_models import Base, Sandbox
from app.infrastructure.orm_models_workspaces import Workspace
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def session() -> AsyncGenerator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as s:
        yield s
    await engine.dispose()


async def _workspace(session: AsyncSession, *, plan: bool | None = None) -> uuid.UUID:
    sandbox = Sandbox(
        id=uuid.uuid4(), name=f"sb-{uuid.uuid4().hex[:6]}", host="sb", session_port=8080
    )
    session.add(sandbox)
    await session.flush()
    extra = {} if plan is None else {"plan_mode_enabled": plan}
    ws = Workspace(
        id=uuid.uuid4(), slug=uuid.uuid4().hex[:8], name="ws", sandbox_id=sandbox.id, **extra
    )
    session.add(ws)
    await session.commit()
    return ws.id


async def test_workspace_novo_nasce_sem_modo_plano(session: AsyncSession) -> None:
    ws_id = await _workspace(session)

    assert await allowed_permission_mode(session, ws_id, "plan") == "bypass_permissions"


async def test_plano_passa_quando_o_workspace_habilita(session: AsyncSession) -> None:
    ws_id = await _workspace(session, plan=True)

    assert await allowed_permission_mode(session, ws_id, "plan") == "plan"


async def test_outros_modos_e_conversa_sem_workspace_nao_mudam(session: AsyncSession) -> None:
    ws_id = await _workspace(session, plan=False)

    assert await allowed_permission_mode(session, ws_id, "accept_edits") == "accept_edits"
    assert await allowed_permission_mode(session, ws_id, None) is None
    assert await allowed_permission_mode(session, None, "plan") == "plan"
    # Workspace apagado: sem configuração, não libera.
    assert await allowed_permission_mode(session, uuid.uuid4(), "plan") == "bypass_permissions"
