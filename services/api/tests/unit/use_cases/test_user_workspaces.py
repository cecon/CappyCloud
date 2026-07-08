from __future__ import annotations

import uuid

import pytest

from app.application.use_cases.user_workspaces import (
    EnsureUserRepositoryWorkspace,
    UserWorkspaceAccessDeniedError,
)
from app.domain.entities import Repository, User, UserRepositoryWorkspace
from app.ports.sandbox_workspaces import SandboxWorkspaceEnsureResult
from tests.conftest import FakeSandboxWorkspaceGateway, InMemoryUserWorkspaceRepository


class FakeAccess:
    def __init__(self) -> None:
        self.allowed: set[tuple[uuid.UUID, uuid.UUID]] = set()

    async def has_access(self, user_id: uuid.UUID, resource_id: uuid.UUID) -> bool:
        return (user_id, resource_id) in self.allowed


@pytest.mark.asyncio
async def test_ensure_reuses_same_workspace_for_same_user_and_branch(repository_repo) -> None:
    user = User(id=uuid.uuid4(), email="u@test.com", hashed_password="x")
    repo = Repository(
        id=uuid.uuid4(),
        slug="seller",
        name="Seller",
        clone_url="https://dev.azure.com/org/project/_git/Seller",
        default_branch="main",
    )
    repository_repo.add(repo)
    workspaces = InMemoryUserWorkspaceRepository()
    access = FakeAccess()
    access.allowed.add((user.id, repo.id))
    sandbox = FakeSandboxWorkspaceGateway()
    uc = EnsureUserRepositoryWorkspace(workspaces, repository_repo, access, sandbox)

    first = await uc.execute(current_user=user, repository_id=repo.id, base_branch="main")
    second = await uc.execute(current_user=user, repository_id=repo.id, base_branch="main")

    assert second.id == first.id
    assert second.workspace_path == first.workspace_path
    assert second.status == "ready"
    assert len(sandbox.ensure_calls) == 2


@pytest.mark.asyncio
async def test_ensure_preserves_branch_name_with_slashes_for_git(repository_repo) -> None:
    user = User(id=uuid.uuid4(), email="u@test.com", hashed_password="x")
    repo = Repository(
        id=uuid.uuid4(),
        slug="seller",
        name="Seller",
        clone_url="https://dev.azure.com/org/project/_git/Seller",
        default_branch="main",
    )
    repository_repo.add(repo)
    workspaces = InMemoryUserWorkspaceRepository()
    access = FakeAccess()
    access.allowed.add((user.id, repo.id))
    sandbox = FakeSandboxWorkspaceGateway()
    uc = EnsureUserRepositoryWorkspace(workspaces, repository_repo, access, sandbox)

    workspace = await uc.execute(
        current_user=user,
        repository_id=repo.id,
        base_branch="SellerWeb/PROD/V11/45/11.45.000X",
    )

    assert sandbox.ensure_calls[0]["base_branch"] == "SellerWeb/PROD/V11/45/11.45.000X"
    assert workspace.base_branch == "SellerWeb/PROD/V11/45/11.45.000X"
    assert "/seller/SellerWeb-PROD-V11-45-11.45.000X-" in workspace.workspace_path


@pytest.mark.asyncio
async def test_ensure_uses_distinct_workspace_for_distinct_users(repository_repo) -> None:
    user_a = User(id=uuid.uuid4(), email="a@test.com", hashed_password="x")
    user_b = User(id=uuid.uuid4(), email="b@test.com", hashed_password="x")
    repo = Repository(
        id=uuid.uuid4(),
        slug="seller",
        name="Seller",
        clone_url="https://github.com/acme/seller.git",
        default_branch="main",
    )
    repository_repo.add(repo)
    workspaces = InMemoryUserWorkspaceRepository()
    access = FakeAccess()
    access.allowed.update({(user_a.id, repo.id), (user_b.id, repo.id)})
    uc = EnsureUserRepositoryWorkspace(
        workspaces,
        repository_repo,
        access,
        FakeSandboxWorkspaceGateway(),
    )

    workspace_a = await uc.execute(current_user=user_a, repository_id=repo.id)
    workspace_b = await uc.execute(current_user=user_b, repository_id=repo.id)

    assert workspace_a.id != workspace_b.id
    assert workspace_a.workspace_path != workspace_b.workspace_path


