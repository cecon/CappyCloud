"""Fakes de workspaces por usuário (registro e gateway da sandbox).

Reexportados por ``conftest.py`` para que testes existentes continuem a
importar de lá.
"""

from __future__ import annotations

import uuid

from app.domain.entities import UserRepositoryWorkspace
from app.ports.sandbox_workspaces import (
    SandboxWorkspaceDeleteResult,
    SandboxWorkspaceEnsureResult,
    SandboxWorkspaceGateway,
)
from app.ports.user_workspaces import UserRepositoryWorkspaceRepository


class InMemoryUserWorkspaceRepository(UserRepositoryWorkspaceRepository):
    """In-memory user workspace registry for use case and HTTP tests."""

    def __init__(self) -> None:
        self.items: dict[uuid.UUID, UserRepositoryWorkspace] = {}

    async def get(self, workspace_id: uuid.UUID) -> UserRepositoryWorkspace | None:
        return self.items.get(workspace_id)

    async def get_for_scope(
        self,
        *,
        user_id: uuid.UUID,
        repository_id: uuid.UUID,
        sandbox_key: str,
        base_branch: str,
    ) -> UserRepositoryWorkspace | None:
        return next(
            (
                item
                for item in self.items.values()
                if item.user_id == user_id
                and item.repository_id == repository_id
                and item.sandbox_key == sandbox_key
                and item.base_branch == base_branch
            ),
            None,
        )

    async def list_for_user(self, user_id: uuid.UUID) -> list[UserRepositoryWorkspace]:
        return [item for item in self.items.values() if item.user_id == user_id]

    async def save(self, workspace: UserRepositoryWorkspace) -> UserRepositoryWorkspace:
        self.items[workspace.id] = workspace
        return workspace

    async def delete(self, workspace_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        item = self.items.get(workspace_id)
        if item is None or item.user_id != user_id:
            return False
        del self.items[workspace_id]
        return True


class FakeSandboxWorkspaceGateway(SandboxWorkspaceGateway):
    """Sandbox workspace fake that records calls and simulates repair/reuse."""

    def __init__(self) -> None:
        self.ensure_calls: list[dict[str, str]] = []
        self.delete_calls: list[str] = []
        self.next_result = SandboxWorkspaceEnsureResult(
            workspace_path="",
            status="ready",
            action="created",
        )

    async def ensure_user_workspace(
        self,
        *,
        slug: str,
        base_branch: str,
        workspace_path: str,
        clone_url: str,
    ) -> SandboxWorkspaceEnsureResult:
        self.ensure_calls.append(
            {
                "slug": slug,
                "base_branch": base_branch,
                "workspace_path": workspace_path,
                "clone_url": clone_url,
            }
        )
        action = "reused" if len(self.ensure_calls) > 1 else self.next_result.action
        return SandboxWorkspaceEnsureResult(
            workspace_path=self.next_result.workspace_path or workspace_path,
            status=self.next_result.status,
            action=action,
            dirty=self.next_result.dirty,
            message=self.next_result.message,
        )

    async def delete_user_workspace(self, *, workspace_path: str) -> SandboxWorkspaceDeleteResult:
        self.delete_calls.append(workspace_path)
        return SandboxWorkspaceDeleteResult(deleted=True)
