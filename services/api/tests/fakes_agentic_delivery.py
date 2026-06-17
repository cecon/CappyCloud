"""In-memory fake for agentic delivery use case tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.domain.agentic_delivery import (
    AgenticPermissionValue,
    CycleStatus,
    GateType,
    ReviewDecisionValue,
)
from app.ports.agentic_delivery import (
    AgenticDeliveryAuditPort,
    AgenticDeliveryRepository,
    CycleCreate,
    Page,
)


def _now() -> datetime:
    return datetime.now(UTC)


class FakeAgenticDeliveryAudit(AgenticDeliveryAuditPort):
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    async def record(self, event_type: str, payload: dict) -> None:
        self.events.append((event_type, payload))


class FakeAgenticDeliveryRepository(AgenticDeliveryRepository):
    def __init__(self) -> None:
        self.cycles: dict[uuid.UUID, dict] = {}
        self.work_packages: list[dict] = []
        self.gates: list[dict] = []
        self.outputs: list[dict] = []
        self.decisions: list[dict] = []
        self.evidence_links: list[dict] = []
        self.surfaces: dict[uuid.UUID, dict] = {}
        self.knowledge: list[dict] = []
        self.relationships: list[dict] = []
        self.permissions: dict[uuid.UUID, dict] = {}
        self.authorizations: list[dict] = []
        self.metrics: list[dict] = []

    async def create_cycle(self, data: CycleCreate) -> dict:
        cycle = {
            "id": uuid.uuid4(),
            "conversation_id": data.conversation_id,
            "created_by_user_id": data.created_by_user_id,
            "repository_ids": data.repository_ids,
            "domain_key": data.domain_key,
            "title": data.title,
            "business_goal": data.business_goal,
            "scope_boundary": data.scope_boundary,
            "expected_outputs": data.expected_outputs,
            "acceptance_expectations": data.acceptance_expectations,
            "status": CycleStatus.DRAFT.value,
            "created_at": _now(),
            "updated_at": _now(),
        }
        self.cycles[cycle["id"]] = cycle
        for gate in (GateType.PRODUCT, GateType.ARCHITECTURE, GateType.QUALITY):
            self.gates.append(
                {
                    "id": uuid.uuid4(),
                    "cycle_id": cycle["id"],
                    "gate_type": gate.value,
                    "status": "pending",
                    "required": True,
                    "trigger_reason": "required",
                }
            )
        return dict(cycle)

    async def get_cycle(self, cycle_id: uuid.UUID) -> dict | None:
        row = self.cycles.get(cycle_id)
        return dict(row) if row else None

    async def update_cycle_status(
        self,
        cycle_id: uuid.UUID,
        from_status: CycleStatus,
        to_status: CycleStatus,
        changed_by_user_id: uuid.UUID | None,
        reason: str,
    ) -> dict:
        del from_status, changed_by_user_id, reason
        self.cycles[cycle_id]["status"] = to_status.value
        return dict(self.cycles[cycle_id])

    async def create_work_package(
        self,
        cycle_id: uuid.UUID,
        instructions: str,
        constraints: list[str],
        review_criteria: list[str],
        source_summary: dict,
    ) -> dict:
        version = 1 + len([w for w in self.work_packages if w["cycle_id"] == cycle_id])
        row = {
            "id": uuid.uuid4(),
            "cycle_id": cycle_id,
            "version": version,
            "instructions": instructions,
            "constraints": constraints,
            "review_criteria": review_criteria,
            "source_summary": source_summary,
            "created_at": _now(),
        }
        self.work_packages.append(row)
        return dict(row)

    async def latest_work_package(self, cycle_id: uuid.UUID) -> dict | None:
        rows = [w for w in self.work_packages if w["cycle_id"] == cycle_id]
        return dict(rows[-1]) if rows else None

    async def add_evidence_sources(self, cycle_id: uuid.UUID, sources: list[dict]) -> list[dict]:
        return [dict(s, id=uuid.uuid4(), cycle_id=cycle_id, created_at=_now()) for s in sources]

    async def list_gates(self, cycle_id: uuid.UUID) -> list[dict]:
        return [dict(g) for g in self.gates if g["cycle_id"] == cycle_id]

    async def ensure_compliance_gate(self, cycle_id: uuid.UUID, reason: str) -> dict:
        for gate in self.gates:
            if gate["cycle_id"] == cycle_id and gate["gate_type"] == GateType.COMPLIANCE.value:
                return dict(gate)
        gate = {
            "id": uuid.uuid4(),
            "cycle_id": cycle_id,
            "gate_type": GateType.COMPLIANCE.value,
            "status": "pending",
            "required": True,
            "trigger_reason": reason,
        }
        self.gates.append(gate)
        return dict(gate)

    async def record_review_decision(
        self,
        cycle_id: uuid.UUID,
        decided_by_user_id: uuid.UUID,
        decision: ReviewDecisionValue,
        rationale: str,
        agent_output_id: uuid.UUID | None = None,
        review_gate_id: uuid.UUID | None = None,
    ) -> dict:
        row = dict(
            id=uuid.uuid4(),
            cycle_id=cycle_id,
            decided_by_user_id=decided_by_user_id,
            decision=decision,
            rationale=rationale,
            agent_output_id=agent_output_id,
            review_gate_id=review_gate_id,
            created_at=_now(),
        )
        if isinstance(row.get("decision"), ReviewDecisionValue):
            row["decision"] = row["decision"].value
        self.decisions.append(row)
        return dict(row)

    async def decide_gate(
        self,
        gate_id: uuid.UUID,
        decided_by_user_id: uuid.UUID,
        approved: bool,
        rationale: str,
    ) -> dict:
        for gate in self.gates:
            if gate["id"] == gate_id:
                gate.update(
                    status="approved" if approved else "rejected",
                    decided_by_user_id=decided_by_user_id,
                    decision_rationale=rationale,
                )
                return dict(gate)
        raise LookupError("Gate não encontrado.")

    async def list_outputs(self, cycle_id: uuid.UUID, limit: int, cursor: str | None) -> Page:
        return self._page([o for o in self.outputs if o["cycle_id"] == cycle_id], limit, cursor)

    async def list_review_decisions(
        self, cycle_id: uuid.UUID, limit: int, cursor: str | None
    ) -> Page:
        return self._page([d for d in self.decisions if d["cycle_id"] == cycle_id], limit, cursor)

    async def list_output_evidence_links(self, output_ids: list[uuid.UUID]) -> list[dict]:
        return [dict(link) for link in self.evidence_links if link["agent_output_id"] in output_ids]

    async def create_agent_output(self, cycle_id: uuid.UUID, output: dict) -> dict:
        row = dict(output, id=uuid.uuid4(), cycle_id=cycle_id, created_at=_now())
        self.outputs.append(row)
        return dict(row)

    async def create_output_evidence_link(self, output_id: uuid.UUID, link: dict) -> dict:
        row = dict(link, id=uuid.uuid4(), agent_output_id=output_id, created_at=_now())
        self.evidence_links.append(row)
        return dict(row)

    async def list_sensitive_surfaces(
        self,
        repository_id: uuid.UUID | None,
        domain_key: str | None,
        limit: int,
        cursor: str | None,
    ) -> Page:
        rows = [
            s
            for s in self.surfaces.values()
            if s.get("active", True)
            and (not repository_id or s.get("repository_id") in {repository_id, None})
            and (not domain_key or s.get("domain_key") in {domain_key, None})
        ]
        return self._page(rows, limit, cursor)

    async def save_sensitive_surface(self, surface_id: uuid.UUID, body: dict) -> dict:
        self.surfaces[surface_id] = dict(body, id=surface_id, created_at=_now())
        return dict(self.surfaces[surface_id])

    async def search_knowledge(
        self,
        repository_ids: list[uuid.UUID],
        domain_key: str | None,
        query: str,
        limit: int,
        cursor: str | None,
    ) -> Page:
        rows = [
            k
            for k in self.knowledge
            if k["repository_id"] in repository_ids
            and (not domain_key or k.get("domain_key") in {domain_key, None})
            and query.lower() in (k["title"] + " " + k["content"]).lower()
        ]
        return self._page(rows, limit, cursor)

    async def create_knowledge_relationship(self, body: dict) -> dict:
        row = dict(body, id=uuid.uuid4(), created_at=_now())
        self.relationships.append(row)
        return row

    async def upsert_permission(
        self,
        permission_id: uuid.UUID,
        user_id: uuid.UUID,
        granted_by_user_id: uuid.UUID,
        permission: AgenticPermissionValue,
        active: bool,
        repository_id: uuid.UUID | None = None,
        domain_key: str | None = None,
    ) -> dict:
        row = {
            "id": permission_id,
            "user_id": user_id,
            "repository_id": repository_id,
            "domain_key": domain_key,
            "permission": permission.value,
            "granted_by_user_id": granted_by_user_id,
            "active": active,
        }
        self.permissions[permission_id] = row
        return dict(row)

    async def has_permission(
        self,
        user_id: uuid.UUID,
        permission: AgenticPermissionValue,
        repository_id: uuid.UUID | None,
        domain_key: str | None,
    ) -> bool:
        return any(
            p["user_id"] == user_id
            and p["permission"] == permission.value
            and p["active"]
            and (not repository_id or p.get("repository_id") in {repository_id, None})
            and (not domain_key or p.get("domain_key") in {domain_key, None})
            for p in self.permissions.values()
        )

    async def authorize_external_action(self, body: dict) -> dict:
        row = dict(body, id=uuid.uuid4(), execution_status="authorized", authorized_at=_now())
        self.authorizations.append(row)
        return dict(row)

    async def list_metrics(self, cycle_id: uuid.UUID, limit: int, cursor: str | None) -> Page:
        return self._page([m for m in self.metrics if m["cycle_id"] == cycle_id], limit, cursor)

    async def upsert_metric(
        self,
        cycle_id: uuid.UUID,
        name: str,
        value: float | None,
        unit: str,
        source: str,
        text: str | None = None,
    ) -> dict:
        row = dict(
            id=uuid.uuid4(),
            cycle_id=cycle_id,
            metric_name=name,
            metric_value=value,
            metric_text=text,
            metric_unit=unit,
            source=source,
            created_at=_now(),
        )
        self.metrics.append(row)
        return dict(row)

    @staticmethod
    def _page(rows: list[dict], limit: int, cursor: str | None) -> Page:
        start = max(0, int(cursor or "0"))
        end = start + min(max(limit, 1), 200)
        return Page(
            items=[dict(row) for row in rows[start:end]],
            next_cursor=str(end) if end < len(rows) else None,
        )
