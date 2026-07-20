"""Unit tests for sandbox runtime status refresh."""

from __future__ import annotations

import pytest
from app.application.use_cases.admin_sandboxes import CreateSandbox
from app.application.use_cases.sandbox_statuses import RefreshSandboxStatuses
from app.domain.entities import ContainerStatus, SandboxRuntime

from tests.conftest import FakeRuntimeGateway, InMemorySandboxRepository


@pytest.fixture
def repo() -> InMemorySandboxRepository:
    return InMemorySandboxRepository()


class TestRefreshSandboxStatuses:
    async def test_refresh_persists_observed_runtime_status(
        self, repo: InMemorySandboxRepository
    ) -> None:
        sandbox = await CreateSandbox(repo).execute(
            name="alpha",
            runtime=SandboxRuntime.COMPOSE,
            image="cappycloud/sandbox:latest",
        )
        await repo.update_container_status(sandbox.id, ContainerStatus.CONFIGURED)

        runtime = FakeRuntimeGateway(ensure_status=ContainerStatus.ERROR)
        result = await RefreshSandboxStatuses(repo, {SandboxRuntime.COMPOSE: runtime}).execute()

        persisted = await repo.get(sandbox.id)
        assert persisted is not None
        assert result[0].container_status is ContainerStatus.ERROR
        assert persisted.container_status is ContainerStatus.ERROR

    async def test_refresh_marks_error_when_runtime_is_missing(
        self, repo: InMemorySandboxRepository
    ) -> None:
        sandbox = await CreateSandbox(repo).execute(
            name="alpha",
            runtime=SandboxRuntime.COMPOSE,
            image="cappycloud/sandbox:latest",
        )

        result = await RefreshSandboxStatuses(repo, {}).execute()

        assert result[0].id == sandbox.id
        assert result[0].container_status is ContainerStatus.ERROR
