"""Use cases for user-scoped HTTP MCP servers."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.domain.entities import User, UserMcpServer, UserRole
from app.ports.mcp_repository import UserMcpServerRepository
from app.ports.repositories import RepositoryRepository
from app.ports.user_access import UserRepositoryAccessRepository


class UserMcpServerNotFoundError(Exception):
    """MCP HTTP não existe ou não pertence ao utilizador."""


class UserMcpServerNameTakenError(Exception):
    """Nome de MCP HTTP já usado pelo mesmo utilizador."""


class UserMcpRepositoryDeniedError(Exception):
    """Utilizador não pode expor este repositório por MCP."""


@dataclass(frozen=True)
class CreatedUserMcpServer:
    server: UserMcpServer
    token: str


def hash_mcp_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_mcp_token() -> str:
    return f"cappy_mcp_{secrets.token_urlsafe(32)}"


def token_preview(token: str) -> str:
    return token[-8:]


class _BaseUserMcpUseCase:
    def __init__(
        self,
        repo: UserMcpServerRepository,
        repositories: RepositoryRepository,
        access: UserRepositoryAccessRepository,
    ) -> None:
        self._repo = repo
        self._repositories = repositories
        self._access = access

    async def _ensure_repository_visible(self, current: User, repository_id: uuid.UUID) -> None:
        repository = await self._repositories.get(repository_id)
        if repository is None:
            raise UserMcpRepositoryDeniedError("Repositório não encontrado.")
        if current.role is UserRole.ADMIN:
            return
        if not await self._access.has_access(current.id, repository_id):
            raise UserMcpRepositoryDeniedError("Sem acesso a este repositório.")


class ListUserMcpServers:
    def __init__(self, repo: UserMcpServerRepository) -> None:
        self._repo = repo

    async def execute(self, user_id: uuid.UUID) -> list[UserMcpServer]:
        return await self._repo.list_for_user(user_id)


class CreateUserMcpServer(_BaseUserMcpUseCase):
    async def execute(
        self,
        *,
        current: User,
        repository_id: uuid.UUID,
        name: str,
        enabled: bool = True,
    ) -> CreatedUserMcpServer:
        await self._ensure_repository_visible(current, repository_id)
        normalised = name.strip()
        if not normalised:
            raise ValueError("Nome do MCP é obrigatório.")
        if await self._repo.get_by_name(normalised, current.id):
            raise UserMcpServerNameTakenError(f"MCP '{normalised}' já existe.")

        token = generate_mcp_token()
        server = UserMcpServer(
            id=uuid.uuid4(),
            user_id=current.id,
            repository_id=repository_id,
            name=normalised,
            token_hash=hash_mcp_token(token),
            token_preview=token_preview(token),
            enabled=enabled,
        )
        return CreatedUserMcpServer(server=await self._repo.create(server), token=token)


class UpdateUserMcpServer(_BaseUserMcpUseCase):
    async def execute(
        self,
        *,
        current: User,
        server_id: uuid.UUID,
        repository_id: uuid.UUID,
        name: str,
        enabled: bool,
    ) -> UserMcpServer:
        server = await self._repo.get(server_id, current.id)
        if server is None:
            raise UserMcpServerNotFoundError("MCP não encontrado.")
        await self._ensure_repository_visible(current, repository_id)
        normalised = name.strip()
        if not normalised:
            raise ValueError("Nome do MCP é obrigatório.")
        existing = await self._repo.get_by_name(normalised, current.id)
        if existing is not None and existing.id != server.id:
            raise UserMcpServerNameTakenError(f"MCP '{normalised}' já existe.")

        server.repository_id = repository_id
        server.name = normalised
        server.enabled = enabled
        server.updated_at = datetime.now(UTC)
        return await self._repo.update(server)


class RotateUserMcpServerToken:
    def __init__(self, repo: UserMcpServerRepository) -> None:
        self._repo = repo

    async def execute(self, *, current: User, server_id: uuid.UUID) -> CreatedUserMcpServer:
        server = await self._repo.get(server_id, current.id)
        if server is None:
            raise UserMcpServerNotFoundError("MCP não encontrado.")
        token = generate_mcp_token()
        server.token_hash = hash_mcp_token(token)
        server.token_preview = token_preview(token)
        server.updated_at = datetime.now(UTC)
        return CreatedUserMcpServer(server=await self._repo.update(server), token=token)


class DeleteUserMcpServer:
    def __init__(self, repo: UserMcpServerRepository) -> None:
        self._repo = repo

    async def execute(self, *, current: User, server_id: uuid.UUID) -> bool:
        return await self._repo.delete(server_id, current.id)
