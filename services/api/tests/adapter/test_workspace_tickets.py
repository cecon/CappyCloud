"""Exportação CSV das conversas de um workspace com o chamado (SQLite em memória)."""

from __future__ import annotations

import csv
import io
import uuid
from collections.abc import AsyncGenerator
from decimal import Decimal

import httpx
import pytest_asyncio
from app.adapters.primary.http import workspace_tickets
from app.adapters.primary.http.deps import get_db_session
from app.adapters.primary.http.deps_auth import get_authenticated_user
from app.domain.entities import User, UserRole
from app.infrastructure.orm_models import Base, Conversation, Message, Sandbox
from app.infrastructure.orm_models import User as UserORM
from app.infrastructure.orm_models_workspaces import Workspace
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def factory() -> AsyncGenerator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    await engine.dispose()


async def _seed(factory: async_sessionmaker[AsyncSession]) -> uuid.UUID:
    async with factory() as session:
        sandbox = Sandbox(id=uuid.uuid4(), name="sb", host="sb", session_port=8080)
        user = UserORM(id=uuid.uuid4(), email="ana@test.com", hashed_password="x", role="user")
        ws = Workspace(id=uuid.uuid4(), slug="proteus", name="PROTEUS", sandbox_id=sandbox.id)
        session.add_all([sandbox, user])
        await session.flush()
        session.add(ws)
        await session.flush()
        conv = Conversation(
            id=uuid.uuid4(),
            user_id=user.id,
            title="Erro no RPS; SP",
            workspace_id=ws.id,
            ticket_number="12345",
            pr_url="https://dev.azure.com/pr/1",
        )
        session.add(conv)
        await session.flush()
        for role, cost in (("user", "0"), ("assistant", "0.25"), ("user", "0")):
            session.add(
                Message(
                    id=uuid.uuid4(),
                    conversation_id=conv.id,
                    role=role,
                    content=role,
                    prompt_tokens=100,
                    completion_tokens=10,
                    cost_usd=Decimal(cost),
                )
            )
        await session.commit()
        return ws.id


def _client(factory: async_sessionmaker[AsyncSession], role: UserRole) -> httpx.AsyncClient:
    app = FastAPI()
    app.include_router(workspace_tickets.router, prefix="/api")

    async def db() -> AsyncGenerator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = db
    app.dependency_overrides[get_authenticated_user] = lambda: User(
        id=uuid.uuid4(), email="a@test.com", hashed_password="", role=role
    )
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")


async def test_exporta_uma_linha_por_conversa(factory: async_sessionmaker[AsyncSession]) -> None:
    ws_id = await _seed(factory)
    async with _client(factory, UserRole.ADMIN) as client:
        r = await client.get(f"/api/admin/workspaces/{ws_id}/tickets.csv")

    assert r.status_code == 200
    assert 'filename="chamados-proteus.csv"' in r.headers["content-disposition"]
    assert r.content.startswith(b"\xef\xbb\xbf")  # BOM para o Excel
    rows = list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig")), delimiter=";"))
    assert len(rows) == 1
    row = rows[0]
    assert row["chamado"] == "12345" and row["usuario"] == "ana@test.com"
    assert row["titulo"] == "Erro no RPS; SP"
    assert (row["perguntas"], row["tokens_entrada"], row["custo_usd"]) == ("2", "300", "0.2500")
    assert row["pr_url"] == "https://dev.azure.com/pr/1" and row["arquivada"] == "nao"


async def test_usuario_comum_nao_exporta(factory: async_sessionmaker[AsyncSession]) -> None:
    ws_id = await _seed(factory)
    async with _client(factory, UserRole.USER) as client:
        r = await client.get(f"/api/admin/workspaces/{ws_id}/tickets.csv")
    assert r.status_code == 403
