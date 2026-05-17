"""Use cases administrativos de gestão de sandboxes (ADR-004).

Camada de aplicação pura — sem FastAPI nem SQLAlchemy. Reforça invariantes:

- Nome único (rejeita duplicata explicitamente, não delega à constraint do DB).
- Não permite apagar uma sandbox em uso pelo orquestrador
  (``container_status`` ≠ ``not_created``/``stopped``/``error``) — força
  pelo menos um Stop antes do Delete.
- Clone copia *config* (image, env_vars, runtime); o container_status do
  clone começa sempre em ``not_created`` (ADR-004 §7).
"""

from __future__ import annotations

import uuid

from app.domain.entities import (
    ContainerStatus,
    Sandbox,
    SandboxRuntime,
)
from app.ports.repositories import SandboxRepository
from app.ports.sandbox_runtime import (
    RuntimeFailureError,
    SandboxRuntimeGateway,
)


class SandboxNotFoundError(Exception):
    """O id solicitado não existe na tabela ``sandboxes``."""


class SandboxNameTakenError(Exception):
    """Já existe sandbox com este nome."""


class SandboxInUseError(Exception):
    """Operação destrutiva bloqueada: container ainda existe no orquestrador."""


_NAME_INVARIANT_ACTIVE_STATUSES = frozenset(
    {
        ContainerStatus.STARTING,
        ContainerStatus.RUNNING,
        ContainerStatus.CONFIGURING,
        ContainerStatus.CONFIGURED,
    }
)


class ListSandboxes:
    def __init__(self, sandboxes: SandboxRepository) -> None:
        self._sandboxes = sandboxes

    async def execute(self) -> list[Sandbox]:
        return await self._sandboxes.list_all()


class GetSandbox:
    def __init__(self, sandboxes: SandboxRepository) -> None:
        self._sandboxes = sandboxes

    async def execute(self, sandbox_id: uuid.UUID) -> Sandbox:
        sb = await self._sandboxes.get(sandbox_id)
        if sb is None:
            raise SandboxNotFoundError(f"Sandbox {sandbox_id} não encontrada.")
        return sb


class CreateSandbox:
    """Cria uma sandbox no DB. Não cria container — isso é responsabilidade
    do ``BootSandbox`` use case + ``SandboxRuntimeGateway``."""

    def __init__(self, sandboxes: SandboxRepository) -> None:
        self._sandboxes = sandboxes

    async def execute(
        self,
        *,
        name: str,
        runtime: SandboxRuntime,
        image: str,
        env_vars: dict[str, str] | None = None,
        host: str | None = None,
        grpc_port: int = 50051,
        session_port: int = 8080,
    ) -> Sandbox:
        normalised = name.strip()
        if not normalised:
            raise ValueError("Nome da sandbox é obrigatório.")
        if await self._sandboxes.get_by_name(normalised):
            raise SandboxNameTakenError(f"Já existe sandbox com nome '{normalised}'.")

        sandbox = Sandbox(
            id=uuid.uuid4(),
            name=normalised,
            host=host or normalised,
            grpc_port=grpc_port,
            session_port=session_port,
            status="active",
            runtime=runtime,
            image=image.strip(),
            env_vars=dict(env_vars or {}),
            container_status=ContainerStatus.NOT_CREATED,
        )
        return await self._sandboxes.save(sandbox)


class UpdateSandbox:
    """Atualiza campos editáveis (image, env_vars, host, ports, status lógico).

    Não permite alterar o ``container_status`` por aqui — essa transição é do
    ``BootSandbox``/``StopSandbox``. Nome também é imutável depois de criado
    (evita drift com o nome do service no orquestrador).
    """

    def __init__(self, sandboxes: SandboxRepository) -> None:
        self._sandboxes = sandboxes

    async def execute(
        self,
        sandbox_id: uuid.UUID,
        *,
        image: str | None = None,
        env_vars: dict[str, str] | None = None,
        host: str | None = None,
        grpc_port: int | None = None,
        session_port: int | None = None,
        status: str | None = None,
    ) -> Sandbox:
        current = await self._sandboxes.get(sandbox_id)
        if current is None:
            raise SandboxNotFoundError(f"Sandbox {sandbox_id} não encontrada.")

        from dataclasses import replace

        updated = replace(
            current,
            image=image.strip() if image is not None else current.image,
            env_vars=dict(env_vars) if env_vars is not None else current.env_vars,
            host=host if host is not None else current.host,
            grpc_port=grpc_port if grpc_port is not None else current.grpc_port,
            session_port=session_port if session_port is not None else current.session_port,
            status=status if status is not None else current.status,
        )
        return await self._sandboxes.update(updated)


class DeleteSandbox:
    """Remove a sandbox do cadastro.

    Bloqueia se o container ainda existe no orquestrador (``container_status``
    em estado "ativo"). O caller deve parar/remover o container antes via
    ``StopSandbox`` / runtime gateway.
    """

    def __init__(self, sandboxes: SandboxRepository) -> None:
        self._sandboxes = sandboxes

    async def execute(self, sandbox_id: uuid.UUID) -> None:
        current = await self._sandboxes.get(sandbox_id)
        if current is None:
            raise SandboxNotFoundError(f"Sandbox {sandbox_id} não encontrada.")
        if current.container_status in _NAME_INVARIANT_ACTIVE_STATUSES:
            raise SandboxInUseError(
                f"Sandbox '{current.name}' está em uso (container_status="
                f"{current.container_status.value}). Pare o container antes."
            )
        await self._sandboxes.delete(sandbox_id)


