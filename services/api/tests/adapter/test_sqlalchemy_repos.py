"""LSP contract tests — same assertions run against both in-memory and SQLite adapters.

Proves that SQLAlchemyXxxRepository and InMemoryXxxRepository satisfy
the same port contract (Liskov Substitution Principle).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from app.adapters.secondary.persistence.sqlalchemy_conversation_repo import (
    SQLAlchemyConversationRepository,
)
from app.adapters.secondary.persistence.sqlalchemy_message_repo import (
    SQLAlchemyMessageRepository,
)
from app.adapters.secondary.persistence.sqlalchemy_user_repo import (
    SQLAlchemyUserRepository,
)
from app.domain.entities import Conversation, Message, User
from app.infrastructure.orm_models import Base
from app.ports.repositories import ConversationRepository, MessageRepository, UserRepository
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.conftest import (
    InMemoryConversationRepository,
    InMemoryMessageRepository,
    InMemoryUserRepository,
)

# ---------------------------------------------------------------------------
# SQLite in-memory fixtures for adapter tests (no PostgreSQL required in CI)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def sqlite_engine():  # type: ignore[no-untyped-def]
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(sqlite_engine: Any) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(sqlite_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


# ---------------------------------------------------------------------------
# UserRepository contract tests
# ---------------------------------------------------------------------------


@pytest.fixture(params=["in_memory", "sqlite"])
async def user_repo_impl(
    request: pytest.FixtureRequest, db_session: AsyncSession
) -> UserRepository:
    if request.param == "in_memory":
        return InMemoryUserRepository()
    return SQLAlchemyUserRepository(db_session)


class TestUserRepositoryContract:
    """Same assertions run against all UserRepository implementations."""

    async def test_save_and_get_by_id(self, user_repo_impl: UserRepository) -> None:
        user = User(id=uuid.uuid4(), email="a@b.com", hashed_password="x")
        saved = await user_repo_impl.save(user)
        found = await user_repo_impl.get_by_id(saved.id)
        assert found is not None
        assert found.id == saved.id
        assert found.email == "a@b.com"

    async def test_get_by_id_returns_none_for_missing(self, user_repo_impl: UserRepository) -> None:
        assert await user_repo_impl.get_by_id(uuid.uuid4()) is None

    async def test_save_and_get_by_email(self, user_repo_impl: UserRepository) -> None:
        user = User(id=uuid.uuid4(), email="find@test.com", hashed_password="y")
        await user_repo_impl.save(user)
        found = await user_repo_impl.get_by_email("find@test.com")
        assert found is not None
        assert found.email == "find@test.com"

    async def test_get_by_email_returns_none_for_missing(
        self, user_repo_impl: UserRepository
    ) -> None:
        assert await user_repo_impl.get_by_email("nobody@x.com") is None


# ---------------------------------------------------------------------------
# ConversationRepository contract tests
# ---------------------------------------------------------------------------


@pytest.fixture(params=["in_memory", "sqlite"])
async def conv_repo_impl(
    request: pytest.FixtureRequest, db_session: AsyncSession, user_repo_impl: UserRepository
) -> ConversationRepository:
    if request.param == "in_memory":
        return InMemoryConversationRepository()
    return SQLAlchemyConversationRepository(db_session)


class TestConversationRepositoryContract:
    async def test_save_and_get(self, conv_repo_impl: ConversationRepository) -> None:
        uid = uuid.uuid4()
        # For SQLite: user must exist (FK). In-memory: no FK.
        conv = Conversation(id=uuid.uuid4(), user_id=uid, title="Test")
        # In-memory impl has no FK, SQLite impl will fail on FK — skip FK constraint for portability
        # (SQLite FK enforcement is off by default)
        saved = await conv_repo_impl.save(conv)
        found = await conv_repo_impl.get(saved.id, uid)
        assert found is not None
        assert found.title == "Test"

    async def test_get_returns_none_for_wrong_user(
        self, conv_repo_impl: ConversationRepository
    ) -> None:
        uid = uuid.uuid4()
        conv = Conversation(id=uuid.uuid4(), user_id=uid, title="Mine")
        saved = await conv_repo_impl.save(conv)
        assert await conv_repo_impl.get(saved.id, uuid.uuid4()) is None

    async def test_list_by_user(self, conv_repo_impl: ConversationRepository) -> None:
        uid = uuid.uuid4()
        other = uuid.uuid4()
        await conv_repo_impl.save(Conversation(id=uuid.uuid4(), user_id=uid, title="A"))
        await conv_repo_impl.save(Conversation(id=uuid.uuid4(), user_id=other, title="B"))
        result = await conv_repo_impl.list_by_user(uid)
        assert all(c.user_id == uid for c in result)
        assert len(result) >= 1

    async def test_update_title(self, conv_repo_impl: ConversationRepository) -> None:
        uid = uuid.uuid4()
        conv = Conversation(id=uuid.uuid4(), user_id=uid, title="Original")
        saved = await conv_repo_impl.save(conv)
        saved.title = "Updated"
        await conv_repo_impl.update(saved)
        found = await conv_repo_impl.get(saved.id, uid)
        assert found is not None
        assert found.title == "Updated"


# ---------------------------------------------------------------------------
# MessageRepository contract tests
# ---------------------------------------------------------------------------


@pytest.fixture(params=["in_memory", "sqlite"])
async def msg_repo_impl(
    request: pytest.FixtureRequest, db_session: AsyncSession
) -> MessageRepository:
    if request.param == "in_memory":
        return InMemoryMessageRepository()
    return SQLAlchemyMessageRepository(db_session)


class TestMessageRepositoryContract:
    async def test_save_and_list(self, msg_repo_impl: MessageRepository) -> None:
        conv_id = uuid.uuid4()
        msg = Message(id=uuid.uuid4(), conversation_id=conv_id, role="user", content="Olá")
        await msg_repo_impl.save(msg)
        msgs = await msg_repo_impl.list_by_conversation(conv_id)
        assert len(msgs) >= 1
        assert msgs[0].content == "Olá"

    async def test_list_returns_only_matching_conversation(
        self, msg_repo_impl: MessageRepository
    ) -> None:
        cid_a = uuid.uuid4()
        cid_b = uuid.uuid4()
        await msg_repo_impl.save(
            Message(id=uuid.uuid4(), conversation_id=cid_a, role="user", content="A")
        )
        await msg_repo_impl.save(
            Message(id=uuid.uuid4(), conversation_id=cid_b, role="user", content="B")
        )
        result = await msg_repo_impl.list_by_conversation(cid_a)
        assert all(m.conversation_id == cid_a for m in result)
