"""Sandbox sidecar adapter for repository graph data."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from app.ports.repo_graph import RepositoryGraphProvider


class SandboxRepoGraphError(RuntimeError):
    """Raised when the sandbox cannot build a repository graph."""

    def __init__(self, message: str, *, status_code: int = 503) -> None:
        super().__init__(message)
        self.status_code = status_code


class SandboxRepositoryGraphProvider(RepositoryGraphProvider):
    """RepositoryGraphProvider backed by session_server.js in the sandbox."""

    async def fetch_graph(
        self,
        *,
        sandbox_host: str,
        sandbox_port: int,
        slug: str,
        max_files: int,
    ) -> dict[str, Any]:
        safe_slug = quote(slug, safe="")
        url = f"http://{sandbox_host}:{sandbox_port}/repos/{safe_slug}/graph"
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
                response = await client.get(url, params={"max_files": max_files})
        except httpx.RequestError as exc:
            raise SandboxRepoGraphError(f"Falha ao conectar ao sandbox: {exc}") from exc

        data: object = {}
        if response.headers.get("content-type", "").startswith("application/json"):
            data = response.json()
        if response.status_code < 400 and isinstance(data, dict):
            return data

        detail = ""
        if isinstance(data, dict):
            detail = str(data.get("detail") or data.get("error") or "").strip()
        if not detail:
            detail = response.text[:800] if response.text else f"HTTP {response.status_code}"
        raise SandboxRepoGraphError(detail, status_code=response.status_code)
