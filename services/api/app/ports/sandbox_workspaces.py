"""Port for sandbox-side user workspace lifecycle operations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SandboxWorkspaceEnsureResult:
    workspace_path: str
    status: str
    action: str
    dirty: bool = False
    message: str = ""


@dataclass(frozen=True)
class SandboxWorkspaceDeleteResult:
    deleted: bool
    message: str = ""


class SandboxWorkspaceGateway:
    async def ensure_user_workspace(
        self,
        *,
        slug: str,
        base_branch: str,
        workspace_path: str,
        clone_url: str,
    ) -> SandboxWorkspaceEnsureResult:
        """Create, reuse, or repair a user baseline workspace in the sandbox."""
        raise NotImplementedError

    async def delete_user_workspace(self, *, workspace_path: str) -> SandboxWorkspaceDeleteResult:
        """Delete a user baseline workspace without touching conversation sessions."""
        raise NotImplementedError
