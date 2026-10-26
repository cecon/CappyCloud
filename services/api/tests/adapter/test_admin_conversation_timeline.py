"""Admin lê passos e anexos de conversas de outros usuários (SQLite em memória)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import pytest_asyncio
from app.adapters.primary.http import admin_conversation_timeline as timeline
from app.adapters.primary.http.deps import get_db_session
from app.adapters.primary.http.deps_attachments import get_attachment_storage
from app.adapters.primary.http.deps_auth import get_admin_scope, get_authenticated_user
from app.application.use_cases.admin_scope import AdminScope
from app.domain.entities import User, UserRole
from app.infrastructure.orm_models import Base, Conversation, Message, MessageAttachment, Sandbox
from app.infrastructure.orm_models import User as UserORM
from app.infrastructure.orm_models_workspaces import Workspace
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

T0 = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)


@pytest_asyncio.fixture
async def factory() -> AsyncGenerator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    await engine.dispose()


async def _seed(factory: async_sessionmaker[AsyncSession]) -> dict[str, uuid.UUID]:
    async with factory() as session:
        sandbox = Sandbox(id=uuid.uuid4(), name="sb", host="sb", session_port=8080)
        ana = UserORM(id=uuid.uuid4(), email="ana@test.com", hashed_password="x", role="user")
        session.add_all([sandbox, ana])
        await session.flush()
        ws = Workspace(id=uuid.uuid4(), slug="protheus", name="PROTHEUS", sandbox_id=sandbox.id)
        session.add(ws)
        await session.flush()
        conv = Conversation(id=uuid.uuid4(), user_id=ana.id, title="Erro", workspace_id=ws.id)
        other = Conversation(id=uuid.uuid4(), user_id=ana.id, title="Sem workspace")
        session.add_all([conv, other])
        await session.flush()
        q1, q2 = uuid.uuid4(), uuid.uuid4()
        for mid, role, at in [
            (q1, "user", T0),
            (uuid.uuid4(), "assistant", T0 + timedelta(seconds=5)),
            (q2, "user", T0 + timedelta(minutes=1)),
        ]:
            session.add(
                Message(id=mid, conversation_id=conv.id, role=role, content=role, created_at=at)
            )
        att = MessageAttachment(
            id=uuid.uuid4(),
            conversation_id=conv.id,
            kind="image",
            mime_type="image/png",
            storage_path="print.png",
            original_filename="print ação.png",
            size_bytes=3,
            vision_description="tela de erro",
            uploaded_at=T0 + timedelta(seconds=30),
        )
        foreign = MessageAttachment(
            id=uuid.uuid4(),
            conversation_id=other.id,
            mime_type="image/png",
            storage_path="x.png",
            original_filename="x.png",
            uploaded_at=T0,
        )
        session.add_all([att, foreign])
        await session.commit()
        return {
            "conv": conv.id,
            "other": other.id,
            "ws": ws.id,
            "q2": q2,
            "att": att.id,
            "foreign": foreign.id,
        }


class _Storage:
    async def read(self, storage_path: str) -> bytes:
        if storage_path == "print.png":
            return b"png"
        raise FileNotFoundError(storage_path)


def _client(
    factory: async_sessionmaker[AsyncSession], scope: frozenset[uuid.UUID] | None
) -> httpx.AsyncClient:
    app = FastAPI()
    app.include_router(timeline.router, prefix="/api")

    async def db() -> AsyncGenerator[AsyncSession]:
        async with factory() as session:
            yield session

    user = User(id=uuid.uuid4(), email="adm@test.com", hashed_password="", role=UserRole.ADMIN)
    app.dependency_overrides[get_db_session] = db
    app.dependency_overrides[get_attachment_storage] = _Storage
    app.dependency_overrides[get_admin_scope] = lambda: AdminScope(user, scope)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")


async def test_anexo_fica_na_pergunta_enviada_depois_do_upload(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    ids = await _seed(factory)
    async with _client(factory, frozenset({ids["ws"]})) as client:
        items = (await client.get(f"/api/admin/conversations/{ids['conv']}/attachments")).json()
        file = await client.get(f"/api/admin/conversations/{ids['conv']}/attachments/{ids['att']}")

    assert [(i["original_filename"], i["message_id"]) for i in items] == [
        ("print ação.png", str(ids["q2"]))
    ]
    assert items[0]["has_description"] is True
    assert items[0]["preview_url"].startswith("/api/admin/conversations/")
    assert (file.status_code, file.content, file.headers["content-type"]) == (
        200,
        b"png",
        "image/png",
    )


async def test_anexo_de_outra_conversa_ou_sem_arquivo_da_404(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    ids = await _seed(factory)
    async with _client(factory, None) as client:
        foreign = await client.get(
            f"/api/admin/conversations/{ids['conv']}/attachments/{ids['foreign']}"
        )
        missing_file = await client.get(
            f"/api/admin/conversations/{ids['other']}/attachments/{ids['foreign']}"
        )
        missing_conv = await client.get(f"/api/admin/conversations/{uuid.uuid4()}/attachments")

    assert foreign.status_code == 404
    assert missing_file.status_code == 404
    assert missing_conv.status_code == 404


async def test_admin_de_outro_workspace_recebe_403(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    ids = await _seed(factory)
    base = f"/api/admin/conversations/{ids['conv']}"
    async with _client(factory, frozenset({uuid.uuid4()})) as client:
        codes = [
            (await client.get(path)).status_code
            for path in (
                f"{base}/activity",
                f"{base}/attachments",
                f"{base}/attachments/{ids['att']}",
            )
        ]
        no_ws = await client.get(f"/api/admin/conversations/{ids['other']}/attachments")

    assert codes == [403, 403, 403]
    assert no_ws.status_code == 403


async def test_atividade_usa_a_mesma_montagem_do_chat(
    factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = await _seed(factory)
    seen: list[uuid.UUID] = []

    async def fake_load(_db: AsyncSession, conversation_id: uuid.UUID) -> list[dict]:
        seen.append(conversation_id)
        return [{"task_id": "t1", "events": []}]

    monkeypatch.setattr(timeline, "load_conversation_activity", fake_load)
    async with _client(factory, frozenset({ids["ws"]})) as client:
        turns = (await client.get(f"/api/admin/conversations/{ids['conv']}/activity")).json()

    assert turns == [{"task_id": "t1", "events": []}]
    assert seen == [ids["conv"]]


async def test_usuario_comum_nao_entra() -> None:
    app = FastAPI()
    app.include_router(timeline.router, prefix="/api")
    app.dependency_overrides[get_authenticated_user] = lambda: User(
        id=uuid.uuid4(), email="u@test.com", hashed_password="", role=UserRole.USER
    )

    class _NoAdmin:
        async def admin_workspace_ids(self, _user_id: uuid.UUID) -> set[uuid.UUID]:
            return set()

    from app.adapters.primary.http import deps_auth

    app.dependency_overrides[deps_auth.get_workspace_admin_repo] = _NoAdmin
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://t"
    ) as client:
        response = await client.get(f"/api/admin/conversations/{uuid.uuid4()}/attachments")
    assert response.status_code == 403


def test_associacao_sem_pergunta_depois_fica_na_ultima() -> None:
    q1, q2, linked = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    questions = [(q1, T0), (q2, T0 + timedelta(minutes=1))]
    owners = timeline.assign_attachments_to_messages(
        [(None, T0 - timedelta(seconds=1)), (None, T0 + timedelta(hours=1)), (linked, T0)],
        questions,
    )
    assert owners == [q1, q2, linked]
    assert timeline.assign_attachments_to_messages([(None, T0)], []) == [None]
