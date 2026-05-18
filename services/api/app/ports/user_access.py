"""Ports — permissões binárias user → recurso (ADR-005 §2).

3 repositórios independentes (sandbox, repository, ai_model). Cada um expõe
o mesmo conjunto mínimo de operações: listar ids permitidos, atribuir,
revogar, conferir.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from app.domain.entities import UserRole


class _UserAccessRepository(ABC):
    """Contrato base de permissão binária user → recurso."""

    @abstractmethod
    async def list_resources_for_user(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        """Devolve os ids de recursos aos quais o user tem acesso."""

    @abstractmethod
    async def has_access(self, user_id: uuid.UUID, resource_id: uuid.UUID) -> bool:
        """``True`` se existe linha (user_id, resource_id)."""

    @abstractmethod
    async def grant(self, user_id: uuid.UUID, resource_id: uuid.UUID) -> None:
        """Cria linha (user, recurso). Idempotente: se já existe, no-op."""

    @abstractmethod
    async def revoke(self, user_id: uuid.UUID, resource_id: uuid.UUID) -> bool:
        """Apaga linha. Devolve ``True`` se algo foi apagado."""


class UserSandboxAccessRepository(_UserAccessRepository):
    """Permissões user → sandbox."""


class UserRepositoryAccessRepository(_UserAccessRepository):
    """Permissões user → repository."""


class UserAiModelAccessRepository(_UserAccessRepository):
    """Permissões user → ai_model."""


class AiModelAccessPolicy(ABC):
    """Resolve o modelo LLM efetivo respeitando ativação global e acesso por user."""

    @abstractmethod
    async def resolve_model_for_user(
        self,
        user_id: uuid.UUID,
        role: UserRole,
        requested_model_id: str | None,
    ) -> str:
        """Retorna ``model_id`` utilizável ou levanta ``PermissionError``."""
