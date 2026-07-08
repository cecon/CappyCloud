"""HTTP adapter for sandbox user workspace operations."""

from __future__ import annotations

import os

import httpx

from app.ports.sandbox_workspaces import (
    SandboxWorkspaceDeleteResult,
    SandboxWorkspaceEnsureResult,
    SandboxWorkspaceGateway,
)


class SandboxUserWorkspaceClient(SandboxWorkspaceGateway):
    def __init__(self, base_url: str | None = None) -> None:
        if base_url:
            self._base_url = base_url.rstrip("/")
        else:
            host = os.getenv("SANDBOX_HOST", "cappycloud-sandbox")
            port = os.getenv("SANDBOX_SESSION_PORT", "8080")
            self._base_url = f"http://{host}:{port}"

    async def ensure_user_workspace(
        self,
        *,
        slug: str,
        base_branch: str,
        workspace_path: str,
        clone_url: str,
    ) -> SandboxWorkspaceEnsureResult:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self._base_url}/user-workspaces/ensure",
                json={
                    "slug": slug,
                    "base_branch": base_branch,
                    "workspace_path": workspace_path,
                    "clone_url": clone_url,
                },
            )
        if resp.status_code >= 400:
            raise RuntimeError(f"sandbox workspace ensure failed: {resp.status_code} {resp.text}")
        data = resp.json()
        return SandboxWorkspaceEnsureResult(
            workspace_path=str(data.get("workspace_path") or workspace_path),
            status=str(data.get("status") or "ready"),
            action=str(data.get("action") or "reused"),
            dirty=bool(data.get("dirty") or False),
            message=str(data.get("message") or ""),
        )

    async def delete_user_workspace(self, *, workspace_path: str) -> SandboxWorkspaceDeleteResult:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.delete(
                f"{self._base_url}/user-workspaces",
                params={"workspace_path": workspace_path},
            )
        if resp.status_code >= 400:
            raise RuntimeError(f"sandbox workspace delete failed: {resp.status_code} {resp.text}")
        data = resp.json()
        return SandboxWorkspaceDeleteResult(
            deleted=bool(data.get("deleted") or False),
            message=str(data.get("message") or ""),
        )
