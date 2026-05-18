"""Port para o orquestrador de containers de sandboxes (ADR-004 §8).

A camada de aplicação fala com containers/services SÓ via este contrato.
Implementações concretas:

- ``DockerComposeSandboxRuntime``: usa Docker SDK contra o daemon local
  (Docker Desktop, dev). Cria containers diretamente.
- ``DockerSwarmSandboxRuntime``: stub — em produção, vai criar Swarm
  services. Bloqueado até PR seguinte.

O caller faz operações idempotentes: ``ensure_service`` cria se não existir,
``start`` inicia se parado, ``stop`` para se rodando.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.domain.entities import ContainerStatus, Sandbox


@dataclass
class RuntimeProbe:
    """Resultado de uma consulta de estado ao orquestrador.

    ``status`` é mapeado para o enum canônico do CappyCloud.
    ``runtime_ref`` é o identificador opaco (container_id em Compose,
    service_id em Swarm) — útil para logs/debug.
    """

    status: ContainerStatus
    runtime_ref: str | None = None
    last_error: str | None = None


class SandboxRuntimeGateway(ABC):
    """Contrato que cada adapter de orquestrador implementa.

    Idempotente: chamar ``ensure_service`` em sandbox já criada é no-op.
    """

    @abstractmethod
    async def ensure_service(self, sandbox: Sandbox) -> RuntimeProbe:
        """Garante que o container/service existe e está rodando.

        - Não existe → cria e inicia.
        - Existe parado → inicia.
        - Existe rodando → no-op.

        Levanta :class:`RuntimeFailureError` se a criação/start falhar.
        """

    @abstractmethod
    async def stop(self, sandbox: Sandbox) -> RuntimeProbe:
        """Para o container/service. No-op se já parado/não existe."""

    @abstractmethod
    async def status(self, sandbox: Sandbox) -> RuntimeProbe:
        """Consulta o estado atual no orquestrador (não muda nada)."""

    @abstractmethod
    async def remove(self, sandbox: Sandbox) -> None:
        """Remove o container/service. No-op se não existe."""


class RuntimeFailureError(Exception):
    """O orquestrador falhou ao executar uma operação."""

    def __init__(self, message: str, *, sandbox_id: uuid.UUID | None = None) -> None:
        super().__init__(message)
        self.sandbox_id = sandbox_id
