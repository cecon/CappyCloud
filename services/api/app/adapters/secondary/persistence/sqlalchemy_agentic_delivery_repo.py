"""SQLAlchemy adapter for agentic delivery persistence."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.secondary.persistence._agentic_delivery_repo_extra import (
    AgenticDeliveryRepositoryExtraMixin,
)
from app.domain.agentic_delivery import (
    CycleStatus,
    GateStatus,
    GateType,
    ReviewDecisionValue,
    required_initial_gates,
)
from app.infrastructure import orm_models_agentic_delivery as orm
from app.ports.agentic_delivery import AgenticDeliveryRepository, CycleCreate, Page


def _offset(cursor: str | None) -> int:
    try:
        return max(0, int(cursor or "0"))
    except ValueError:
        return 0


def _next(offset: int, limit: int, count: int) -> str | None:
    return str(offset + limit) if count == limit else None


class SQLAlchemyAgenticDeliveryRepository(
    AgenticDeliveryRepositoryExtraMixin, AgenticDeliveryRepository
):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_cycle(self, data: CycleCreate) -> dict:
        row = orm.AgenticDeliveryCycle(
            id=uuid.uuid4(),
            conversation_id=data.conversation_id,
            created_by_user_id=data.created_by_user_id,
            repository_ids=[str(r) for r in data.repository_ids],
            domain_key=data.domain_key,
            title=data.title,
            business_goal=data.business_goal,
            scope_boundary=data.scope_boundary,
            expected_outputs=data.expected_outputs,
            acceptance_expectations=data.acceptance_expectations,
        )
        self._session.add(row)
        await self._session.flush()
        for gate in required_initial_gates():
            self._session.add(
                orm.ReviewGate(
                    id=uuid.uuid4(),
                    cycle_id=row.id,
                    gate_type=gate.value,
                    required=True,
                    trigger_reason="required",
                )
            )
        await self._session.commit()
        await self._session.refresh(row)
        return self._cycle(row)

    async def get_cycle(self, cycle_id: uuid.UUID) -> dict | None:
        row = await self._session.get(orm.AgenticDeliveryCycle, cycle_id)
        return self._cycle(row) if row else None

    async def update_cycle_status(
        self,
        cycle_id: uuid.UUID,
        from_status: CycleStatus,
        to_status: CycleStatus,
        changed_by_user_id: uuid.UUID | None,
        reason: str,
    ) -> dict:
        row = await self._session.get(orm.AgenticDeliveryCycle, cycle_id)
        if row is None:
            raise LookupError("Ciclo não encontrado.")
        row.status = to_status.value
        self._session.add(
            orm.LifecycleTransition(
                id=uuid.uuid4(),
                cycle_id=cycle_id,
                from_status=from_status.value,
                to_status=to_status.value,
                changed_by_user_id=changed_by_user_id,
                reason=reason,
            )
        )
        await self._session.commit()
        await self._session.refresh(row)
        return self._cycle(row)

    async def create_work_package(
        self,
        cycle_id: uuid.UUID,
        instructions: str,
        constraints: list[str],
        review_criteria: list[str],
        source_summary: dict,
    ) -> dict:
        version = await self._next_work_package_version(cycle_id)
        row = orm.StructuredWorkPackage(
            id=uuid.uuid4(),
            cycle_id=cycle_id,
            version=version,
            instructions=instructions,
            constraints=constraints,
            review_criteria=review_criteria,
            source_summary=source_summary,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return self._work_package(row)

    async def latest_work_package(self, cycle_id: uuid.UUID) -> dict | None:
        result = await self._session.execute(
            select(orm.StructuredWorkPackage)
            .where(orm.StructuredWorkPackage.cycle_id == cycle_id)
            .order_by(orm.StructuredWorkPackage.version.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return self._work_package(row) if row else None

    async def add_evidence_sources(self, cycle_id: uuid.UUID, sources: list[dict]) -> list[dict]:
        rows: list[orm.EvidenceSource] = []
        for item in sources:
            row = orm.EvidenceSource(id=uuid.uuid4(), cycle_id=cycle_id, **item)
            self._session.add(row)
            rows.append(row)
        await self._session.commit()
        return [self._row(r) for r in rows]

    async def list_gates(self, cycle_id: uuid.UUID) -> list[dict]:
        result = await self._session.execute(
            select(orm.ReviewGate).where(orm.ReviewGate.cycle_id == cycle_id)
        )
        return [self._row(row) for row in result.scalars()]

    async def ensure_compliance_gate(self, cycle_id: uuid.UUID, reason: str) -> dict:
        result = await self._session.execute(
            select(orm.ReviewGate).where(
                orm.ReviewGate.cycle_id == cycle_id,
                orm.ReviewGate.gate_type == GateType.COMPLIANCE.value,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = orm.ReviewGate(
                id=uuid.uuid4(),
                cycle_id=cycle_id,
                gate_type=GateType.COMPLIANCE.value,
                trigger_reason=reason,
                required=True,
            )
            self._session.add(row)
            await self._session.commit()
            await self._session.refresh(row)
        return self._row(row)

    async def record_review_decision(
        self,
        cycle_id: uuid.UUID,
        decided_by_user_id: uuid.UUID,
        decision: ReviewDecisionValue,
        rationale: str,
        agent_output_id: uuid.UUID | None = None,
        review_gate_id: uuid.UUID | None = None,
    ) -> dict:
        row = orm.ReviewDecision(
            id=uuid.uuid4(),
            cycle_id=cycle_id,
            agent_output_id=agent_output_id,
            review_gate_id=review_gate_id,
            decision=decision.value,
            rationale=rationale,
            decided_by_user_id=decided_by_user_id,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return self._row(row)

    async def decide_gate(
        self,
        gate_id: uuid.UUID,
        decided_by_user_id: uuid.UUID,
        approved: bool,
        rationale: str,
    ) -> dict:
        row = await self._session.get(orm.ReviewGate, gate_id)
        if row is None:
            raise LookupError("Gate não encontrado.")
        row.status = GateStatus.APPROVED.value if approved else GateStatus.REJECTED.value
        row.decided_by_user_id = decided_by_user_id
        row.decision_rationale = rationale
        await self._session.commit()
        await self._session.refresh(row)
        return self._row(row)

    async def list_outputs(self, cycle_id: uuid.UUID, limit: int, cursor: str | None) -> Page:
        return await self._page(
            select(orm.AgentOutput)
            .where(orm.AgentOutput.cycle_id == cycle_id)
            .order_by(orm.AgentOutput.created_at, orm.AgentOutput.id),
            limit,
            cursor,
        )

    async def list_review_decisions(
        self, cycle_id: uuid.UUID, limit: int, cursor: str | None
    ) -> Page:
        return await self._page(
            select(orm.ReviewDecision)
            .where(orm.ReviewDecision.cycle_id == cycle_id)
            .order_by(orm.ReviewDecision.created_at, orm.ReviewDecision.id),
            limit,
            cursor,
        )

    async def list_output_evidence_links(self, output_ids: list[uuid.UUID]) -> list[dict]:
        if not output_ids:
            return []
        result = await self._session.execute(
            select(orm.AgentOutputEvidenceLink).where(
                orm.AgentOutputEvidenceLink.agent_output_id.in_(output_ids)
            )
        )
        return [self._row(row) for row in result.scalars()]

    async def create_agent_output(self, cycle_id: uuid.UUID, output: dict) -> dict:
        row = orm.AgentOutput(id=uuid.uuid4(), cycle_id=cycle_id, **output)
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return self._row(row)

    async def create_output_evidence_link(self, output_id: uuid.UUID, link: dict) -> dict:
        row = orm.AgentOutputEvidenceLink(id=uuid.uuid4(), agent_output_id=output_id, **link)
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return self._row(row)

    async def _next_work_package_version(self, cycle_id: uuid.UUID) -> int:
        latest = await self.latest_work_package(cycle_id)
        return int(latest["version"]) + 1 if latest else 1

    async def _page(self, stmt, limit: int, cursor: str | None) -> Page:
        clean_limit = min(max(limit, 1), 200)
        start = _offset(cursor)
        result = await self._session.execute(stmt.offset(start).limit(clean_limit))
        items = [self._row(row) for row in result.scalars()]
        return Page(items=items, next_cursor=_next(start, clean_limit, len(items)))

    @staticmethod
    def _cycle(row: orm.AgenticDeliveryCycle) -> dict:
        data = SQLAlchemyAgenticDeliveryRepository._row(row)
        data["repository_ids"] = [uuid.UUID(str(r)) for r in row.repository_ids]
        return data

    @staticmethod
    def _work_package(row: orm.StructuredWorkPackage) -> dict:
        return SQLAlchemyAgenticDeliveryRepository._row(row)

    @staticmethod
    def _row(row: Any) -> dict:
        out: dict[str, Any] = {}
        for column in row.__table__.columns:
            out[column.name] = getattr(row, column.name)
        return out
