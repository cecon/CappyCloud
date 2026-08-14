"""Integration HTTP - /api/admin/dashboard."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
from app.adapters.primary.http.deps import get_db_session
from app.domain.entities import UserRole
from app.infrastructure import orm_models_platform
from app.infrastructure.orm_base import Base
from app.infrastructure.orm_models import Conversation, Message, Sandbox
from app.infrastructure.orm_models import User as UserORM
from app.infrastructure.orm_models_execution import AgentTask
from app.main import app as fastapi_app
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.conftest import InMemoryUserRepository
from tests.integration.conftest import seed_user

_ORM_METADATA_MODULES = (orm_models_platform,)


@pytest.fixture
async def dashboard_session() -> AsyncGenerator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def _seed_dashboard_rows(session: AsyncSession) -> None:
    now = datetime.now(UTC)
    user_id = uuid.uuid4()
    sandbox_id = uuid.uuid4()
    conversation_id = uuid.uuid4()

    session.add_all(
        [
            UserORM(
                id=user_id,
                email="owner@test.com",
                hashed_password="x",
                role=UserRole.USER.value,
            ),
            UserORM(
                id=uuid.uuid4(),
                email="admin-db@test.com",
                hashed_password="x",
                role=UserRole.ADMIN.value,
            ),
            Sandbox(
                id=sandbox_id,
                name="prod",
                host="localhost",
                grpc_port=50051,
                session_port=8080,
                status="active",
                container_status="configured",
            ),
            Conversation(
                id=conversation_id,
                user_id=user_id,
                sandbox_id=sandbox_id,
                title="Investigar lentidao",
                pr_status="open",
                ci_status="success",
                created_at=now - timedelta(hours=1),
                updated_at=now,
            ),
            Message(
                id=uuid.uuid4(),
                conversation_id=conversation_id,
                role="user",
                content="Por que cada iteracao esta lenta?",
                created_at=now - timedelta(minutes=12),
            ),
            Message(
                id=uuid.uuid4(),
                conversation_id=conversation_id,
                role="assistant",
                content="Resumo operacional com diagnostico e proximos passos.",
                model_used="openrouter/model",
                prompt_tokens=1000,
                completion_tokens=400,
                cost_usd=0.0123,
                created_at=now - timedelta(minutes=10),
            ),
            AgentTask(
                id=uuid.uuid4(),
                conversation_id=conversation_id,
                sandbox_id=sandbox_id,
                env_slug="cappycloud",
                status="running",
                prompt="Executar diagnostico",
                created_at=now - timedelta(minutes=9),
            ),
        ]
    )
    await session.commit()


class TestAdminDashboardEndpoint:
    async def test_requires_admin(
        self,
        client: AsyncClient,
        user_headers: dict[str, str],
        dashboard_session: AsyncSession,
    ) -> None:
        fastapi_app.dependency_overrides[get_db_session] = lambda: dashboard_session
        try:
            response = await client.get("/api/admin/dashboard", headers=user_headers)
        finally:
            fastapi_app.dependency_overrides.pop(get_db_session, None)

        assert response.status_code == 403

    async def test_returns_operational_summary_for_admin(
        self,
        client: AsyncClient,
        user_repo: InMemoryUserRepository,
        dashboard_session: AsyncSession,
    ) -> None:
        await seed_user(user_repo, "admin-dashboard@test.com", role=UserRole.ADMIN)
        await _seed_dashboard_rows(dashboard_session)
        login = await client.post(
            "/api/auth/login",
            data={"username": "admin-dashboard@test.com", "password": "password123"},
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        fastapi_app.dependency_overrides[get_db_session] = lambda: dashboard_session
        try:
            response = await client.get("/api/admin/dashboard", headers=headers)
        finally:
            fastapi_app.dependency_overrides.pop(get_db_session, None)

        assert response.status_code == 200
        body = response.json()
        assert body["totals"]["users"] == 2
        assert body["totals"]["admins"] == 1
        assert body["totals"]["conversations"] == 1
        assert body["totals"]["messages"] == 2
        assert body["totals"]["assistant_messages"] == 1
        assert body["totals"]["running_tasks"] == 1
        assert body["totals"]["open_pull_requests"] == 1
        assert body["totals"]["active_sandboxes"] == 1
        assert body["totals"]["prompt_tokens"] == 1000
        assert body["totals"]["completion_tokens"] == 400
        assert body["totals"]["total_cost_usd"] == 0.0123
        assert body["recent_conversations"][0]["title"] == "Investigar lentidao"
        assert body["recent_conversations"][0]["user_email"] == "owner@test.com"
        assert body["recent_conversations"][0]["message_count"] == 2
        assert body["recent_conversations"][0]["model_used"] == "openrouter/model"
