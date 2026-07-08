from __future__ import annotations

import uuid

import pytest
from app.domain.entities import Repository
from app.ports.sandbox_workspaces import SandboxWorkspaceEnsureResult
from httpx import AsyncClient

from tests.conftest import (
    FakeSandboxWorkspaceGateway,
    InMemoryRepositoryRepository,
    InMemoryUserRepositoryAccessRepository,
    InMemoryUserWorkspaceRepository,
)


@pytest.mark.asyncio
async def test_authenticated_user_can_ensure_and_list_own_workspace(
    client: AsyncClient,
    user_headers: dict[str, str],
    repository_repo: InMemoryRepositoryRepository,
    repository_access_repo: InMemoryUserRepositoryAccessRepository,
    user_workspace_repo: InMemoryUserWorkspaceRepository,
    sandbox_workspace_gateway: FakeSandboxWorkspaceGateway,
) -> None:
    repo = Repository(
        id=uuid.uuid4(),
        slug="seller",
        name="Seller",
        clone_url="https://github.com/acme/seller.git",
        default_branch="main",
    )
    repository_repo.add(repo)
    me = await client.get("/api/auth/me", headers=user_headers)
    user_id = uuid.UUID(me.json()["id"])
    await repository_access_repo.grant(user_id, repo.id)

    response = await client.post(
        "/api/user-workspaces/ensure",
        headers=user_headers,
        json={"repository_id": str(repo.id), "base_branch": "main"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["repository_id"] == str(repo.id)
    assert payload["status"] == "ready"
    assert payload["workspace_path"].startswith(f"/repos/users/{user_id.hex[:12]}/")
    assert len(user_workspace_repo.items) == 1
    assert sandbox_workspace_gateway.ensure_calls[0]["slug"] == "seller"

    listed = await client.get("/api/user-workspaces", headers=user_headers)
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == payload["id"]


@pytest.mark.asyncio
async def test_ensure_denies_repository_without_access(
    client: AsyncClient,
    user_headers: dict[str, str],
    repository_repo: InMemoryRepositoryRepository,
) -> None:
    repo = Repository(
        id=uuid.uuid4(),
        slug="seller",
        name="Seller",
        clone_url="https://github.com/acme/seller.git",
        default_branch="main",
    )
    repository_repo.add(repo)

    response = await client.post(
        "/api/user-workspaces/ensure",
        headers=user_headers,
        json={"repository_id": str(repo.id), "base_branch": "main"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_ensure_repairs_existing_workspace_record(
    client: AsyncClient,
    user_headers: dict[str, str],
    repository_repo: InMemoryRepositoryRepository,
    repository_access_repo: InMemoryUserRepositoryAccessRepository,
    sandbox_workspace_gateway: FakeSandboxWorkspaceGateway,
) -> None:
    repo = Repository(
        id=uuid.uuid4(),
        slug="seller",
        name="Seller",
        clone_url="https://github.com/acme/seller.git",
        default_branch="main",
    )
    repository_repo.add(repo)
    me = await client.get("/api/auth/me", headers=user_headers)
    user_id = uuid.UUID(me.json()["id"])
    await repository_access_repo.grant(user_id, repo.id)

    first = await client.post(
        "/api/user-workspaces/ensure",
        headers=user_headers,
        json={"repository_id": str(repo.id), "base_branch": "main"},
    )
    workspace_path = first.json()["workspace_path"]
    sandbox_workspace_gateway.next_result = SandboxWorkspaceEnsureResult(
        workspace_path=workspace_path,
        status="ready",
        action="repaired",
        message="repaired",
    )

    second = await client.post(
        "/api/user-workspaces/ensure",
        headers=user_headers,
        json={"repository_id": str(repo.id), "base_branch": "main"},
    )

    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["health_message"] == "repaired"
