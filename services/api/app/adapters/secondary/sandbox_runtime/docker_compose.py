"""Adapter Docker Compose para o ``SandboxRuntimeGateway`` (ADR-004 §8).

Usa o Docker SDK contra o daemon local. Pensado para dev (Docker Desktop) —
em produção (Swarm), use :class:`DockerSwarmSandboxRuntime`.

Pontos importantes:

- Container nomeado com prefixo ``cappycloud-sandbox-<name>`` para evitar
  colisão com outros containers (e tornar o lookup por nome confiável).
- Procura por nome via filtro do Docker, não por id — assim a operação é
  idempotente mesmo após restart da API.
- ``ensure_service`` é síncrono internamente (Docker SDK em Python é blocking).
  Envolvido em ``asyncio.to_thread`` para não bloquear o event loop.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any

import docker
from docker.errors import APIError, DockerException, ImageNotFound, NotFound
from docker.models.containers import Container

from app.domain.entities import ContainerStatus, Sandbox
from app.ports.sandbox_runtime import (
    RuntimeFailureError,
    RuntimeProbe,
    SandboxRuntimeGateway,
)

log = logging.getLogger(__name__)

CONTAINER_PREFIX = "cappycloud-sandbox-"

# Mapeia o ``State.Status`` do Docker para o enum canônico do CappyCloud.
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
    """Implementação para Docker Desktop / compose local."""

    def __init__(self, client: docker.DockerClient | None = None) -> None:
        # ``client`` é injetável para testes (mock); em prod usa env do daemon.
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
        """Canonical managed name plus legacy/external Compose service name."""
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
                    f"Docker indisponível para consultar containers: {exc}",
                    sandbox_id=sandbox.id,
                ) from exc
        return None

    @staticmethod
    def _probe_from_container(container: Container) -> RuntimeProbe:
        state: dict[str, Any] = container.attrs.get("State", {})
        docker_status = state.get("Status", "")
        last_error = state.get("Error") or None
        return RuntimeProbe(
            status=_DOCKER_STATE_TO_STATUS.get(docker_status, ContainerStatus.ERROR),
            runtime_ref=container.id,
            last_error=last_error,
        )

    @staticmethod
    def _online_status_for(sandbox: Sandbox) -> ContainerStatus:
        if sandbox.container_status is ContainerStatus.CONFIGURED:
            return ContainerStatus.CONFIGURED
        return ContainerStatus.RUNNING

    @staticmethod
    def _unreachable_status_for(sandbox: Sandbox) -> ContainerStatus:
        if sandbox.container_status in {ContainerStatus.STARTING, ContainerStatus.CONFIGURING}:
            return ContainerStatus.STARTING
        return ContainerStatus.ERROR

    @staticmethod
    def _probe_session_server(sandbox: Sandbox) -> RuntimeProbe | None:
        url = f"http://{sandbox.host}:{sandbox.session_port}/health"
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if 200 <= response.status < 300:
                    data = json.loads(response.read().decode("utf-8") or "{}")
                    if data.get("openclaude") == "stopped":
                        return RuntimeProbe(status=ContainerStatus.STOPPED, runtime_ref=url)
                    return RuntimeProbe(
                        status=DockerComposeSandboxRuntime._online_status_for(sandbox),
                        runtime_ref=url,
                    )
        except OSError:
            return None
        except urllib.error.URLError:
            return None
        except TimeoutError:
            return None
        return None

    @staticmethod
    def _post_runtime_control(sandbox: Sandbox, action: str) -> None:
        url = f"http://{sandbox.host}:{sandbox.session_port}/runtime/{action}"
        request = urllib.request.Request(url, data=b"{}", method="POST")
        request.add_header("Content-Type", "application/json")
        try:
            urllib.request.urlopen(request, timeout=5).close()
        except OSError as exc:
            raise RuntimeFailureError(
                f"Falha ao controlar OpenClaude via sidecar: {exc}",
                sandbox_id=sandbox.id,
            ) from exc

    @staticmethod
    def _restart_session_server(sandbox: Sandbox) -> RuntimeProbe:
        DockerComposeSandboxRuntime._post_runtime_control(sandbox, "restart-openclaude")
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            time.sleep(1)
            probe = DockerComposeSandboxRuntime._probe_session_server(sandbox)
            if probe is not None:
                return probe
        return RuntimeProbe(
            status=ContainerStatus.STARTING,
            runtime_ref=f"http://{sandbox.host}:{sandbox.session_port}/runtime/restart-openclaude",
            last_error="OpenClaude reiniciando; /health ainda indisponível",
        )

    @staticmethod
    def _stop_session_server(sandbox: Sandbox) -> RuntimeProbe:
        DockerComposeSandboxRuntime._post_runtime_control(sandbox, "stop-openclaude")
        return RuntimeProbe(
            status=ContainerStatus.STOPPED,
            runtime_ref=f"http://{sandbox.host}:{sandbox.session_port}/runtime/stop-openclaude",
        )

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
            # Lê estado inicial diretamente de ``attrs`` (já vem populado por
            # ``containers.get``); só recarregamos depois de uma ação (start).
            state_status = existing.attrs.get("State", {}).get("Status", "")
            if state_status == "running" and restart:
                try:
                    existing.restart(timeout=10)
                except APIError as exc:
                    raise RuntimeFailureError(
                        f"Falha ao reiniciar container existente: {exc}",
                        sandbox_id=sandbox.id,
                    ) from exc
                existing.reload()
            elif state_status != "running":
                try:
                    existing.start()
                except APIError as exc:
                    raise RuntimeFailureError(
                        f"Falha ao iniciar container existente: {exc}",
                        sandbox_id=sandbox.id,
                    ) from exc
                existing.reload()
            return self._probe_from_container(existing)

        external = self._probe_session_server(sandbox)
        if external is not None:
            if restart or external.status is ContainerStatus.STOPPED:
                return self._restart_session_server(sandbox)
            return external

        if docker_error is not None:
            raise docker_error

        if not sandbox.image:
            raise RuntimeFailureError(
                "Sandbox sem imagem definida — defina ``image`` antes de bootar.",
                sandbox_id=sandbox.id,
            )

        name = self._container_name(sandbox)
        ports = {
            f"{sandbox.grpc_port}/tcp": sandbox.grpc_port,
            f"{sandbox.session_port}/tcp": sandbox.session_port,
        }
        try:
            container = self._docker().containers.run(
                image=sandbox.image,
                name=name,
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
                f"Imagem '{sandbox.image}' não encontrada localmente — "
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
            external = self._probe_session_server(sandbox)
            if external is not None:
                return self._stop_session_server(sandbox)
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
            external = self._probe_session_server(sandbox)
            if external is not None:
                return external
            raise exc
        if existing is None:
            external = self._probe_session_server(sandbox)
            if external is not None:
                return external
            return RuntimeProbe(status=ContainerStatus.NOT_CREATED)
        existing.reload()
        probe = self._probe_from_container(existing)
        if probe.status is not ContainerStatus.RUNNING:
            return probe
        external = self._probe_session_server(sandbox)
        if external is not None:
            return external
        return RuntimeProbe(
            status=self._unreachable_status_for(sandbox),
            runtime_ref=probe.runtime_ref,
            last_error="session server /health indisponível",
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
