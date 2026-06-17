"""Use cases for review packages, decisions, lifecycle, and sensitive surfaces."""

from __future__ import annotations

import uuid

from app.domain.agentic_delivery import (
    AgenticPermissionValue,
    CycleStatus,
    EvidenceSupportStatus,
    GateStatus,
    GateType,
    ReviewDecisionValue,
    ReviewGate,
    surface_matches,
    validate_sensitive_surface_rules,
    validate_transition,
)
from app.domain.entities import User, UserRole
from app.ports.agentic_delivery import AgenticDeliveryRepository
from app.ports.user_access import UserRepositoryAccessRepository


class GetReviewPackage:
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
        outputs_limit: int,
        outputs_cursor: str | None,
        decisions_limit: int,
        decisions_cursor: str | None,
    ) -> dict:
        cycle = await self._require_cycle(cycle_id)
        await self._ensure_cycle_access(cycle, user_id, user_role)
        outputs = await self._repo.list_outputs(cycle_id, outputs_limit, outputs_cursor)
        decisions = await self._repo.list_review_decisions(
            cycle_id, decisions_limit, decisions_cursor
        )
        await self._apply_output_sensitive_surface_triggers(cycle, outputs.items)
        gates = await self._repo.list_gates(cycle_id)
        links = await self._repo.list_output_evidence_links([o["id"] for o in outputs.items])
        by_output: dict[uuid.UUID, list[dict]] = {}
        for link in links:
            by_output.setdefault(link["agent_output_id"], []).append(link)
        return {
            "cycle": cycle,
            "work_package": await self._repo.latest_work_package(cycle_id),
            "outputs": [dict(o, evidence_links=by_output.get(o["id"], [])) for o in outputs.items],
            "gates": gates,
            "decisions": decisions.items,
            "outputs_next_cursor": outputs.next_cursor,
            "decisions_next_cursor": decisions.next_cursor,
        }

    async def _apply_output_sensitive_surface_triggers(
        self, cycle: dict, outputs: list[dict]
    ) -> None:
        if not outputs:
            return
        texts = [
            str(value)
            for output in outputs
            for value in (output.get("title"), output.get("content"), output.get("output_type"))
            if value
        ]
        paths = [
            str(output.get("worktree_path")) for output in outputs if output.get("worktree_path")
        ]
        for repo_id in cycle["repository_ids"]:
            surfaces = await self._repo.list_sensitive_surfaces(
                repo_id, cycle.get("domain_key"), limit=100, cursor=None
            )
            for surface in surfaces.items:
                if surface_matches(surface["match_rules"], texts, paths):
                    await self._repo.ensure_compliance_gate(
                        cycle["id"],
                        f"Output toca superfície sensível: {surface['name']}",
                    )
                    return

    async def _require_cycle(self, cycle_id: uuid.UUID) -> dict:
        cycle = await self._repo.get_cycle(cycle_id)
        if not cycle:
            raise LookupError("Ciclo não encontrado.")
        return cycle

    async def _ensure_cycle_access(
        self, cycle: dict, user_id: uuid.UUID, user_role: UserRole
    ) -> None:
        if user_role is UserRole.ADMIN:
            return
        for repo_id in cycle["repository_ids"]:
            if not await self._access.has_access(user_id, repo_id):
                raise PermissionError("Usuário sem acesso ao ciclo selecionado.")


class RecordReviewDecision:
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
        decision: ReviewDecisionValue,
        rationale: str,
        agent_output_id: uuid.UUID | None,
        review_gate_id: uuid.UUID | None,
    ) -> dict:
        cycle = await self._require_cycle(cycle_id)
        await self._ensure_cycle_access(cycle, user_id, user_role)
        if review_gate_id and decision in {ReviewDecisionValue.APPROVE, ReviewDecisionValue.REJECT}:
            await self._repo.decide_gate(
                review_gate_id, user_id, decision is ReviewDecisionValue.APPROVE, rationale
            )
        row = await self._repo.record_review_decision(
            cycle_id, user_id, decision, rationale, agent_output_id, review_gate_id
        )
        if (
            decision is ReviewDecisionValue.REQUEST_REWORK
            and cycle["status"] == CycleStatus.REVIEW.value
        ):
            await self._repo.update_cycle_status(
                cycle_id, CycleStatus.REVIEW, CycleStatus.REWORK, user_id, "Rework solicitado."
            )
            cycle = await self._require_cycle(cycle_id)
        return {"decision": row, "cycle": cycle}

    async def _require_cycle(self, cycle_id: uuid.UUID) -> dict:
        cycle = await self._repo.get_cycle(cycle_id)
        if not cycle:
            raise LookupError("Ciclo não encontrado.")
        return cycle

    async def _ensure_cycle_access(
        self, cycle: dict, user_id: uuid.UUID, user_role: UserRole
    ) -> None:
        if user_role is UserRole.ADMIN:
            return
        for repo_id in cycle["repository_ids"]:
            if not await self._access.has_access(user_id, repo_id):
                raise PermissionError("Usuário sem acesso ao ciclo selecionado.")


