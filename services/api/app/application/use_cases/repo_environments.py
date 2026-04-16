"""Repo environment use cases — manage global repository environments."""

from __future__ import annotations

import uuid

from app.domain.entities import RepoEnvironment
from app.ports.repositories import RepoEnvironmentRepository


class ListRepoEnvironments:
    """Return all global repo environments."""

    def __init__(self, repo_envs: RepoEnvironmentRepository) -> None:
        self._repo_envs = repo_envs

    async def execute(self) -> list[RepoEnvironment]:
        return await self._repo_envs.list_all()


class CreateRepoEnvironment:
    """Create a new global repo environment."""

    def __init__(self, repo_envs: RepoEnvironmentRepository) -> None:
        self._repo_envs = repo_envs

    async def execute(
        self,
        slug: str,
        name: str,
        repo_url: str,
        branch: str = "main",
    ) -> RepoEnvironment:
        existing = await self._repo_envs.get_by_slug(slug)
        if existing:
            raise ValueError(f"Ambiente com slug '{slug}' já existe.")
        env = RepoEnvironment(
            id=uuid.uuid4(),
            slug=slug,
            name=name,
            repo_url=repo_url,
            branch=branch,
        )
        return await self._repo_envs.save(env)


class DeleteRepoEnvironment:
    """Delete a global repo environment."""

    def __init__(
        self,
        repo_envs: RepoEnvironmentRepository,
    ) -> None:
        self._repo_envs = repo_envs

    async def execute(self, env_id: uuid.UUID) -> None:
        env = await self._repo_envs.get(env_id)
        if not env:
            raise LookupError("Ambiente não encontrado.")
        await self._repo_envs.delete(env_id)
