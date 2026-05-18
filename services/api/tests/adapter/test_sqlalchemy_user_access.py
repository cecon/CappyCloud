"""Contract tests para os 3 UserAccessRepository (ADR-005 §2).

Os mesmos asserts rodam contra a impl in-memory e SQLAlchemy/SQLite,
provando LSP (Liskov): use cases que funcionam com fakes funcionam com
qualquer impl conformante.

Cobre também ``SQLAlchemyModelsByTierLookup``: filtra por tier e ignora
modelos com ``active=False``.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from app.adapters.secondary.persistence.sqlalchemy_models_by_tier import (
    SQLAlchemyModelsByTierLookup,
)
from app.adapters.secondary.persistence.sqlalchemy_user_access_repo import (
    SQLAlchemyUserAiModelAccessRepository,
    SQLAlchemyUserRepositoryAccessRepository,
    SQLAlchemyUserSandboxAccessRepository,
)
from app.domain.entities import ModelTier
from app.infrastructure.orm_models import AiModel, AiProvider, Base
from app.ports.user_access import (
    UserAiModelAccessRepository,
    UserRepositoryAccessRepository,
    UserSandboxAccessRepository,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.conftest import (
    InMemoryUserAiModelAccessRepository,
    InMemoryUserRepositoryAccessRepository,
    InMemoryUserSandboxAccessRepository,
)


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def sqlite_engine() -> AsyncGenerator[Any]:
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


# ── Sandbox access ───────────────────────────────────────────────────────────


@pytest.fixture(params=["in_memory", "sqlite"])
async def sandbox_access_impl(
    request: pytest.FixtureRequest, db_session: AsyncSession
) -> UserSandboxAccessRepository:
    if request.param == "in_memory":
        return InMemoryUserSandboxAccessRepository()
    return SQLAlchemyUserSandboxAccessRepository(db_session)


class TestUserSandboxAccessContract:
    async def test_grant_then_list_and_has_access(
        self, sandbox_access_impl: UserSandboxAccessRepository
    ) -> None:
        uid, sid = uuid.uuid4(), uuid.uuid4()
        await sandbox_access_impl.grant(uid, sid)

        assert await sandbox_access_impl.list_resources_for_user(uid) == [sid]
        assert await sandbox_access_impl.has_access(uid, sid) is True

    async def test_grant_is_idempotent(
        self, sandbox_access_impl: UserSandboxAccessRepository
    ) -> None:
        uid, sid = uuid.uuid4(), uuid.uuid4()
        await sandbox_access_impl.grant(uid, sid)
        await sandbox_access_impl.grant(uid, sid)

        # Idempotência efetiva: lista ainda tem 1 item, não 2.
        assert await sandbox_access_impl.list_resources_for_user(uid) == [sid]

    async def test_revoke_returns_true_and_removes(
        self, sandbox_access_impl: UserSandboxAccessRepository
    ) -> None:
        uid, sid = uuid.uuid4(), uuid.uuid4()
        await sandbox_access_impl.grant(uid, sid)

        assert await sandbox_access_impl.revoke(uid, sid) is True
        assert await sandbox_access_impl.has_access(uid, sid) is False

    async def test_revoke_returns_false_when_missing(
        self, sandbox_access_impl: UserSandboxAccessRepository
    ) -> None:
        assert await sandbox_access_impl.revoke(uuid.uuid4(), uuid.uuid4()) is False

    async def test_access_is_isolated_by_user(
        self, sandbox_access_impl: UserSandboxAccessRepository
    ) -> None:
        user_a, user_b = uuid.uuid4(), uuid.uuid4()
        sid = uuid.uuid4()
        await sandbox_access_impl.grant(user_a, sid)

        # Só o user_a vê — user_b continua sem acesso:
        assert sid in await sandbox_access_impl.list_resources_for_user(user_a)
        assert await sandbox_access_impl.list_resources_for_user(user_b) == []
        assert await sandbox_access_impl.has_access(user_b, sid) is False


# ── Repository access ───────────────────────────────────────────────────────


@pytest.fixture(params=["in_memory", "sqlite"])
async def repository_access_impl(
    request: pytest.FixtureRequest, db_session: AsyncSession
) -> UserRepositoryAccessRepository:
    if request.param == "in_memory":
        return InMemoryUserRepositoryAccessRepository()
    return SQLAlchemyUserRepositoryAccessRepository(db_session)


class TestUserRepositoryAccessContract:
    async def test_grant_revoke_roundtrip(
        self, repository_access_impl: UserRepositoryAccessRepository
    ) -> None:
        uid, rid = uuid.uuid4(), uuid.uuid4()
        await repository_access_impl.grant(uid, rid)

        assert await repository_access_impl.has_access(uid, rid) is True
        assert await repository_access_impl.revoke(uid, rid) is True
        assert await repository_access_impl.list_resources_for_user(uid) == []


# ── AI Model access ─────────────────────────────────────────────────────────


@pytest.fixture(params=["in_memory", "sqlite"])
async def ai_model_access_impl(
    request: pytest.FixtureRequest, db_session: AsyncSession
) -> UserAiModelAccessRepository:
    if request.param == "in_memory":
        return InMemoryUserAiModelAccessRepository()
    return SQLAlchemyUserAiModelAccessRepository(db_session)


class TestUserAiModelAccessContract:
    async def test_grant_revoke_roundtrip(
        self, ai_model_access_impl: UserAiModelAccessRepository
    ) -> None:
        uid, mid = uuid.uuid4(), uuid.uuid4()
        await ai_model_access_impl.grant(uid, mid)

        assert await ai_model_access_impl.has_access(uid, mid) is True
        assert await ai_model_access_impl.revoke(uid, mid) is True
        assert await ai_model_access_impl.list_resources_for_user(uid) == []


# ── ModelsByTierLookup (SQL only — sem fake equivalente) ────────────────────


@pytest.fixture
async def provider_id(db_session: AsyncSession) -> uuid.UUID:
    p = AiProvider(id=uuid.uuid4(), name=f"test-{uuid.uuid4()}", base_url="http://x")
    db_session.add(p)
    await db_session.commit()
    return p.id


def _ai_model(provider_id: uuid.UUID, tier: str, active: bool = True) -> AiModel:
    return AiModel(
        id=uuid.uuid4(),
        provider_id=provider_id,
        model_id=f"m-{uuid.uuid4()}",
        display_name="Test",
        capabilities=["text"],
        is_default={},
        context_window=4096,
        tier=tier,
        active=active,
    )


class TestModelsByTierLookup:
    async def test_returns_only_models_of_given_tier_and_active(
        self, db_session: AsyncSession, provider_id: uuid.UUID
    ) -> None:
        free_active = _ai_model(provider_id, tier="free", active=True)
        free_inactive = _ai_model(provider_id, tier="free", active=False)
        paid_active = _ai_model(provider_id, tier="paid", active=True)
        db_session.add_all([free_active, free_inactive, paid_active])
        await db_session.commit()

        lookup = SQLAlchemyModelsByTierLookup(db_session)
        free_ids = await lookup.list_active_model_ids_by_tier(ModelTier.FREE)

        # ``free_active`` aparece; ``free_inactive`` é filtrado por ``active``;
        # ``paid_active`` é filtrado pelo tier:
        assert free_active.id in free_ids
        assert free_inactive.id not in free_ids
        assert paid_active.id not in free_ids

    async def test_returns_empty_for_tier_without_models(self, db_session: AsyncSession) -> None:
        lookup = SQLAlchemyModelsByTierLookup(db_session)
        # Tier "unknown" não tem nenhum modelo nesta sessão:
        assert await lookup.list_active_model_ids_by_tier(ModelTier.UNKNOWN) == []
