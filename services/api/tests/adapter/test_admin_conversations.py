"""Admin lê conversas de qualquer usuário (SQLite em memória)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest_asyncio
from app.adapters.primary.http import admin_conversations
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


async def _seed(factory: async_sessionmaker[AsyncSession]) -> dict[str, uuid.UUID]:
    now = datetime.now(UTC)
    async with factory() as session:
        sandbox = Sandbox(id=uuid.uuid4(), name="sb", host="sb", session_port=8080)
        ana = UserORM(id=uuid.uuid4(), email="ana@test.com", hashed_password="x", role="user")
        bia = UserORM(id=uuid.uuid4(), email="bia@test.com", hashed_password="x", role="user")
        session.add_all([sandbox, ana, bia])
        await session.flush()
        ws = Workspace(id=uuid.uuid4(), slug="proteus", name="PROTEUS", sandbox_id=sandbox.id)
        session.add(ws)
        await session.flush()
        nfse = Conversation(
            id=uuid.uuid4(),
            user_id=ana.id,
            title="RPS rejeitado",
            workspace_id=ws.id,
            ticket_number="12345",
        )
        other = Conversation(id=uuid.uuid4(), user_id=bia.id, title="Outra coisa")
        session.add_all([nfse, other])
        await session.flush()
        for i, (role, text, cost) in enumerate(
            [("user", "Por que o RPS volta?", "0"), ("assistant", "Falta o CNAE.", "0.30")]
        ):
            session.add(
                Message(
                    id=uuid.uuid4(),
                    conversation_id=nfse.id,
                    role=role,
                    content=text,
                    model_used="claude-sonnet-5" if role == "assistant" else None,
                    prompt_tokens=100,
                    completion_tokens=10,
                    cost_usd=Decimal(cost),
                    created_at=now + timedelta(seconds=i),
                )
            )
        await session.commit()
        return {"nfse": nfse.id, "other": other.id, "ws": ws.id}


def _client(factory: async_sessionmaker[AsyncSession], role: UserRole) -> httpx.AsyncClient:
    app = FastAPI()
    app.include_router(admin_conversations.router, prefix="/api")

    async def db() -> AsyncGenerator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = db
    app.dependency_overrides[get_authenticated_user] = lambda: User(
        id=uuid.uuid4(), email="admin@test.com", hashed_password="", role=role
    )
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")


async def test_lista_todas_e_filtra_por_chamado_usuario_e_workspace(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    ids = await _seed(factory)
    async with _client(factory, UserRole.ADMIN) as client:
        everything = (await client.get("/api/admin/conversations")).json()
        by_ticket = (await client.get("/api/admin/conversations", params={"q": "#123"})).json()
        by_user = (await client.get("/api/admin/conversations", params={"q": "bia@"})).json()
        by_ws = (
            await client.get("/api/admin/conversations", params={"workspace_id": str(ids["ws"])})
        ).json()

    assert everything["total"] == 2
    assert [i["title"] for i in by_ticket["items"]] == ["RPS rejeitado"]
    item = by_ticket["items"][0]
    assert (item["user_email"], item["workspace_slug"], item["ticket_number"]) == (
        "ana@test.com",
        "proteus",
        "12345",
    )
    assert (item["questions"], item["message_count"], item["cost_usd"]) == (1, 2, 0.3)
    assert [i["title"] for i in by_user["items"]] == ["Outra coisa"]
    assert by_ws["total"] == 1


async def test_abre_a_conversa_completa_em_ordem(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    ids = await _seed(factory)
    async with _client(factory, UserRole.ADMIN) as client:
        detail = (await client.get(f"/api/admin/conversations/{ids['nfse']}")).json()
        missing = await client.get(f"/api/admin/conversations/{uuid.uuid4()}")

    assert [(m["role"], m["content"]) for m in detail["messages"]] == [
        ("user", "Por que o RPS volta?"),
        ("assistant", "Falta o CNAE."),
    ]
    assert detail["messages"][1]["model_used"] == "claude-sonnet-5"
    assert missing.status_code == 404


async def test_usuario_comum_nao_le_conversa_de_outro(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    ids = await _seed(factory)
    async with _client(factory, UserRole.USER) as client:
        assert (await client.get("/api/admin/conversations")).status_code == 403
        assert (await client.get(f"/api/admin/conversations/{ids['nfse']}")).status_code == 403
