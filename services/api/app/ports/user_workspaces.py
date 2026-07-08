"""Ports for per-user repository workspace persistence."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from app.domain.entities import UserRepositoryWorkspace


class UserRepositoryWorkspaceRepository(ABC):
    """Persistence contract for user-owned prepared repository workspaces."""

    @abstractmethod
    async def get(self, workspace_id: uuid.UUID) -> UserRepositoryWorkspace | None:
        """Return a workspace by primary key, or None."""

    @abstractmethod
    async def get_for_scope(
        self,
        *,
        user_id: uuid.UUID,
        repository_id: uuid.UUID,
        sandbox_key: str,
        base_branch: str,
    ) -> UserRepositoryWorkspace | None:
        """Return the unique workspace for a user/repository/sandbox/branch scope."""

    @abstractmethod
    async def list_for_user(self, user_id: uuid.UUID) -> list[UserRepositoryWorkspace]:
        """Return all workspace records owned by a user."""

    @abstractmethod
    async def save(self, workspace: UserRepositoryWorkspace) -> UserRepositoryWorkspace:
        """Insert or update a workspace record."""

    @abstractmethod
    async def delete(self, workspace_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Delete a workspace record owned by the user."""
