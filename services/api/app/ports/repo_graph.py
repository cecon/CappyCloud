"""Ports for repository graph exploration."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class RepositoryGraphProvider(ABC):
    """External provider capable of building a graph for a sandbox repository."""

    @abstractmethod
    async def fetch_graph(
        self,
        *,
        sandbox_host: str,
        sandbox_port: int,
        slug: str,
        max_files: int,
    ) -> dict[str, Any]:
        """Return the lightweight graph payload for a repository clone."""

    @abstractmethod
    async def fetch_commit_sha(
        self,
        *,
        sandbox_host: str,
        sandbox_port: int,
        slug: str,
        ref: str,
    ) -> str:
        """Return the resolved commit SHA for a sandbox repository ref."""
