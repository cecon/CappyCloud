"""Unit tests for admin_sandboxes CRUD + Clone use cases (ADR-004).

Testes de Boot/Stop vivem em ``test_boot_stop_sandbox.py`` para manter os
arquivos abaixo do limite de 300 linhas.
"""

from __future__ import annotations

import uuid

import pytest
from app.application.use_cases.admin_sandboxes import (
    CloneSandbox,
    CreateSandbox,
    DeleteSandbox,
    GetSandbox,
    ListSandboxes,
    SandboxInUseError,
    SandboxNameTakenError,
    SandboxNotFoundError,
    UpdateSandbox,
)
from app.domain.entities import ContainerStatus, Sandbox, SandboxRuntime

from tests.conftest import InMemorySandboxRepository


@pytest.fixture
def repo() -> InMemorySandboxRepository:
    return InMemorySandboxRepository()


async def _make(repo: InMemorySandboxRepository, name: str = "alpha") -> Sandbox:
    return await CreateSandbox(repo).execute(
        name=name,
        runtime=SandboxRuntime.COMPOSE,
        image="cappycloud/sandbox:latest",
        env_vars={"FOO": "bar"},
    )


class TestCreateSandbox:
    async def test_creates_with_defaults(self, repo: InMemorySandboxRepository) -> None:
        sb = await _make(repo, name="alpha")
        assert sb.name == "alpha"
        assert sb.runtime is SandboxRuntime.COMPOSE
        assert sb.container_status is ContainerStatus.NOT_CREATED
        assert sb.image == "cappycloud/sandbox:latest"
        assert sb.env_vars == {"FOO": "bar"}
        assert sb.host == "alpha"

    async def test_rejects_duplicate_name(self, repo: InMemorySandboxRepository) -> None:
        await _make(repo, name="alpha")
        with pytest.raises(SandboxNameTakenError, match="alpha"):
            await _make(repo, name="alpha")

    async def test_rejects_empty_name(self, repo: InMemorySandboxRepository) -> None:
        with pytest.raises(ValueError, match="obrigatório"):
            await CreateSandbox(repo).execute(
                name="   ",
                runtime=SandboxRuntime.COMPOSE,
                image="x",
            )


class TestListSandboxes:
    async def test_empty(self, repo: InMemorySandboxRepository) -> None:
        assert await ListSandboxes(repo).execute() == []

    async def test_ordered_by_created_at(self, repo: InMemorySandboxRepository) -> None:
        a = await _make(repo, name="alpha")
        b = await _make(repo, name="beta")
        result = await ListSandboxes(repo).execute()
        assert [s.id for s in result] == [a.id, b.id]


class TestGetSandbox:
    async def test_found(self, repo: InMemorySandboxRepository) -> None:
        a = await _make(repo, name="alpha")
        result = await GetSandbox(repo).execute(a.id)
        assert result.id == a.id

    async def test_missing_raises(self, repo: InMemorySandboxRepository) -> None:
        with pytest.raises(SandboxNotFoundError):
            await GetSandbox(repo).execute(uuid.uuid4())


class TestUpdateSandbox:
    async def test_partial_update_preserves_other_fields(
        self, repo: InMemorySandboxRepository
    ) -> None:
        a = await _make(repo, name="alpha")
        updated = await UpdateSandbox(repo).execute(a.id, image="new/img:v2")
        assert updated.image == "new/img:v2"
        # Outros campos preservados:
        assert updated.env_vars == {"FOO": "bar"}
        assert updated.runtime is SandboxRuntime.COMPOSE
        assert updated.name == "alpha"

    async def test_env_vars_replaced_not_merged(self, repo: InMemorySandboxRepository) -> None:
        a = await _make(repo, name="alpha")
        updated = await UpdateSandbox(repo).execute(a.id, env_vars={"NEW": "x"})
        # Replace, não merge — chave antiga sumiu:
        assert updated.env_vars == {"NEW": "x"}

    async def test_missing_raises(self, repo: InMemorySandboxRepository) -> None:
        with pytest.raises(SandboxNotFoundError):
            await UpdateSandbox(repo).execute(uuid.uuid4(), image="x")


class TestDeleteSandbox:
    async def test_deletes_when_not_created(self, repo: InMemorySandboxRepository) -> None:
        a = await _make(repo, name="alpha")
        await DeleteSandbox(repo).execute(a.id)
        assert await repo.get(a.id) is None

    async def test_deletes_when_stopped(self, repo: InMemorySandboxRepository) -> None:
        a = await _make(repo, name="alpha")
        await repo.update_container_status(a.id, ContainerStatus.STOPPED)
        await DeleteSandbox(repo).execute(a.id)
        assert await repo.get(a.id) is None

    @pytest.mark.parametrize(
        "active_status",
        [
            ContainerStatus.STARTING,
            ContainerStatus.RUNNING,
            ContainerStatus.CONFIGURING,
            ContainerStatus.CONFIGURED,
        ],
    )
    async def test_blocks_when_container_active(
        self,
        repo: InMemorySandboxRepository,
        active_status: ContainerStatus,
    ) -> None:
        a = await _make(repo, name="alpha")
        await repo.update_container_status(a.id, active_status)
        with pytest.raises(SandboxInUseError, match="em uso"):
            await DeleteSandbox(repo).execute(a.id)
        # Sandbox preservada:
        assert await repo.get(a.id) is not None

    async def test_missing_raises(self, repo: InMemorySandboxRepository) -> None:
        with pytest.raises(SandboxNotFoundError):
            await DeleteSandbox(repo).execute(uuid.uuid4())


class TestCloneSandbox:
    async def test_clones_config_resets_runtime_state(
        self, repo: InMemorySandboxRepository
    ) -> None:
        a = await _make(repo, name="alpha")
        await repo.update_container_status(a.id, ContainerStatus.RUNNING)

        clone = await CloneSandbox(repo).execute(a.id, "alpha-copy")

        assert clone.name == "alpha-copy"
        assert clone.id != a.id
        # Config copiada:
        assert clone.image == a.image
        assert clone.env_vars == a.env_vars
        assert clone.runtime is a.runtime
        # Runtime state reset:
        assert clone.container_status is ContainerStatus.NOT_CREATED
        assert clone.host == "alpha-copy"
        # Original preservada:
        original = await repo.get(a.id)
        assert original is not None
        assert original.container_status is ContainerStatus.RUNNING

    async def test_rejects_name_collision(self, repo: InMemorySandboxRepository) -> None:
        a = await _make(repo, name="alpha")
        await _make(repo, name="beta")
        with pytest.raises(SandboxNameTakenError):
            await CloneSandbox(repo).execute(a.id, "beta")

    async def test_source_not_found(self, repo: InMemorySandboxRepository) -> None:
        with pytest.raises(SandboxNotFoundError):
            await CloneSandbox(repo).execute(uuid.uuid4(), "new")
