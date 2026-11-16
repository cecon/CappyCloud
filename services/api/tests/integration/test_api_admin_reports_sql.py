"""Relatório com o repositório SQL de verdade (SQLite em memória)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import pytest
from app.adapters.primary.http.admin_reports import get_usd_brl_rates
from app.adapters.primary.http.deps import get_db_session
from app.infrastructure.orm_models import Base, Conversation, Message, Sandbox
from app.infrastructure.orm_models import User as UserORM
from app.infrastructure.orm_models_workspaces import UserWorkspaceAccess, Workspace, WorkspaceTeam
from app.main import app as fastapi_app
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.conftest import InMemoryUserRepository
from tests.fakes_reports import FakeUsdBrlRateProvider
from tests.integration.test_api_admin_reports import PERIOD, T0, _headers


@pytest.fixture
async def sql_session() -> AsyncGenerator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        fastapi_app.dependency_overrides[get_db_session] = lambda: session
        yield session
        fastapi_app.dependency_overrides.pop(get_db_session, None)
    await engine.dispose()


async def test_real_repository_wiring(
    client: AsyncClient, user_repo: InMemoryUserRepository, sql_session: AsyncSession
) -> None:
    fastapi_app.dependency_overrides[get_usd_brl_rates] = lambda: FakeUsdBrlRateProvider()
    headers, _ = await _headers(client, user_repo, super_admin=True)
    sandbox = Sandbox(id=uuid.uuid4(), name="sb", host="sb", session_port=8080)
    user = UserORM(id=uuid.uuid4(), email="ana@linx.com", hashed_password="x")
    ws = Workspace(
        id=uuid.uuid4(),
        slug="proteus",
        name="PROTEUS",
        sandbox_id=sandbox.id,
        report_theme_preset="nfse-detalhado",
    )
    conv = Conversation(
        id=uuid.uuid4(),
        user_id=user.id,
        workspace_id=ws.id,
        title="Falha de schema",
        repos=[{"base_branch": "main"}],
    )
    sql_session.add_all([sandbox, user])
    await sql_session.flush()
    sql_session.add(ws)
    await sql_session.flush()
    team = WorkspaceTeam(id=uuid.uuid4(), workspace_id=ws.id, name="PROTHEUS SPED")
    sql_session.add_all([conv, team])
    await sql_session.flush()
    sql_session.add(
        UserWorkspaceAccess(id=uuid.uuid4(), user_id=user.id, workspace_id=ws.id, team_id=team.id)
    )
    sql_session.add(
        Message(
            id=uuid.uuid4(),
            conversation_id=conv.id,
            role="assistant",
            content="ok",
            cost_usd=0.5,
            created_at=T0,
        )
    )
    await sql_session.commit()

    body = (await client.get("/api/admin/reports/workspace", headers=headers, params=PERIOD)).json()
    assert body["totals"]["cost_usd"] == 0.5
    assert body["conversations"][0]["theme_key"] == "nfse-schema-xml"
    assert body["conversations"][0]["branches"] == ["main"]
    assert body["brl"] is None
    options = (await client.get("/api/admin/reports/options", headers=headers)).json()
    assert options["branches"] == ["main"]
    assert options["teams"] == ["PROTHEUS SPED"]
    assert body["conversations"][0]["team"] == "PROTHEUS SPED"
    assert [(t["name"], t["analysts"]) for t in body["teams"]] == [("PROTHEUS SPED", 1)]
    none = (
        await client.get(
            "/api/admin/reports/workspace",
            headers=headers,
            params={**PERIOD, "team": "__none__"},
        )
    ).json()
    assert none["totals"]["conversations"] == 0
    fastapi_app.dependency_overrides.pop(get_usd_brl_rates, None)
