"""In-memory fakes para os ``UserAccessRepository`` (ADR-005 §2).

Sob arquivo separado para manter ``conftest.py`` abaixo do limite de 300
linhas (regra do projeto). Re-exportados pelo conftest.
"""

from __future__ import annotations

import uuid

from app.ports.user_access import (
    UserAiModelAccessRepository,
    UserRepositoryAccessRepository,
    UserSandboxAccessRepository,
)


class _InMemoryAccessStore:
    """Implementação compartilhada para os 3 tipos de access."""

    def __init__(self) -> None:
        self._pairs: set[tuple[uuid.UUID, uuid.UUID]] = set()

    async def list_resources_for_user(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        return [rid for (uid, rid) in self._pairs if uid == user_id]

    async def has_access(self, user_id: uuid.UUID, resource_id: uuid.UUID) -> bool:
        return (user_id, resource_id) in self._pairs

    async def grant(self, user_id: uuid.UUID, resource_id: uuid.UUID) -> None:
        self._pairs.add((user_id, resource_id))

    async def revoke(self, user_id: uuid.UUID, resource_id: uuid.UUID) -> bool:
        pair = (user_id, resource_id)
        if pair in self._pairs:
            self._pairs.remove(pair)
            return True
        return False


class InMemoryUserSandboxAccessRepository(_InMemoryAccessStore, UserSandboxAccessRepository):
    pass


class InMemoryUserRepositoryAccessRepository(_InMemoryAccessStore, UserRepositoryAccessRepository):
    pass


class InMemoryUserAiModelAccessRepository(_InMemoryAccessStore, UserAiModelAccessRepository):
    pass