class LinkAgentOutputEvidence:
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
        output_id: uuid.UUID,
        evidence_source_id: uuid.UUID | None,
        claim_summary: str,
        support_status: EvidenceSupportStatus,
    ) -> dict:
        cycle = await self._require_cycle(cycle_id)
        await self._ensure_cycle_access(cycle, user_id, user_role)
        outputs = await self._repo.list_outputs(cycle_id, limit=200, cursor=None)
        if not any(item["id"] == output_id for item in outputs.items):
            raise LookupError("Output do agente não encontrado neste ciclo.")
        if support_status is EvidenceSupportStatus.SUPPORTED and evidence_source_id is None:
            raise ValueError("Evidência é obrigatória para uma afirmação suportada.")
        row = await self._repo.create_output_evidence_link(
            output_id,
            {
                "evidence_source_id": evidence_source_id,
                "claim_summary": claim_summary.strip(),
                "support_status": support_status.value,
            },
        )
        if self._is_unsupported(support_status):
            await self._repo.upsert_metric(
                cycle["id"],
                "unsupported_claims",
                1.0,
                "count",
                "system",
                text=claim_summary.strip(),
            )
        return row

    @staticmethod
    def _is_unsupported(status: EvidenceSupportStatus) -> bool:
        return status in {
            EvidenceSupportStatus.UNSUPPORTED,
            EvidenceSupportStatus.CONTRADICTED,
            EvidenceSupportStatus.STALE,
        }

    async def _require_cycle(self, cycle_id: uuid.UUID) -> dict:
        cycle = await self._repo.get_cycle(cycle_id)
        if not cycle:
            raise LookupError("Ciclo não encontrado.")
        return cycle

    async def _ensure_cycle_access(
        self, cycle: dict, user_id: uuid.UUID, user_role: UserRole
    ) -> None:
        if user_role is UserRole.ADMIN:
            return
        for repo_id in cycle["repository_ids"]:
            if not await self._access.has_access(user_id, repo_id):
                raise PermissionError("Usuário sem acesso ao ciclo selecionado.")


class TransitionAgenticDeliveryCycle:
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
        to_status: CycleStatus,
        reason: str,
    ) -> dict:
        cycle = await self._require_cycle(cycle_id)
        await self._ensure_cycle_access(cycle, user_id, user_role)
        current = CycleStatus(cycle["status"])
        gates = await self._repo.list_gates(cycle_id)
        domain_gates = [
            ReviewGate(
                id=g["id"],
                cycle_id=cycle_id,
                gate_type=GateType(g["gate_type"]),
                status=GateStatus(g["status"]),
                required=g["required"],
            )
            for g in gates
        ]
        validate_transition(
            current,
            to_status,
            domain_gates,
            has_review_history=current is CycleStatus.REVIEW,
        )
        updated = await self._repo.update_cycle_status(
            cycle_id, current, to_status, user_id, reason
        )
        return {"cycle": updated, "from_status": current.value}

    async def _require_cycle(self, cycle_id: uuid.UUID) -> dict:
        cycle = await self._repo.get_cycle(cycle_id)
        if not cycle:
            raise LookupError("Ciclo não encontrado.")
        return cycle

    async def _ensure_cycle_access(
        self, cycle: dict, user_id: uuid.UUID, user_role: UserRole
    ) -> None:
        if user_role is UserRole.ADMIN:
            return
        for repo_id in cycle["repository_ids"]:
            if not await self._access.has_access(user_id, repo_id):
                raise PermissionError("Usuário sem acesso ao ciclo selecionado.")


class ManageSensitiveSurfaces:
    def __init__(self, repo: AgenticDeliveryRepository) -> None:
        self._repo = repo

    async def list(
        self,
        repository_id: uuid.UUID | None,
        domain_key: str | None,
        limit: int,
        cursor: str | None,
    ) -> dict:
        page = await self._repo.list_sensitive_surfaces(repository_id, domain_key, limit, cursor)
        return {"items": page.items, "next_cursor": page.next_cursor}

    async def save(self, surface_id: uuid.UUID, body: dict, current: User) -> dict:
        validate_sensitive_surface_rules(body["match_rules"])
        if not await self._can_manage(current, body.get("repository_id"), body.get("domain_key")):
            raise PermissionError("Permissão de superfície sensível necessária.")
        return await self._repo.save_sensitive_surface(surface_id, body)

    async def _can_manage(
        self, current: User, repository_id: uuid.UUID | None, domain_key: str | None
    ) -> bool:
        if current.role is UserRole.ADMIN:
            return True
        return await self._repo.has_permission(
            current.id,
            AgenticPermissionValue.MANAGE_SENSITIVE_SURFACES,
            repository_id,
            domain_key,
        )


class ManageAgenticDeliveryPermissions:
    def __init__(self, repo: AgenticDeliveryRepository) -> None:
        self._repo = repo

    async def upsert(
        self,
        permission_id: uuid.UUID,
        granted_by_user_id: uuid.UUID,
        body: dict,
    ) -> dict:
        if not body.get("repository_id") and not body.get("domain_key"):
            raise ValueError("Informe repositório ou domínio para a permissão.")
        return await self._repo.upsert_permission(
            permission_id=permission_id,
            user_id=body["user_id"],
            granted_by_user_id=granted_by_user_id,
            repository_id=body.get("repository_id"),
            domain_key=body.get("domain_key"),
            permission=AgenticPermissionValue(body["permission"]),
            active=body["active"],
        )
