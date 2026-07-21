"""Adapter test: DockerComposeSandboxRuntime contra mock do Docker SDK (ADR-004)."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import MagicMock

import pytest
from app.adapters.secondary.sandbox_runtime.docker_compose import (
    CONTAINER_PREFIX,
    DockerComposeSandboxRuntime,
)
from app.domain.entities import ContainerStatus, Sandbox, SandboxRuntime
from app.ports.sandbox_runtime import RuntimeFailureError
from docker.errors import APIError, DockerException, ImageNotFound, NotFound


def _sandbox(
    name: str = "alpha", image: str = "cappy/sandbox:latest", env: dict | None = None
) -> Sandbox:
    return Sandbox(
        id=uuid.uuid4(),
        name=name,
        host=name,
        runtime=SandboxRuntime.COMPOSE,
        image=image,
        env_vars=env or {"FOO": "bar"},
    )


def _container_with_state(state: dict[str, Any], cid: str = "abc123") -> MagicMock:
    container = MagicMock()
    container.id = cid
    container.attrs = {"State": state}
    container.reload = MagicMock()
    container.start = MagicMock()
    container.stop = MagicMock()
    container.remove = MagicMock()
    return container


@pytest.fixture
def docker_client() -> MagicMock:
    """Mock do Docker client com `containers.get` e `containers.run`."""
    client = MagicMock()
    client.containers = MagicMock()
    return client


@pytest.fixture
def runtime(docker_client: MagicMock) -> DockerComposeSandboxRuntime:
    return DockerComposeSandboxRuntime(client=docker_client)


class TestEnsureService:
    async def test_creates_when_not_found(
        self, runtime: DockerComposeSandboxRuntime, docker_client: MagicMock
    ) -> None:
        sb = _sandbox(name="alpha")
        docker_client.containers.get.side_effect = NotFound("nope")
        created = _container_with_state({"Status": "running"})
        docker_client.containers.run.return_value = created

        probe = await runtime.ensure_service(sb)

        assert probe.status is ContainerStatus.RUNNING
        # Nome com prefixo padrão:
        kwargs = docker_client.containers.run.call_args.kwargs
        assert kwargs["name"] == f"{CONTAINER_PREFIX}alpha"
        # Variáveis injetadas e portas mapeadas 1:1:
        assert kwargs["environment"] == {"FOO": "bar"}
        assert "50051/tcp" in kwargs["ports"]
        assert "8080/tcp" in kwargs["ports"]
        # Labels marcam que é uma sandbox CappyCloud:
        assert kwargs["labels"]["cappycloud.role"] == "sandbox"
        assert kwargs["labels"]["cappycloud.sandbox_id"] == str(sb.id)

    async def test_starts_when_existing_is_stopped(
        self, runtime: DockerComposeSandboxRuntime, docker_client: MagicMock
    ) -> None:
        sb = _sandbox(name="alpha")
        existing = _container_with_state({"Status": "exited"})
        # reload() depois do start() retorna running:
        existing.attrs = {"State": {"Status": "exited"}}

        def reload_side_effect() -> None:
            existing.attrs = {"State": {"Status": "running"}}

        existing.reload.side_effect = reload_side_effect
        docker_client.containers.get.return_value = existing

        probe = await runtime.ensure_service(sb)

        existing.start.assert_called_once()
        assert probe.status is ContainerStatus.RUNNING
        # Não tentou criar de novo:
        docker_client.containers.run.assert_not_called()

    async def test_noop_when_existing_already_running(
        self, runtime: DockerComposeSandboxRuntime, docker_client: MagicMock
    ) -> None:
        sb = _sandbox(name="alpha")
        existing = _container_with_state({"Status": "running"})
        docker_client.containers.get.return_value = existing

        probe = await runtime.ensure_service(sb)

        existing.start.assert_not_called()
        docker_client.containers.run.assert_not_called()
        assert probe.status is ContainerStatus.RUNNING

    async def test_finds_existing_compose_service_name_without_image(
        self, runtime: DockerComposeSandboxRuntime, docker_client: MagicMock
    ) -> None:
        sb = _sandbox(name="cappycloud-sandbox", image="")
        existing = _container_with_state({"Status": "running"})
        docker_client.containers.get.side_effect = [NotFound("no prefixed"), existing]

        probe = await runtime.ensure_service(sb)

        assert probe.status is ContainerStatus.RUNNING
        assert docker_client.containers.get.call_args_list[0].args[0] == (
            "cappycloud-sandbox-cappycloud-sandbox"
        )
        assert docker_client.containers.get.call_args_list[1].args[0] == "cappycloud-sandbox"
        docker_client.containers.run.assert_not_called()

    async def test_uses_session_server_when_docker_is_unavailable(
        self,
        runtime: DockerComposeSandboxRuntime,
        docker_client: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        class Response:
            status = 200

            def __enter__(self) -> Response:
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def read(self) -> bytes:
                return b'{"status":"ok","openclaude":"running","sessions":3}'

        sb = _sandbox(name="cappycloud-sandbox", image="")
        docker_client.containers.get.side_effect = DockerException("no docker socket")
        monkeypatch.setattr(
            "app.adapters.secondary.sandbox_runtime.docker_sidecar.urllib.request.urlopen",
            lambda *_args, **_kwargs: Response(),
        )

        probe = await runtime.ensure_service(sb)

        assert probe.status is ContainerStatus.RUNNING
        assert probe.runtime_ref == "http://cappycloud-sandbox:8080/health"
        assert probe.active_sessions == 3
        docker_client.containers.run.assert_not_called()

    async def test_raises_runtime_failure_on_image_not_found(
        self, runtime: DockerComposeSandboxRuntime, docker_client: MagicMock
    ) -> None:
        sb = _sandbox(name="alpha")
        docker_client.containers.get.side_effect = NotFound("nope")
        docker_client.containers.run.side_effect = ImageNotFound("missing")

        with pytest.raises(RuntimeFailureError, match="nao encontrada"):
            await runtime.ensure_service(sb)

    async def test_raises_runtime_failure_on_api_error(
        self, runtime: DockerComposeSandboxRuntime, docker_client: MagicMock
    ) -> None:
        sb = _sandbox(name="alpha")
        docker_client.containers.get.side_effect = NotFound("nope")
        docker_client.containers.run.side_effect = APIError("boom")

        with pytest.raises(RuntimeFailureError, match="Docker API"):
            await runtime.ensure_service(sb)

    async def test_raises_when_image_blank(
        self, runtime: DockerComposeSandboxRuntime, docker_client: MagicMock
    ) -> None:
        sb = _sandbox(name="alpha", image="")
        docker_client.containers.get.side_effect = NotFound("nope")

        with pytest.raises(RuntimeFailureError, match="sem imagem"):
            await runtime.ensure_service(sb)


class TestStop:
    async def test_stops_existing(
        self, runtime: DockerComposeSandboxRuntime, docker_client: MagicMock
    ) -> None:
        sb = _sandbox(name="alpha")
        existing = _container_with_state({"Status": "running"})

        def reload_side_effect() -> None:
            existing.attrs = {"State": {"Status": "exited"}}

        existing.reload.side_effect = reload_side_effect
        docker_client.containers.get.return_value = existing

        probe = await runtime.stop(sb)

        existing.stop.assert_called_once()
        assert probe.status is ContainerStatus.STOPPED

    async def test_noop_when_not_found(
        self, runtime: DockerComposeSandboxRuntime, docker_client: MagicMock
    ) -> None:
        sb = _sandbox(name="alpha")
        docker_client.containers.get.side_effect = NotFound("nope")

        probe = await runtime.stop(sb)

        assert probe.status is ContainerStatus.NOT_CREATED


class TestStatus:
    async def test_returns_not_created_when_missing(
        self, runtime: DockerComposeSandboxRuntime, docker_client: MagicMock
    ) -> None:
        sb = _sandbox(name="alpha")
        docker_client.containers.get.side_effect = NotFound("nope")
        probe = await runtime.status(sb)
        assert probe.status is ContainerStatus.NOT_CREATED

    async def test_maps_dead_to_error(
        self, runtime: DockerComposeSandboxRuntime, docker_client: MagicMock
    ) -> None:
        sb = _sandbox(name="alpha")
        existing = _container_with_state({"Status": "dead", "Error": "OOMKilled"})
        docker_client.containers.get.return_value = existing
        probe = await runtime.status(sb)
        assert probe.status is ContainerStatus.ERROR
        assert probe.last_error == "OOMKilled"


class TestRemove:
    async def test_force_removes(
        self, runtime: DockerComposeSandboxRuntime, docker_client: MagicMock
    ) -> None:
        sb = _sandbox(name="alpha")
        existing = _container_with_state({"Status": "exited"})
        docker_client.containers.get.return_value = existing

        await runtime.remove(sb)

        existing.remove.assert_called_once_with(force=True)

    async def test_noop_when_missing(
        self, runtime: DockerComposeSandboxRuntime, docker_client: MagicMock
    ) -> None:
        sb = _sandbox(name="alpha")
        docker_client.containers.get.side_effect = NotFound("nope")
        # Não levanta erro:
        await runtime.remove(sb)
