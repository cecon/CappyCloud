"""Use cases for persistent per-user repository workspaces."""

from __future__ import annotations

import re
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha1

from app.domain.entities import Repository, User, UserRepositoryWorkspace
from app.domain.value_objects import UserWorkspaceStatus
from app.ports.repositories import RepositoryRepository
from app.ports.sandbox_workspaces import SandboxWorkspaceGateway
from app.ports.user_access import UserRepositoryAccessRepository
from app.ports.user_workspaces import UserRepositoryWorkspaceRepository


class UserWorkspaceAccessDeniedError(Exception):
    """Raised when a user cannot access the requested repository workspace."""


class UserWorkspaceNotFoundError(Exception):
    """Raised when a workspace record cannot be found for the current user."""


_SAFE_SEGMENT_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def _safe_segment(raw: object, fallback: str) -> str:
    value = _SAFE_SEGMENT_RE.sub("-", str(raw or "").strip()).strip(".-_")
    return (value or fallback)[:96]


def _sandbox_key(repo: Repository) -> str:
    return str(repo.sandbox_id) if repo.sandbox_id else "default"


def _workspace_path(user_id: uuid.UUID, repo: Repository, base_branch: str) -> str:
    user_part = user_id.hex[:12]
    slug = _safe_segment(repo.slug, repo.id.hex[:12])
    branch_safe = _safe_segment(base_branch, "main")
    branch_hash = sha1(base_branch.encode("utf-8")).hexdigest()[:8]
    branch = _safe_segment(f"{branch_safe}-{branch_hash}", branch_hash)
    sandbox = _safe_segment(_sandbox_key(repo), "default")
    return f"/repos/users/{user_part}/{sandbox}/{slug}/{branch}"


class EnsureUserRepositoryWorkspace:
    def __init__(
        self,
        workspaces: UserRepositoryWorkspaceRepository,
        repositories: RepositoryRepository,
        access: UserRepositoryAccessRepository,
        sandbox: SandboxWorkspaceGateway,
    ) -> None:
        self._workspaces = workspaces
        self._repositories = repositories
        self._access = access
        self._sandbox = sandbox

    async def execute(
        self,
        *,
        current_user: User,
        repository_id: uuid.UUID,
        base_branch: str | None = None,
    ) -> UserRepositoryWorkspace:
        repo = await self._visible_repository(current_user, repository_id)
        branch = str(base_branch or repo.default_branch or "main").strip() or "main"
        existing = await self._workspaces.get_for_scope(
            user_id=current_user.id,
            repository_id=repo.id,
            sandbox_key=_sandbox_key(repo),
            base_branch=branch,
        )
        now = datetime.now(UTC)
        workspace = existing or UserRepositoryWorkspace(
            id=uuid.uuid4(),
            user_id=current_user.id,
            repository_id=repo.id,
            sandbox_id=repo.sandbox_id,
            sandbox_key=_sandbox_key(repo),
            base_branch=branch,
            workspace_path=_workspace_path(current_user.id, repo, branch),
            status=UserWorkspaceStatus.PREPARING.value,
            last_used_at=now,
        )
        workspace.status = (
            UserWorkspaceStatus.REPAIRING.value
            if existing
            and existing.status
            in {UserWorkspaceStatus.MISSING.value, UserWorkspaceStatus.ERROR.value}
            else UserWorkspaceStatus.PREPARING.value
        )
        workspace.last_used_at = now
        workspace = await self._workspaces.save(workspace)

        clone_url = await self._repositories.get_authenticated_clone_url(repo.id)
        result = await self._sandbox.ensure_user_workspace(
            slug=repo.slug,
            base_branch=branch,
            workspace_path=workspace.workspace_path,
            clone_url=clone_url or repo.clone_url,
        )
        status = UserWorkspaceStatus.READY.value
        if result.dirty:
            status = UserWorkspaceStatus.DIRTY.value
        elif result.status in {UserWorkspaceStatus.MISSING.value, UserWorkspaceStatus.ERROR.value}:
            status = result.status
        updated = replace(
            workspace,
            workspace_path=result.workspace_path,
            status=status,
            health_message=result.message or result.action,
            last_prepared_at=now,
            last_used_at=now,
        )
        return await self._workspaces.save(updated)

    async def _visible_repository(self, current_user: User, repository_id: uuid.UUID) -> Repository:
        repo = await self._repositories.get(repository_id)
        if repo is None or not repo.active:
            raise UserWorkspaceNotFoundError("Repositório não encontrado.")
        if current_user.is_admin:
            return repo
        if not await self._access.has_access(current_user.id, repository_id):
            raise UserWorkspaceAccessDeniedError("Sem acesso a este repositório.")
        return repo


class ListUserRepositoryWorkspaces:
    def __init__(self, workspaces: UserRepositoryWorkspaceRepository) -> None:
        self._workspaces = workspaces

    async def execute(self, *, current_user: User) -> list[UserRepositoryWorkspace]:
        return await self._workspaces.list_for_user(current_user.id)


class DeleteUserRepositoryWorkspace:
    def __init__(
        self,
        workspaces: UserRepositoryWorkspaceRepository,
        sandbox: SandboxWorkspaceGateway,
    ) -> None:
        self._workspaces = workspaces
        self._sandbox = sandbox

    async def execute(self, *, current_user: User, workspace_id: uuid.UUID) -> bool:
        workspace = await self._workspaces.get(workspace_id)
        if workspace is None or workspace.user_id != current_user.id:
            raise UserWorkspaceNotFoundError("Workspace não encontrado.")
        await self._sandbox.delete_user_workspace(workspace_path=workspace.workspace_path)
        return await self._workspaces.delete(workspace_id, current_user.id)
