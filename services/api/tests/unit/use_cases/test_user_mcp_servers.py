from __future__ import annotations

import uuid

import pytest
from app.application.use_cases.user_mcp_servers import (
    CreateUserMcpServer,
    DeleteUserMcpServer,
    RotateUserMcpServerToken,
    UpdateUserMcpServer,
    UserMcpRepositoryDeniedError,
    UserMcpServerNameTakenError,
    hash_mcp_token,
)
from app.domain.entities import Repository, User, UserRole

from tests.conftest import (
    InMemoryRepositoryRepository,
    InMemoryUserMcpServerRepository,
    InMemoryUserRepositoryAccessRepository,
)


@pytest.fixture
def repos() -> InMemoryRepositoryRepository:
    return InMemoryRepositoryRepository()


@pytest.fixture
def access() -> InMemoryUserRepositoryAccessRepository:
    return InMemoryUserRepositoryAccessRepository()


@pytest.fixture
def mcp_repo() -> InMemoryUserMcpServerRepository:
    return InMemoryUserMcpServerRepository()


def _user(role: UserRole = UserRole.USER) -> User:
    return User(id=uuid.uuid4(), email="u@test.com", hashed_password="x", role=role)


def _repo() -> Repository:
    return Repository(
        id=uuid.uuid4(),
        slug="demo",
        name="Demo",
        clone_url="https://github.com/acme/demo.git",
    )


class TestCreateUserMcpServer:
    async def test_creates_token_once_for_allowed_repository(
        self,
        repos: InMemoryRepositoryRepository,
        access: InMemoryUserRepositoryAccessRepository,
        mcp_repo: InMemoryUserMcpServerRepository,
    ) -> None:
        current = _user()
        repository = _repo()
        repos.add(repository)
        await access.grant(current.id, repository.id)

        created = await CreateUserMcpServer(mcp_repo, repos, access).execute(
            current=current,
            repository_id=repository.id,
            name="Claude Demo",
        )

        assert created.token.startswith("cappy_mcp_")
        assert created.server.token_hash == hash_mcp_token(created.token)
        assert created.server.token_preview == created.token[-8:]
        assert created.server.repository_id == repository.id

    async def test_rejects_repository_without_user_access(
        self,
        repos: InMemoryRepositoryRepository,
        access: InMemoryUserRepositoryAccessRepository,
        mcp_repo: InMemoryUserMcpServerRepository,
    ) -> None:
        current = _user()
        repository = _repo()
        repos.add(repository)

        with pytest.raises(UserMcpRepositoryDeniedError):
            await CreateUserMcpServer(mcp_repo, repos, access).execute(
                current=current,
                repository_id=repository.id,
                name="No access",
            )

    async def test_admin_can_create_without_explicit_repository_access(
        self,
        repos: InMemoryRepositoryRepository,
        access: InMemoryUserRepositoryAccessRepository,
        mcp_repo: InMemoryUserMcpServerRepository,
    ) -> None:
        current = _user(UserRole.ADMIN)
        repository = _repo()
        repos.add(repository)

        created = await CreateUserMcpServer(mcp_repo, repos, access).execute(
            current=current,
            repository_id=repository.id,
            name="Admin MCP",
        )

        assert created.server.repository_id == repository.id

    async def test_rejects_duplicate_name_per_user(
        self,
        repos: InMemoryRepositoryRepository,
        access: InMemoryUserRepositoryAccessRepository,
        mcp_repo: InMemoryUserMcpServerRepository,
    ) -> None:
        current = _user(UserRole.ADMIN)
        repository = _repo()
        repos.add(repository)
        use_case = CreateUserMcpServer(mcp_repo, repos, access)
        await use_case.execute(current=current, repository_id=repository.id, name="dup")

        with pytest.raises(UserMcpServerNameTakenError):
            await use_case.execute(current=current, repository_id=repository.id, name="dup")


class TestRotateUserMcpServerToken:
    async def test_rotates_token_hash(
        self,
        repos: InMemoryRepositoryRepository,
        access: InMemoryUserRepositoryAccessRepository,
        mcp_repo: InMemoryUserMcpServerRepository,
    ) -> None:
        current = _user(UserRole.ADMIN)
        repository = _repo()
        repos.add(repository)
        created = await CreateUserMcpServer(mcp_repo, repos, access).execute(
            current=current,
            repository_id=repository.id,
            name="Rotate",
        )

        rotated = await RotateUserMcpServerToken(mcp_repo).execute(
            current=current,
            server_id=created.server.id,
        )

        assert rotated.token != created.token
        assert rotated.server.token_hash == hash_mcp_token(rotated.token)


class TestUpdateAndDeleteUserMcpServer:
    async def test_updates_name_repository_and_enabled_flag(
        self,
        repos: InMemoryRepositoryRepository,
        access: InMemoryUserRepositoryAccessRepository,
        mcp_repo: InMemoryUserMcpServerRepository,
    ) -> None:
        current = _user()
        first = _repo()
        second = Repository(
            id=uuid.uuid4(),
            slug="other",
            name="Other",
            clone_url="https://github.com/acme/other.git",
        )
        repos.add(first)
        repos.add(second)
        await access.grant(current.id, first.id)
        await access.grant(current.id, second.id)
        created = await CreateUserMcpServer(mcp_repo, repos, access).execute(
            current=current,
            repository_id=first.id,
            name="Original",
        )

        updated = await UpdateUserMcpServer(mcp_repo, repos, access).execute(
            current=current,
            server_id=created.server.id,
            repository_id=second.id,
            name="Updated",
            enabled=False,
        )

        assert updated.name == "Updated"
        assert updated.repository_id == second.id
        assert updated.enabled is False

    async def test_delete_is_scoped_to_owner(
        self,
        repos: InMemoryRepositoryRepository,
        access: InMemoryUserRepositoryAccessRepository,
        mcp_repo: InMemoryUserMcpServerRepository,
    ) -> None:
        owner = _user(UserRole.ADMIN)
        other = _user(UserRole.ADMIN)
        repository = _repo()
        repos.add(repository)
        created = await CreateUserMcpServer(mcp_repo, repos, access).execute(
            current=owner,
            repository_id=repository.id,
            name="Scoped",
        )

        assert (
            await DeleteUserMcpServer(mcp_repo).execute(
                current=other,
                server_id=created.server.id,
            )
            is False
        )
        assert (
            await DeleteUserMcpServer(mcp_repo).execute(
                current=owner,
                server_id=created.server.id,
            )
            is True
        )
