"""SQLAlchemy implementation of RepositoryRepository port.

Lookup-only: este adapter cobre apenas as opera\u00e7\u00f5es necess\u00e1rias para que
use cases resolvam ``slug \u2192 id`` (ex.: ``CreateConversation``). O CRUD
completo da tabela ``repositories`` continua a viver no router admin
(``adapters/primary/http/repositories_admin.py``).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Repository as RepositoryEntity
from app.infrastructure.encryption import get_encryptor
from app.infrastructure.orm_models_platform import GitProvider as GitProviderORM
from app.infrastructure.orm_models_platform import Repository as RepositoryORM
from app.ports.repositories import RepositoryRepository


def _inject_token_in_url(url: str, token: str, provider_type: str) -> str:
    """Injeta PAT na clone_url para autentica\u00e7\u00e3o sem env vars globais."""
    if not token or not url:
        return url
    if provider_type == "github" and "github.com" in url:
        return url.replace("https://github.com", f"https://x-token:{token}@github.com", 1)
    if provider_type == "azure_devops" and "dev.azure.com" in url:
        return url.replace("https://dev.azure.com", f"https://pat:{token}@dev.azure.com", 1)
    if provider_type == "gitlab" and "gitlab.com" in url:
        return url.replace("https://gitlab.com", f"https://oauth2:{token}@gitlab.com", 1)
    # Gen\u00e9rico: injeta antes do host
    if url.startswith("https://"):
        host_start = len("https://")
        return f"https://token:{token}@{url[host_start:]}"
    return url


class SQLAlchemyRepositoryRepository(RepositoryRepository):
    """Concrete RepositoryRepository backed by PostgreSQL via SQLAlchemy async."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, repo_id: uuid.UUID) -> RepositoryEntity | None:
        row = await self._session.get(RepositoryORM, repo_id)
        return self._to_entity(row) if row else None

    async def get_by_slug(self, slug: str) -> RepositoryEntity | None:
        result = await self._session.execute(
            select(RepositoryORM).where(RepositoryORM.slug == slug)
        )
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def get_authenticated_clone_url(self, repo_id: uuid.UUID) -> str | None:
        repo_row = await self._session.get(RepositoryORM, repo_id)
        if not repo_row or not repo_row.provider_id:
            return repo_row.clone_url if repo_row else None

        provider_row = await self._session.get(GitProviderORM, repo_row.provider_id)
        if not provider_row or not provider_row.token_encrypted:
            return repo_row.clone_url

        try:
            token = get_encryptor().decrypt(provider_row.token_encrypted)
        except Exception:
            return repo_row.clone_url

        return _inject_token_in_url(repo_row.clone_url, token, provider_row.provider_type)

    @staticmethod
    def _to_entity(row: RepositoryORM) -> RepositoryEntity:
        return RepositoryEntity(
            id=row.id,
            slug=row.slug,
            name=row.name,
            clone_url=row.clone_url,
            default_branch=row.default_branch,
            provider_id=row.provider_id,
            sandbox_id=row.sandbox_id,
            sandbox_status=row.sandbox_status,
            sandbox_path=row.sandbox_path,
            last_sync_at=row.last_sync_at,
            error_message=row.error_message,
            active=row.active,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