@pytest.mark.asyncio
async def test_ensure_denies_workspace_when_repository_access_was_revoked(repository_repo) -> None:
    user = User(id=uuid.uuid4(), email="u@test.com", hashed_password="x")
    repo = Repository(
        id=uuid.uuid4(),
        slug="seller",
        name="Seller",
        clone_url="https://github.com/acme/seller.git",
        default_branch="main",
    )
    repository_repo.add(repo)
    uc = EnsureUserRepositoryWorkspace(
        InMemoryUserWorkspaceRepository(),
        repository_repo,
        FakeAccess(),
        FakeSandboxWorkspaceGateway(),
    )

    with pytest.raises(UserWorkspaceAccessDeniedError):
        await uc.execute(current_user=user, repository_id=repo.id)


@pytest.mark.asyncio
async def test_missing_workspace_transitions_through_repairing(repository_repo) -> None:
    user = User(id=uuid.uuid4(), email="u@test.com", hashed_password="x")
    repo = Repository(
        id=uuid.uuid4(),
        slug="seller",
        name="Seller",
        clone_url="https://github.com/acme/seller.git",
        default_branch="main",
    )
    repository_repo.add(repo)
    workspaces = InMemoryUserWorkspaceRepository()
    existing = UserRepositoryWorkspace(
        id=uuid.uuid4(),
        user_id=user.id,
        repository_id=repo.id,
        sandbox_id=None,
        sandbox_key="default",
        base_branch="main",
        workspace_path="/repos/users/u/default/seller/main",
        status="missing",
    )
    await workspaces.save(existing)
    access = FakeAccess()
    access.allowed.add((user.id, repo.id))
    sandbox = FakeSandboxWorkspaceGateway()
    sandbox.next_result = SandboxWorkspaceEnsureResult(
        workspace_path=existing.workspace_path,
        status="ready",
        action="repaired",
        message="repaired",
    )
    uc = EnsureUserRepositoryWorkspace(workspaces, repository_repo, access, sandbox)

    repaired = await uc.execute(current_user=user, repository_id=repo.id)

    assert repaired.id == existing.id
    assert repaired.status == "ready"
    assert repaired.health_message == "repaired"


@pytest.mark.asyncio
async def test_dirty_baseline_is_repaired_without_leaving_dirty_status(repository_repo) -> None:
    user = User(id=uuid.uuid4(), email="u@test.com", hashed_password="x")
    repo = Repository(
        id=uuid.uuid4(),
        slug="seller",
        name="Seller",
        clone_url="https://github.com/acme/seller.git",
        default_branch="main",
    )
    repository_repo.add(repo)
    workspaces = InMemoryUserWorkspaceRepository()
    existing = UserRepositoryWorkspace(
        id=uuid.uuid4(),
        user_id=user.id,
        repository_id=repo.id,
        sandbox_id=None,
        sandbox_key="default",
        base_branch="main",
        workspace_path="/repos/users/u/default/seller/main",
        status="dirty",
    )
    await workspaces.save(existing)
    access = FakeAccess()
    access.allowed.add((user.id, repo.id))
    sandbox = FakeSandboxWorkspaceGateway()
    sandbox.next_result = SandboxWorkspaceEnsureResult(
        workspace_path=existing.workspace_path,
        status="ready",
        action="repaired",
        dirty=False,
        message="dirty baseline repaired",
    )
    uc = EnsureUserRepositoryWorkspace(workspaces, repository_repo, access, sandbox)

    repaired = await uc.execute(current_user=user, repository_id=repo.id)

    assert repaired.status == "ready"
    assert repaired.health_message == "dirty baseline repaired"
