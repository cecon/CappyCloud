"""Stub Docker Swarm — ADR-004 §8.

Implementação completa fica para PR de produção. Hoje só sinaliza explicitamente
que a sandbox marcada com ``runtime=swarm`` precisa do adapter real, em vez de
silenciosamente cair no Compose.
"""

from __future__ import annotations

from app.domain.entities import Sandbox
from app.ports.sandbox_runtime import (
    RuntimeProbe,
    SandboxRuntimeGateway,
)


class DockerSwarmSandboxRuntime(SandboxRuntimeGateway):
    """Adapter Swarm — stub. Levanta erro até a implementação real entrar."""

    async def ensure_service(self, sandbox: Sandbox, *, restart: bool = False) -> RuntimeProbe:
        raise NotImplementedError(
            "Adapter Swarm ainda não implementado (ADR-004). Use runtime='compose' "
            "para dev ou aguarde o PR de produção."
        )

    async def stop(self, sandbox: Sandbox) -> RuntimeProbe:
        raise NotImplementedError("Adapter Swarm ainda não implementado.")

    async def status(self, sandbox: Sandbox) -> RuntimeProbe:
        raise NotImplementedError("Adapter Swarm ainda não implementado.")

    async def remove(self, sandbox: Sandbox) -> None:
        raise NotImplementedError("Adapter Swarm ainda não implementado.")
