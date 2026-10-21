"""Port de leitura dos acessos a workspace usados pelo escopo de admin."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from collections.abc import Iterable


class WorkspaceAdminRepository(ABC):
    @abstractmethod
    async def admin_workspace_ids(self, user_id: uuid.UUID) -> set[uuid.UUID]:
        """Workspaces em que o usuário é admin (``is_admin``)."""

    @abstractmethod
    async def member_workspace_ids(self, user_id: uuid.UUID) -> set[uuid.UUID]:
        """Workspaces a que o usuário tem acesso (admin ou não)."""

    @abstractmethod
    async def member_user_ids(self, workspace_ids: Iterable[uuid.UUID]) -> set[uuid.UUID]:
        """Usuários com acesso a algum dos workspaces."""

    @abstractmethod
    async def grant_access(self, user_id: uuid.UUID, workspace_id: uuid.UUID) -> None:
        """Libera o workspace (idempotente)."""

    @abstractmethod
    async def copy_model_access(self, from_user_id: uuid.UUID, to_user_id: uuid.UUID) -> None:
        """Dá ao segundo usuário os modelos LLM liberados para o primeiro."""
