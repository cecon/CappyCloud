"""Use cases administrativos para permissões binárias (ADR-005 §2).

Camada pura. Caller (HTTP) verifica papel via ``require_role(ADMIN)``.

Inclui bulk-assign de modelos por tier (ADR-006 §3): liberar todos os
modelos ``free`` para um utilizador é o caso mais comum, então merece
endpoint dedicado para evitar N chamadas individuais.
"""

from __future__ import annotations

import uuid

from app.domain.entities import ModelTier
from app.ports.user_access import (
    UserAiModelAccessRepository,
    UserRepositoryAccessRepository,
    UserSandboxAccessRepository,
)


class ListUserSandboxAccess:
    def __init__(self, repo: UserSandboxAccessRepository) -> None:
        self._repo = repo

    async def execute(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        return await self._repo.list_resources_for_user(user_id)


class GrantSandboxAccess:
    def __init__(self, repo: UserSandboxAccessRepository) -> None:
        self._repo = repo

    async def execute(self, user_id: uuid.UUID, sandbox_id: uuid.UUID) -> None:
        await self._repo.grant(user_id, sandbox_id)


class RevokeSandboxAccess:
    def __init__(self, repo: UserSandboxAccessRepository) -> None:
        self._repo = repo

    async def execute(self, user_id: uuid.UUID, sandbox_id: uuid.UUID) -> bool:
        return await self._repo.revoke(user_id, sandbox_id)


class ListUserRepositoryAccess:
    def __init__(self, repo: UserRepositoryAccessRepository) -> None:
        self._repo = repo

    async def execute(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        return await self._repo.list_resources_for_user(user_id)


class GrantRepositoryAccess:
    def __init__(self, repo: UserRepositoryAccessRepository) -> None:
        self._repo = repo

    async def execute(self, user_id: uuid.UUID, repository_id: uuid.UUID) -> None:
        await self._repo.grant(user_id, repository_id)


class RevokeRepositoryAccess:
    def __init__(self, repo: UserRepositoryAccessRepository) -> None:
        self._repo = repo

    async def execute(self, user_id: uuid.UUID, repository_id: uuid.UUID) -> bool:
        return await self._repo.revoke(user_id, repository_id)


class ListUserAiModelAccess:
    def __init__(self, repo: UserAiModelAccessRepository) -> None:
        self._repo = repo

    async def execute(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        return await self._repo.list_resources_for_user(user_id)


class GrantAiModelAccess:
    def __init__(self, repo: UserAiModelAccessRepository) -> None:
        self._repo = repo

    async def execute(self, user_id: uuid.UUID, ai_model_id: uuid.UUID) -> None:
        await self._repo.grant(user_id, ai_model_id)


class RevokeAiModelAccess:
    def __init__(self, repo: UserAiModelAccessRepository) -> None:
        self._repo = repo

    async def execute(self, user_id: uuid.UUID, ai_model_id: uuid.UUID) -> bool:
        return await self._repo.revoke(user_id, ai_model_id)


class BulkGrantAiModelsByTier:
    """Libera todos os modelos ativos de um ``tier`` para o utilizador.

    Útil para "dar acesso ao plano free": uma chamada em vez de N. Operação
    idempotente — modelos já liberados continuam liberados (grant é no-op
    em duplicata).

    Recebe um *lookup* de modelos por tier (callback) para manter a camada
    de aplicação independente de SQLAlchemy.
    """

    def __init__(
        self,
        access_repo: UserAiModelAccessRepository,
        models_by_tier: ModelsByTierLookup,
    ) -> None:
        self._access = access_repo
        self._lookup = models_by_tier

    async def execute(self, user_id: uuid.UUID, tier: ModelTier) -> int:
        ids = await self._lookup.list_active_model_ids_by_tier(tier)
        for model_id in ids:
            await self._access.grant(user_id, model_id)
        return len(ids)


class ModelsByTierLookup:
    """Port estreito para resolver ``tier → [ai_model_id]``. Adapter usa SQL."""

    async def list_active_model_ids_by_tier(self, tier: ModelTier) -> list[uuid.UUID]:
        raise NotImplementedError
