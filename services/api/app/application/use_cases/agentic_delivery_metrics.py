"""Use cases for agentic delivery metrics."""

from __future__ import annotations

import uuid

from app.domain.entities import UserRole
from app.ports.agentic_delivery import AgenticDeliveryRepository
from app.ports.user_access import UserRepositoryAccessRepository


class GetCycleMetrics:
    def __init__(
        self, repo: AgenticDeliveryRepository, access: UserRepositoryAccessRepository
    ) -> None:
        self._repo = repo
        self._access = access

    async def execute(
        self,
        cycle_id: uuid.UUID,
        user_id: uuid.UUID,
        user_role: UserRole,
        limit: int,
        cursor: str | None,
    ) -> dict:
        cycle = await self._repo.get_cycle(cycle_id)
        if not cycle:
            raise LookupError("Ciclo não encontrado.")
        await self._ensure_cycle_access(cycle, user_id, user_role)
        page = await self._repo.list_metrics(cycle_id, limit, cursor)
        return {"cycle_id": cycle_id, "metrics": page.items, "next_cursor": page.next_cursor}

    async def _ensure_cycle_access(
        self, cycle: dict, user_id: uuid.UUID, user_role: UserRole
    ) -> None:
        if user_role is UserRole.ADMIN:
            return
        for repo_id in cycle["repository_ids"]:
            if not await self._access.has_access(user_id, repo_id):
                raise PermissionError("Usuário sem acesso ao ciclo selecionado.")


class PersistCycleMetric:
    def __init__(self, repo: AgenticDeliveryRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        cycle_id: uuid.UUID,
        name: str,
        value: float | None,
        unit: str,
        source: str = "system",
        text: str | None = None,
    ) -> dict:
        return await self._repo.upsert_metric(cycle_id, name, value, unit, source, text)
