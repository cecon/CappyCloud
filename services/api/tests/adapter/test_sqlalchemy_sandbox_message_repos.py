"""Contract tests for sandbox and message repository adapters."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from app.adapters.secondary.persistence.sqlalchemy_message_repo import (
    SQLAlchemyMessageRepository,
)
from app.adapters.secondary.persistence.sqlalchemy_sandbox_repo import (
    SQLAlchemySandboxRepository,
)
from app.domain.entities import (
    ContainerStatus,
    Message,
    Sandbox,
    SandboxRuntime,
)
from app.infrastructure.orm_models import Base
from app.ports.repositories import MessageRepository, SandboxRepository
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.conftest import InMemoryMessageRepository, InMemorySandboxRepository


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


@pytest.fixture(params=["in_memory", "sqlite"])
async def sandbox_repo_impl(
    request: pytest.FixtureRequest, db_session: AsyncSession
) -> SandboxRepository:
    if request.param == "in_memory":
        return InMemorySandboxRepository()
    return SQLAlchemySandboxRepository(db_session)


def _sandbox(name: str = "alpha") -> Sandbox:
    return Sandbox(
        id=uuid.uuid4(),
        name=name,
        host=name,
        runtime=SandboxRuntime.COMPOSE,
        image="cappy/sandbox:latest",
        env_vars={"FOO": "bar"},
    )


class TestSandboxRepositoryContract:
    async def test_save_and_get(self, sandbox_repo_impl: SandboxRepository) -> None:
        sb = _sandbox("alpha")
        saved = await sandbox_repo_impl.save(sb)

        found = await sandbox_repo_impl.get(saved.id)

        assert found is not None
        assert found.name == "alpha"
        assert found.runtime is SandboxRuntime.COMPOSE
        assert found.env_vars == {"FOO": "bar"}
        assert found.container_status is ContainerStatus.NOT_CREATED

    async def test_get_by_name(self, sandbox_repo_impl: SandboxRepository) -> None:
        sb = _sandbox("by-name")
        await sandbox_repo_impl.save(sb)

        found = await sandbox_repo_impl.get_by_name("by-name")
        assert found is not None and found.id == sb.id

    async def test_get_by_name_returns_none_for_missing(
        self, sandbox_repo_impl: SandboxRepository
    ) -> None:
        assert await sandbox_repo_impl.get_by_name("nope") is None

    async def test_list_all_orders_by_created_at(
        self, sandbox_repo_impl: SandboxRepository
    ) -> None:
        a = await sandbox_repo_impl.save(_sandbox("alpha-list"))
        b = await sandbox_repo_impl.save(_sandbox("beta-list"))

        rows = await sandbox_repo_impl.list_all()

        names = [s.name for s in rows]
        assert "alpha-list" in names and "beta-list" in names
        ids = [s.id for s in rows if s.name in {"alpha-list", "beta-list"}]
        assert ids.index(a.id) < ids.index(b.id)

    async def test_update_container_status(self, sandbox_repo_impl: SandboxRepository) -> None:
        sb = await sandbox_repo_impl.save(_sandbox("alpha-status"))

        updated = await sandbox_repo_impl.update_container_status(sb.id, ContainerStatus.RUNNING)

        assert updated is not None
        assert updated.container_status is ContainerStatus.RUNNING
        assert updated.image == "cappy/sandbox:latest"
        reread = await sandbox_repo_impl.get(sb.id)
        assert reread is not None and reread.container_status is ContainerStatus.RUNNING

    async def test_update_container_status_returns_none_for_missing(
        self, sandbox_repo_impl: SandboxRepository
    ) -> None:
        result = await sandbox_repo_impl.update_container_status(
            uuid.uuid4(), ContainerStatus.RUNNING
        )
        assert result is None

    async def test_delete_returns_true_when_existed(
        self, sandbox_repo_impl: SandboxRepository
    ) -> None:
        sb = await sandbox_repo_impl.save(_sandbox("to-delete"))
        assert await sandbox_repo_impl.delete(sb.id) is True
        assert await sandbox_repo_impl.get(sb.id) is None

    async def test_delete_returns_false_when_missing(
        self, sandbox_repo_impl: SandboxRepository
    ) -> None:
        assert await sandbox_repo_impl.delete(uuid.uuid4()) is False


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
