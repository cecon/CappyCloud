"""Use cases for repository graph exploration."""

from __future__ import annotations

from typing import Any

from app.ports.repo_graph import RepositoryGraphProvider


class GetRepositoryGraph:
    """Build a lightweight code graph for a repository already cloned in a sandbox."""

    def __init__(self, provider: RepositoryGraphProvider) -> None:
        self._provider = provider

    async def execute(
        self,
        *,
        sandbox_host: str,
        sandbox_port: int,
        slug: str,
        max_files: int,
    ) -> dict[str, Any]:
        return await self._provider.fetch_graph(
            sandbox_host=sandbox_host,
            sandbox_port=sandbox_port,
            slug=slug,
            max_files=max_files,
        )