class BootSandbox:
    """Cria/inicia o container da sandbox no orquestrador.

    Transições típicas:

    - ``not_created``/``stopped``/``error`` → ``starting`` → (probe) → ``running``
      → (bootstrap noop) → ``configured``.

    Idempotente: chamar em sandbox já configurada apenas revalida o probe.

    O bootstrap de periféricos (MCPs/skills/agents) é placeholder até PR4-5
    (ADR-004 §5). Por agora, ``running`` → ``configured`` é transição direta.
    """

    def __init__(
        self,
        sandboxes: SandboxRepository,
        runtimes: dict[SandboxRuntime, SandboxRuntimeGateway],
    ) -> None:
        self._sandboxes = sandboxes
        self._runtimes = runtimes

    async def execute(self, sandbox_id: uuid.UUID) -> Sandbox:
        sandbox = await self._sandboxes.get(sandbox_id)
        if sandbox is None:
            raise SandboxNotFoundError(f"Sandbox {sandbox_id} não encontrada.")

        runtime = self._runtimes.get(sandbox.runtime)
        if runtime is None:
            raise RuntimeFailureError(
                f"Runtime '{sandbox.runtime.value}' não está configurado nesta instância.",
                sandbox_id=sandbox.id,
            )

        await self._sandboxes.update_container_status(sandbox.id, ContainerStatus.STARTING)
        try:
            probe = await runtime.ensure_service(sandbox)
        except RuntimeFailureError:
            await self._sandboxes.update_container_status(sandbox.id, ContainerStatus.ERROR)
            raise

        if probe.status is ContainerStatus.RUNNING:
            # Bootstrap placeholder (PR4-5 vai materializar MCPs/skills/agents).
            await self._sandboxes.update_container_status(sandbox.id, ContainerStatus.CONFIGURING)
            final = await self._sandboxes.update_container_status(
                sandbox.id, ContainerStatus.CONFIGURED
            )
            if final is None:
                raise SandboxNotFoundError(f"Sandbox {sandbox.id} sumiu durante boot.")
            return final

        final = await self._sandboxes.update_container_status(sandbox.id, probe.status)
        if final is None:
            raise SandboxNotFoundError(f"Sandbox {sandbox.id} sumiu durante boot.")
        return final


class StopSandbox:
    """Para o container da sandbox no orquestrador.

    Transições: qualquer → ``stopped`` (ou ``not_created`` se já não existia).
    """

    def __init__(
        self,
        sandboxes: SandboxRepository,
        runtimes: dict[SandboxRuntime, SandboxRuntimeGateway],
    ) -> None:
        self._sandboxes = sandboxes
        self._runtimes = runtimes

    async def execute(self, sandbox_id: uuid.UUID) -> Sandbox:
        sandbox = await self._sandboxes.get(sandbox_id)
        if sandbox is None:
            raise SandboxNotFoundError(f"Sandbox {sandbox_id} não encontrada.")

        runtime = self._runtimes.get(sandbox.runtime)
        if runtime is None:
            raise RuntimeFailureError(
                f"Runtime '{sandbox.runtime.value}' não está configurado nesta instância.",
                sandbox_id=sandbox.id,
            )

        try:
            probe = await runtime.stop(sandbox)
        except RuntimeFailureError:
            await self._sandboxes.update_container_status(sandbox.id, ContainerStatus.ERROR)
            raise

        final = await self._sandboxes.update_container_status(sandbox.id, probe.status)
        if final is None:
            raise SandboxNotFoundError(f"Sandbox {sandbox.id} sumiu durante stop.")
        return final


class CloneSandbox:
    """Clona uma sandbox existente (ADR-004 §7).

    Copia: ``image``, ``env_vars``, ``runtime``, ``grpc_port``, ``session_port``.
    Reset: ``container_status`` para ``NOT_CREATED``; ``host`` para o ``new_name``;
    ``status`` lógico para ``active``.

    Em PR4/PR5, este use case será estendido para também duplicar entradas
    de ``SandboxMcp``/``SandboxSkill``/``SandboxAgent``.
    """

    def __init__(self, sandboxes: SandboxRepository) -> None:
        self._sandboxes = sandboxes

    async def execute(self, source_id: uuid.UUID, new_name: str) -> Sandbox:
        source = await self._sandboxes.get(source_id)
        if source is None:
            raise SandboxNotFoundError(f"Sandbox {source_id} não encontrada.")
        normalised = new_name.strip()
        if not normalised:
            raise ValueError("Nome do clone é obrigatório.")
        if await self._sandboxes.get_by_name(normalised):
            raise SandboxNameTakenError(f"Já existe sandbox com nome '{normalised}'.")

        clone = Sandbox(
            id=uuid.uuid4(),
            name=normalised,
            host=normalised,
            grpc_port=source.grpc_port,
            session_port=source.session_port,
            status="active",
            runtime=source.runtime,
            image=source.image,
            env_vars=dict(source.env_vars),
            container_status=ContainerStatus.NOT_CREATED,
        )
        return await self._sandboxes.save(clone)
