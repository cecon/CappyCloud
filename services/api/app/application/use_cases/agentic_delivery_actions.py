"""Use cases for external action authorization."""

from __future__ import annotations

import uuid

from app.domain.agentic_delivery import (
    AgenticPermissionValue,
    CycleStatus,
    DeniedExternalActionError,
    GateStatus,
)
from app.ports.agentic_delivery import AgenticDeliveryAuditPort, AgenticDeliveryRepository


class AuthorizeExternalAction:
    def __init__(
        self,
        repo: AgenticDeliveryRepository,
        audit: AgenticDeliveryAuditPort | None = None,
    ) -> None:
        self._repo = repo
        self._audit = audit

    async def execute(self, cycle_id: uuid.UUID, user_id: uuid.UUID, body: dict) -> dict:
        cycle = await self._repo.get_cycle(cycle_id)
        if not cycle:
            raise LookupError("Ciclo não encontrado.")
        if cycle["status"] != CycleStatus.APPROVED.value:
            raise RuntimeError("O ciclo precisa estar Approved.")
        gates = await self._repo.list_gates(cycle_id)
        incomplete = [
            g["gate_type"]
            for g in gates
            if g["required"] and g["status"] != GateStatus.APPROVED.value
        ]
        if incomplete:
            raise RuntimeError("Gates obrigatórios incompletos: " + ", ".join(incomplete))
        has_permission = await self._repo.has_permission(
            user_id,
            AgenticPermissionValue.AUTHORIZE_EXTERNAL_ACTION,
            body.get("repository_id"),
            body.get("domain_key"),
        )
        if not has_permission:
            if self._audit:
                await self._audit.record(
                    "agentic_delivery.external_action_denied",
                    {"cycle_id": str(cycle_id), "user_id": str(user_id)},
                )
            raise DeniedExternalActionError("Permissão para ação externa negada.")
        return await self._repo.authorize_external_action(
            dict(body, cycle_id=cycle_id, authorized_by_user_id=user_id)
        )
