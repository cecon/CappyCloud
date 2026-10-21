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
from app.infrastructure.orm_models_workspaces import Workspace
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


async def _seed_workspace_costs(session: AsyncSession) -> uuid.UUID:
    """Dois workspaces com mensagens a 3, 10, 20 e 40 dias; devolve o id do ``proteus``."""
    now = datetime.now(UTC)
    user_id = uuid.uuid4()
    sandbox_id = uuid.uuid4()
    proteus = Workspace(id=uuid.uuid4(), slug="proteus", name="PROTEUS", sandbox_id=sandbox_id)
    seller = Workspace(id=uuid.uuid4(), slug="seller", name="SELLER", sandbox_id=sandbox_id)
    session.add_all(
        [
            UserORM(id=user_id, email="analista@test.com", hashed_password="x"),
            Sandbox(
                id=sandbox_id, name="prod", host="localhost", grpc_port=50051, session_port=8080
            ),
            proteus,
            seller,
        ]
    )
    for workspace, costs in ((proteus, (1.0, 2.0, 4.0, 8.0)), (seller, (100.0, 0, 0, 0))):
        conversation_id = uuid.uuid4()
        session.add(
            Conversation(
                id=conversation_id,
                user_id=user_id,
                sandbox_id=sandbox_id,
                workspace_id=workspace.id,
                title=f"Chamado {workspace.slug}",
                created_at=now - timedelta(days=41),
                updated_at=now,
            )
        )
        for days_ago, cost in zip((3, 10, 20, 40), costs, strict=True):
            session.add(
                Message(
                    id=uuid.uuid4(),
                    conversation_id=conversation_id,
                    role="assistant",
                    content="resposta",
                    prompt_tokens=100,
                    completion_tokens=10,
                    cost_usd=cost,
                    created_at=now - timedelta(days=days_ago),
                )
            )
    await session.commit()
    return proteus.id


async def _admin_headers(client: AsyncClient, user_repo: InMemoryUserRepository) -> dict[str, str]:
    await seed_user(user_repo, "admin-dashboard@test.com", role=UserRole.ADMIN)
    login = await client.post(
        "/api/auth/login",
        data={"username": "admin-dashboard@test.com", "password": "password123"},
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


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
        assert [p["days"] for p in body["cost_periods"]] == [7, 15, 30]
        assert all(p["cost_usd"] == 0.0123 for p in body["cost_periods"])

    async def test_cost_periods_sum_only_messages_inside_each_window(
        self,
        client: AsyncClient,
        user_repo: InMemoryUserRepository,
        dashboard_session: AsyncSession,
    ) -> None:
        headers = await _admin_headers(client, user_repo)
        await _seed_workspace_costs(dashboard_session)

        fastapi_app.dependency_overrides[get_db_session] = lambda: dashboard_session
        try:
            response = await client.get("/api/admin/dashboard", headers=headers)
        finally:
            fastapi_app.dependency_overrides.pop(get_db_session, None)

        assert response.status_code == 200
        periods = {p["days"]: p for p in response.json()["cost_periods"]}
        assert periods[7]["cost_usd"] == 101.0
        assert periods[15]["cost_usd"] == 103.0
        assert periods[30]["cost_usd"] == 107.0
        assert periods[30]["prompt_tokens"] == 600
        assert periods[30]["completion_tokens"] == 60
        assert periods[7]["conversations"] == 2
        assert response.json()["totals"]["total_cost_usd"] == 115.0

    async def test_workspace_filter_restricts_cost_and_conversations(
        self,
        client: AsyncClient,
        user_repo: InMemoryUserRepository,
        dashboard_session: AsyncSession,
    ) -> None:
        headers = await _admin_headers(client, user_repo)
        proteus_id = await _seed_workspace_costs(dashboard_session)

        fastapi_app.dependency_overrides[get_db_session] = lambda: dashboard_session
        try:
            response = await client.get(
                "/api/admin/dashboard", headers=headers, params={"workspace_id": str(proteus_id)}
            )
        finally:
            fastapi_app.dependency_overrides.pop(get_db_session, None)

        assert response.status_code == 200
        body = response.json()
        assert body["workspace_id"] == str(proteus_id)
        periods = {p["days"]: p["cost_usd"] for p in body["cost_periods"]}
        assert periods == {7: 1.0, 15: 3.0, 30: 7.0}
        assert body["totals"]["total_cost_usd"] == 15.0
        assert body["totals"]["conversations"] == 2
        assert [c["title"] for c in body["recent_conversations"]] == ["Chamado proteus"]
