"""SQLAlchemy implementation of SandboxRepository port (ADR-004)."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import (
    ContainerStatus,
    SandboxRuntime,
)
from app.domain.entities import (
    Sandbox as SandboxEntity,
)
from app.infrastructure.orm_models import Sandbox as SandboxORM
from app.ports.repositories import SandboxRepository


class SQLAlchemySandboxRepository(SandboxRepository):
    """Concrete SandboxRepository backed by PostgreSQL via SQLAlchemy async."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self) -> list[SandboxEntity]:
        result = await self._session.execute(
            select(SandboxORM).order_by(SandboxORM.created_at.asc())
        )
        return [self._to_entity(row) for row in result.scalars().all()]

    async def get(self, sandbox_id: uuid.UUID) -> SandboxEntity | None:
        row = await self._session.get(SandboxORM, sandbox_id)
        return self._to_entity(row) if row else None

    async def get_by_name(self, name: str) -> SandboxEntity | None:
        result = await self._session.execute(select(SandboxORM).where(SandboxORM.name == name))
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def save(self, sandbox: SandboxEntity) -> SandboxEntity:
        orm = SandboxORM(
            id=sandbox.id,
            name=sandbox.name,
            host=sandbox.host,
            grpc_port=sandbox.grpc_port,
            session_port=sandbox.session_port,
            status=sandbox.status,
            runtime=sandbox.runtime.value,
            image=sandbox.image,
            env_vars=dict(sandbox.env_vars),
            container_status=sandbox.container_status.value,
            register_token=sandbox.register_token,
        )
        self._session.add(orm)
        await self._session.commit()
        await self._session.refresh(orm)
        return self._to_entity(orm)

    async def update(self, sandbox: SandboxEntity) -> SandboxEntity:
        row = await self._session.get(SandboxORM, sandbox.id)
        if row is None:
            # update() não cria — para inserir, use save().
            raise LookupError(f"Sandbox {sandbox.id} não encontrada.")
        row.name = sandbox.name
        row.host = sandbox.host
        row.grpc_port = sandbox.grpc_port
        row.session_port = sandbox.session_port
        row.status = sandbox.status
        row.runtime = sandbox.runtime.value
        row.image = sandbox.image
        row.env_vars = dict(sandbox.env_vars)
        row.container_status = sandbox.container_status.value
        row.register_token = sandbox.register_token
        await self._session.commit()
        await self._session.refresh(row)
        return self._to_entity(row)

    async def update_container_status(
        self, sandbox_id: uuid.UUID, status: ContainerStatus
    ) -> SandboxEntity | None:
        row = await self._session.get(SandboxORM, sandbox_id)
        if row is None:
            return None
        row.container_status = status.value
        await self._session.commit()
        await self._session.refresh(row)
        return self._to_entity(row)

    async def delete(self, sandbox_id: uuid.UUID) -> bool:
        result: CursorResult = await self._session.execute(  # type: ignore[assignment]
            delete(SandboxORM).where(SandboxORM.id == sandbox_id)
        )
        await self._session.commit()
        return result.rowcount > 0

    @staticmethod
    def _to_entity(row: SandboxORM) -> SandboxEntity:
        return SandboxEntity(
            id=row.id,
            name=row.name,
            host=row.host,
            grpc_port=row.grpc_port,
            session_port=row.session_port,
            status=row.status,
            runtime=_runtime_from_str(row.runtime),
            image=row.image or "",
            env_vars=dict(row.env_vars or {}),
            container_status=_container_status_from_str(row.container_status),
            register_token=row.register_token,
            created_at=row.created_at,
        )


def _runtime_from_str(value: str | None) -> SandboxRuntime:
    """Mapeia o texto persistido para o enum, com fallback defensivo."""
    if value is None:
        return SandboxRuntime.COMPOSE
    try:
        return SandboxRuntime(value)
    except ValueError:
        return SandboxRuntime.COMPOSE


def _container_status_from_str(value: str | None) -> ContainerStatus:
    """Mapeia o texto persistido para o enum, com fallback para NOT_CREATED."""
    if value is None:
        return ContainerStatus.NOT_CREATED
    try:
        return ContainerStatus(value)
    except ValueError:
        return ContainerStatus.NOT_CREATED
