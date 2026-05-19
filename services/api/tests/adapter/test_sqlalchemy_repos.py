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
from app.adapters.secondary.persistence.sqlalchemy_user_repo import (
    SQLAlchemyUserRepository,
)
from app.domain.entities import (
    Conversation,
    User,
    UserRole,
)
from app.infrastructure.orm_models import Base
from app.ports.repositories import (
    ConversationRepository,
    UserRepository,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.conftest import (
    InMemoryConversationRepository,
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
async def db_session(sqlite_engine: Any) -> AsyncGenerator[AsyncSession]:
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

    async def test_role_defaults_to_user(self, user_repo_impl: UserRepository) -> None:
        user = User(id=uuid.uuid4(), email="default@test.com", hashed_password="x")
        await user_repo_impl.save(user)
        found = await user_repo_impl.get_by_email("default@test.com")
        assert found is not None
        assert found.role is UserRole.USER

    async def test_admin_role_is_persisted(self, user_repo_impl: UserRepository) -> None:
        user = User(
            id=uuid.uuid4(),
            email="admin@test.com",
            hashed_password="x",
            role=UserRole.ADMIN,
        )
        await user_repo_impl.save(user)
        found = await user_repo_impl.get_by_email("admin@test.com")
        assert found is not None
        assert found.role is UserRole.ADMIN
        assert found.is_admin is True

    async def test_super_admin_flag_is_persisted(self, user_repo_impl: UserRepository) -> None:
        user = User(
            id=uuid.uuid4(),
            email="super@test.com",
            hashed_password="x",
            role=UserRole.ADMIN,
            is_super_admin=True,
        )
        await user_repo_impl.save(user)
        found = await user_repo_impl.get_by_email("super@test.com")
        assert found is not None
        assert found.is_super_admin is True

    async def test_must_change_password_flag_is_persisted(
        self, user_repo_impl: UserRepository
    ) -> None:
        user = User(
            id=uuid.uuid4(),
            email="must-change@test.com",
            hashed_password="x",
            must_change_password=True,
        )
        await user_repo_impl.save(user)
        found = await user_repo_impl.get_by_email("must-change@test.com")
        assert found is not None
        assert found.must_change_password is True

    async def test_list_all_returns_saved_users(self, user_repo_impl: UserRepository) -> None:
        u1 = User(id=uuid.uuid4(), email="list1@test.com", hashed_password="x")
        u2 = User(
            id=uuid.uuid4(),
            email="list2@test.com",
            hashed_password="x",
            role=UserRole.ADMIN,
        )
        await user_repo_impl.save(u1)
        await user_repo_impl.save(u2)

        all_users = await user_repo_impl.list_all()

        emails = {u.email for u in all_users}
        assert {"list1@test.com", "list2@test.com"}.issubset(emails)
        # Papéis foram preservados na listagem (não voltam tudo USER):
        by_email = {u.email: u for u in all_users}
        assert by_email["list1@test.com"].role is UserRole.USER
        assert by_email["list2@test.com"].role is UserRole.ADMIN

    async def test_update_role_promotes_existing_user(self, user_repo_impl: UserRepository) -> None:
        user = User(id=uuid.uuid4(), email="prom@test.com", hashed_password="x")
        await user_repo_impl.save(user)

        updated = await user_repo_impl.update_role(user.id, UserRole.ADMIN)

        assert updated is not None
        assert updated.role is UserRole.ADMIN
        # Persistido — re-ler do repo confirma:
        reread = await user_repo_impl.get_by_id(user.id)
        assert reread is not None and reread.is_admin

    async def test_update_role_returns_none_for_missing_user(
        self, user_repo_impl: UserRepository
    ) -> None:
        assert await user_repo_impl.update_role(uuid.uuid4(), UserRole.ADMIN) is None

    async def test_update_password_clears_required_change(
        self, user_repo_impl: UserRepository
    ) -> None:
        user = User(
            id=uuid.uuid4(),
            email="change-pass@test.com",
            hashed_password="old",
            must_change_password=True,
        )
        await user_repo_impl.save(user)

        updated = await user_repo_impl.update_password(
            user.id,
            "new",
            must_change_password=False,
        )

        assert updated is not None
        assert updated.hashed_password == "new"
        assert updated.must_change_password is False
        reread = await user_repo_impl.get_by_id(user.id)
        assert reread is not None
        assert reread.hashed_password == "new"
        assert reread.must_change_password is False


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
