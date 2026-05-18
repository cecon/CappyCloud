"""Unit tests for admin user access use cases (ADR-005 §2, ADR-006 §3)."""

from __future__ import annotations

import uuid

import pytest
from app.application.use_cases.admin_user_access import (
    BulkGrantAiModelsByTier,
    GrantAiModelAccess,
    GrantRepositoryAccess,
    GrantSandboxAccess,
    ListUserAiModelAccess,
    ListUserRepositoryAccess,
    ListUserSandboxAccess,
    ModelsByTierLookup,
    RevokeAiModelAccess,
    RevokeRepositoryAccess,
    RevokeSandboxAccess,
)
from app.domain.entities import ModelTier

from tests.conftest import (
    InMemoryUserAiModelAccessRepository,
    InMemoryUserRepositoryAccessRepository,
    InMemoryUserSandboxAccessRepository,
)


class _FakeModelsByTier(ModelsByTierLookup):
    def __init__(self, mapping: dict[ModelTier, list[uuid.UUID]]) -> None:
        self._mapping = mapping

    async def list_active_model_ids_by_tier(self, tier: ModelTier) -> list[uuid.UUID]:
        return list(self._mapping.get(tier, []))


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


class TestSandboxAccess:
    async def test_grant_then_list_returns_resource(self, user_id: uuid.UUID) -> None:
        repo = InMemoryUserSandboxAccessRepository()
        sandbox_id = uuid.uuid4()

        await GrantSandboxAccess(repo).execute(user_id, sandbox_id)
        result = await ListUserSandboxAccess(repo).execute(user_id)

        assert result == [sandbox_id]

    async def test_grant_is_idempotent(self, user_id: uuid.UUID) -> None:
        repo = InMemoryUserSandboxAccessRepository()
        sandbox_id = uuid.uuid4()

        await GrantSandboxAccess(repo).execute(user_id, sandbox_id)
        await GrantSandboxAccess(repo).execute(user_id, sandbox_id)
        result = await ListUserSandboxAccess(repo).execute(user_id)

        # Mesmo após 2 grants, apenas 1 resource_id no resultado:
        assert result == [sandbox_id]

    async def test_revoke_removes_pair(self, user_id: uuid.UUID) -> None:
        repo = InMemoryUserSandboxAccessRepository()
        sandbox_id = uuid.uuid4()
        await GrantSandboxAccess(repo).execute(user_id, sandbox_id)

        deleted = await RevokeSandboxAccess(repo).execute(user_id, sandbox_id)

        assert deleted is True
        assert await ListUserSandboxAccess(repo).execute(user_id) == []

    async def test_revoke_returns_false_when_missing(self, user_id: uuid.UUID) -> None:
        repo = InMemoryUserSandboxAccessRepository()
        deleted = await RevokeSandboxAccess(repo).execute(user_id, uuid.uuid4())
        assert deleted is False

    async def test_isolated_by_user(self) -> None:
        repo = InMemoryUserSandboxAccessRepository()
        user_a, user_b = uuid.uuid4(), uuid.uuid4()
        sandbox = uuid.uuid4()

        await GrantSandboxAccess(repo).execute(user_a, sandbox)

        assert await ListUserSandboxAccess(repo).execute(user_a) == [sandbox]
        assert await ListUserSandboxAccess(repo).execute(user_b) == []


class TestRepositoryAccess:
    async def test_grant_revoke_roundtrip(self, user_id: uuid.UUID) -> None:
        repo = InMemoryUserRepositoryAccessRepository()
        rid = uuid.uuid4()

        await GrantRepositoryAccess(repo).execute(user_id, rid)
        assert await ListUserRepositoryAccess(repo).execute(user_id) == [rid]
        assert await RevokeRepositoryAccess(repo).execute(user_id, rid) is True
        assert await ListUserRepositoryAccess(repo).execute(user_id) == []


class TestAiModelAccess:
    async def test_grant_revoke_roundtrip(self, user_id: uuid.UUID) -> None:
        repo = InMemoryUserAiModelAccessRepository()
        mid = uuid.uuid4()

        await GrantAiModelAccess(repo).execute(user_id, mid)
        assert await ListUserAiModelAccess(repo).execute(user_id) == [mid]
        assert await RevokeAiModelAccess(repo).execute(user_id, mid) is True


class TestBulkGrantAiModelsByTier:
    async def test_grants_all_free_models(self, user_id: uuid.UUID) -> None:
        free_ids = [uuid.uuid4() for _ in range(3)]
        repo = InMemoryUserAiModelAccessRepository()
        lookup = _FakeModelsByTier({ModelTier.FREE: free_ids, ModelTier.PAID: [uuid.uuid4()]})

        granted = await BulkGrantAiModelsByTier(repo, lookup).execute(user_id, ModelTier.FREE)

        assert granted == 3
        result = await ListUserAiModelAccess(repo).execute(user_id)
        assert set(result) == set(free_ids)

    async def test_idempotent_when_already_granted(self, user_id: uuid.UUID) -> None:
        free_ids = [uuid.uuid4(), uuid.uuid4()]
        repo = InMemoryUserAiModelAccessRepository()
        lookup = _FakeModelsByTier({ModelTier.FREE: free_ids})

        # 1ª chamada concede 2.
        first = await BulkGrantAiModelsByTier(repo, lookup).execute(user_id, ModelTier.FREE)
        # 2ª chamada não duplica (grant é idempotente no repo).
        second = await BulkGrantAiModelsByTier(repo, lookup).execute(user_id, ModelTier.FREE)

        assert first == 2 and second == 2  # ambas iteram a mesma lista
        result = await ListUserAiModelAccess(repo).execute(user_id)
        assert set(result) == set(free_ids)  # ainda só 2

    async def test_unknown_tier_returns_zero(self, user_id: uuid.UUID) -> None:
        repo = InMemoryUserAiModelAccessRepository()
        lookup = _FakeModelsByTier({})

        granted = await BulkGrantAiModelsByTier(repo, lookup).execute(user_id, ModelTier.UNKNOWN)

        assert granted == 0
        assert await ListUserAiModelAccess(repo).execute(user_id) == []
