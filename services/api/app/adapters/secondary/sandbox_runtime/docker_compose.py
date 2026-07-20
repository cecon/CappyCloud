"""Adapter Docker Compose para o ``SandboxRuntimeGateway``."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import docker
from docker.errors import APIError, DockerException, ImageNotFound, NotFound
from docker.models.containers import Container

from app.adapters.secondary.sandbox_runtime.docker_sidecar import (
    probe_session_server,
    restart_session_server,
    stop_session_server,
)
from app.domain.entities import ContainerStatus, Sandbox
from app.ports.sandbox_runtime import (
    RuntimeFailureError,
    RuntimeProbe,
    SandboxRuntimeGateway,
)

log = logging.getLogger(__name__)

CONTAINER_PREFIX = "cappycloud-sandbox-"

_DOCKER_STATE_TO_STATUS: dict[str, ContainerStatus] = {
    "created": ContainerStatus.STARTING,
    "restarting": ContainerStatus.STARTING,
    "running": ContainerStatus.RUNNING,
    "removing": ContainerStatus.STOPPED,
    "paused": ContainerStatus.STOPPED,
    "exited": ContainerStatus.STOPPED,
    "dead": ContainerStatus.ERROR,
}


class DockerComposeSandboxRuntime(SandboxRuntimeGateway):
    """Implementacao para Docker Desktop / compose local."""

    def __init__(self, client: docker.DockerClient | None = None) -> None:
        self._client = client

    def _docker(self) -> docker.DockerClient:
        if self._client is None:
            self._client = docker.from_env()
        return self._client

    @staticmethod
    def _container_name(sandbox: Sandbox) -> str:
        return f"{CONTAINER_PREFIX}{sandbox.name}"

    @staticmethod
    def _container_name_candidates(sandbox: Sandbox) -> tuple[str, ...]:
        canonical = DockerComposeSandboxRuntime._container_name(sandbox)
        if sandbox.name == canonical:
            return (canonical,)
        return (canonical, sandbox.name)

    def _find_container(self, sandbox: Sandbox) -> Container | None:
        for name in self._container_name_candidates(sandbox):
            try:
                return self._docker().containers.get(name)
            except NotFound:
                continue
            except APIError as exc:
                raise RuntimeFailureError(
                    f"Falha ao consultar Docker: {exc}", sandbox_id=sandbox.id
                ) from exc
            except DockerException as exc:
                raise RuntimeFailureError(
                    f"Docker indisponivel para consultar containers: {exc}",
                    sandbox_id=sandbox.id,
                ) from exc
        return None

    @staticmethod
    def _probe_from_container(container: Container) -> RuntimeProbe:
        state: dict[str, Any] = container.attrs.get("State", {})
        docker_status = state.get("Status", "")
        return RuntimeProbe(
            status=_DOCKER_STATE_TO_STATUS.get(docker_status, ContainerStatus.ERROR),
            runtime_ref=container.id,
            last_error=state.get("Error") or None,
        )

    @staticmethod
    def _unreachable_status_for(sandbox: Sandbox) -> ContainerStatus:
        if sandbox.container_status in {ContainerStatus.STARTING, ContainerStatus.CONFIGURING}:
            return ContainerStatus.STARTING
        return ContainerStatus.ERROR

    async def ensure_service(self, sandbox: Sandbox, *, restart: bool = False) -> RuntimeProbe:
        return await asyncio.to_thread(self._ensure_service_sync, sandbox, restart)

    def _ensure_service_sync(self, sandbox: Sandbox, restart: bool) -> RuntimeProbe:
        docker_error: RuntimeFailureError | None = None
        try:
            existing = self._find_container(sandbox)
        except RuntimeFailureError as exc:
            existing = None
            docker_error = exc

        if existing is not None:
            state_status = existing.attrs.get("State", {}).get("Status", "")
            if state_status == "running" and restart:
                self._restart_existing(existing, sandbox)
            elif state_status != "running":
                self._start_existing(existing, sandbox)
            return self._probe_from_container(existing)

        external = probe_session_server(sandbox)
        if external is not None:
            if restart or external.status is ContainerStatus.STOPPED:
                return restart_session_server(sandbox)
            return external
        if docker_error is not None:
            raise docker_error
        return self._create_container(sandbox)

    @staticmethod
    def _restart_existing(container: Container, sandbox: Sandbox) -> None:
        try:
            container.restart(timeout=10)
        except APIError as exc:
            raise RuntimeFailureError(
                f"Falha ao reiniciar container existente: {exc}",
                sandbox_id=sandbox.id,
            ) from exc
        container.reload()

    @staticmethod
    def _start_existing(container: Container, sandbox: Sandbox) -> None:
        try:
            container.start()
        except APIError as exc:
            raise RuntimeFailureError(
                f"Falha ao iniciar container existente: {exc}",
                sandbox_id=sandbox.id,
            ) from exc
        container.reload()

    def _create_container(self, sandbox: Sandbox) -> RuntimeProbe:
        if not sandbox.image:
            raise RuntimeFailureError(
                "Sandbox sem imagem definida - defina `image` antes de bootar.",
                sandbox_id=sandbox.id,
            )
        ports = {
            f"{sandbox.grpc_port}/tcp": sandbox.grpc_port,
            f"{sandbox.session_port}/tcp": sandbox.session_port,
        }
        try:
            container = self._docker().containers.run(
                image=sandbox.image,
                name=self._container_name(sandbox),
                detach=True,
                environment=dict(sandbox.env_vars),
                ports=ports,
                labels={
                    "cappycloud.role": "sandbox",
                    "cappycloud.sandbox_id": str(sandbox.id),
                    "cappycloud.sandbox_name": sandbox.name,
                },
                restart_policy={"Name": "unless-stopped"},
            )
        except ImageNotFound as exc:
            raise RuntimeFailureError(
                f"Imagem '{sandbox.image}' nao encontrada localmente - "
                "rode docker pull antes ou ajuste a sandbox.",
                sandbox_id=sandbox.id,
            ) from exc
        except APIError as exc:
            raise RuntimeFailureError(
                f"Docker API falhou ao criar container: {exc}", sandbox_id=sandbox.id
            ) from exc

        container.reload()
        log.info("Sandbox %s container criado: %s", sandbox.name, container.id[:12])
        return self._probe_from_container(container)

    async def stop(self, sandbox: Sandbox) -> RuntimeProbe:
        return await asyncio.to_thread(self._stop_sync, sandbox)

    def _stop_sync(self, sandbox: Sandbox) -> RuntimeProbe:
        try:
            existing = self._find_container(sandbox)
        except RuntimeFailureError:
            existing = None
        if existing is None:
            external = probe_session_server(sandbox)
            if external is not None:
                return stop_session_server(sandbox)
            return RuntimeProbe(status=ContainerStatus.NOT_CREATED)
        try:
            existing.stop(timeout=10)
        except APIError as exc:
            raise RuntimeFailureError(
                f"Falha ao parar container: {exc}", sandbox_id=sandbox.id
            ) from exc
        existing.reload()
        return self._probe_from_container(existing)

    async def status(self, sandbox: Sandbox) -> RuntimeProbe:
        return await asyncio.to_thread(self._status_sync, sandbox)

    def _status_sync(self, sandbox: Sandbox) -> RuntimeProbe:
        try:
            existing = self._find_container(sandbox)
        except RuntimeFailureError as exc:
            external = probe_session_server(sandbox)
            if external is not None:
                return external
            raise exc
        if existing is None:
            external = probe_session_server(sandbox)
            if external is not None:
                return external
            return RuntimeProbe(status=ContainerStatus.NOT_CREATED)

        existing.reload()
        probe = self._probe_from_container(existing)
        if probe.status is not ContainerStatus.RUNNING:
            return probe
        external = probe_session_server(sandbox)
        if external is not None:
            return external
        return RuntimeProbe(
            status=self._unreachable_status_for(sandbox),
            runtime_ref=probe.runtime_ref,
            last_error="session server /health indisponivel",
        )

    async def remove(self, sandbox: Sandbox) -> None:
        await asyncio.to_thread(self._remove_sync, sandbox)

    def _remove_sync(self, sandbox: Sandbox) -> None:
        existing = self._find_container(sandbox)
        if existing is None:
            return
        try:
            existing.remove(force=True)
        except APIError as exc:
            raise RuntimeFailureError(
                f"Falha ao remover container: {exc}", sandbox_id=sandbox.id
            ) from exc
