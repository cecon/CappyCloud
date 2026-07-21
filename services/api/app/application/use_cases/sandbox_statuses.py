"""Use cases de saúde operacional de sandboxes."""

from __future__ import annotations

from dataclasses import replace

from app.domain.entities import ContainerStatus, Sandbox, SandboxRuntime
from app.ports.repositories import SandboxRepository
from app.ports.sandbox_runtime import RuntimeFailureError, SandboxRuntimeGateway


class RefreshSandboxStatuses:
    """Consulta o runtime real e persiste o estado observado."""

    def __init__(
        self,
        sandboxes: SandboxRepository,
        runtimes: dict[SandboxRuntime, SandboxRuntimeGateway],
    ) -> None:
        self._sandboxes = sandboxes
        self._runtimes = runtimes

    async def execute(self) -> list[Sandbox]:
        refreshed: list[Sandbox] = []
        for sandbox in await self._sandboxes.list_all():
            refreshed.append(await self._refresh_one(sandbox))
        return refreshed

    async def _refresh_one(self, sandbox: Sandbox) -> Sandbox:
        runtime = self._runtimes.get(sandbox.runtime)
        if runtime is None:
            return await self._update_or_keep(sandbox, ContainerStatus.ERROR)
        try:
            probe = await runtime.status(sandbox)
        except RuntimeFailureError, NotImplementedError:
            return await self._update_or_keep(sandbox, ContainerStatus.ERROR)
        refreshed = await self._update_or_keep(sandbox, probe.status)
        observed = replace(refreshed)
        observed.active_sessions = probe.active_sessions  # type: ignore[attr-defined]
        return observed

    async def _update_or_keep(self, sandbox: Sandbox, status: ContainerStatus) -> Sandbox:
        if sandbox.container_status is status:
            return sandbox
        updated = await self._sandboxes.update_container_status(sandbox.id, status)
        return updated or sandbox
