"""Ports for the agentic delivery feature."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from app.domain.agentic_delivery import (
    AgenticPermissionValue,
    CycleStatus,
    ReviewDecisionValue,
)


@dataclass(frozen=True)
class Page:
    items: list[Any]
    next_cursor: str | None = None


@dataclass(frozen=True)
class CycleCreate:
    created_by_user_id: uuid.UUID
    repository_ids: list[uuid.UUID]
    title: str
    business_goal: str
    scope_boundary: str
    expected_outputs: list[str]
    acceptance_expectations: list[str]
    conversation_id: uuid.UUID | None = None
    domain_key: str | None = None


class AgenticDeliveryRepository(ABC):
    @abstractmethod
    async def create_cycle(self, data: CycleCreate) -> dict:
        """Create a cycle and its initial required gates."""

    @abstractmethod
    async def get_cycle(self, cycle_id: uuid.UUID) -> dict | None:
        """Return a cycle projection."""

    @abstractmethod
    async def update_cycle_status(
        self,
        cycle_id: uuid.UUID,
        from_status: CycleStatus,
        to_status: CycleStatus,
        changed_by_user_id: uuid.UUID | None,
        reason: str,
    ) -> dict:
        """Update lifecycle status and persist the transition."""

    @abstractmethod
    async def create_work_package(
        self,
        cycle_id: uuid.UUID,
        instructions: str,
        constraints: list[str],
        review_criteria: list[str],
        source_summary: dict,
    ) -> dict:
        """Create a new work package version."""

    @abstractmethod
    async def latest_work_package(self, cycle_id: uuid.UUID) -> dict | None:
        """Return the latest work package."""

    @abstractmethod
    async def add_evidence_sources(self, cycle_id: uuid.UUID, sources: list[dict]) -> list[dict]:
        """Persist evidence sources for a cycle."""

    @abstractmethod
    async def list_gates(self, cycle_id: uuid.UUID) -> list[dict]:
        """Return review gates for a cycle."""

    @abstractmethod
    async def ensure_compliance_gate(self, cycle_id: uuid.UUID, reason: str) -> dict:
        """Ensure a compliance gate exists."""

    @abstractmethod
    async def record_review_decision(
        self,
        cycle_id: uuid.UUID,
        decided_by_user_id: uuid.UUID,
        decision: ReviewDecisionValue,
        rationale: str,
        agent_output_id: uuid.UUID | None = None,
        review_gate_id: uuid.UUID | None = None,
    ) -> dict:
        """Persist a human review decision."""

    @abstractmethod
    async def decide_gate(
        self,
        gate_id: uuid.UUID,
        decided_by_user_id: uuid.UUID,
        approved: bool,
        rationale: str,
    ) -> dict:
        """Approve or reject a gate."""

    @abstractmethod
    async def list_outputs(self, cycle_id: uuid.UUID, limit: int, cursor: str | None) -> Page:
        """Return paginated agent outputs."""

    @abstractmethod
    async def list_review_decisions(
        self, cycle_id: uuid.UUID, limit: int, cursor: str | None
    ) -> Page:
        """Return paginated review decisions."""

    @abstractmethod
    async def list_output_evidence_links(self, output_ids: list[uuid.UUID]) -> list[dict]:
        """Return evidence links for output ids."""

    @abstractmethod
    async def create_agent_output(self, cycle_id: uuid.UUID, output: dict) -> dict:
        """Persist an agent-produced output."""

    @abstractmethod
    async def create_output_evidence_link(self, output_id: uuid.UUID, link: dict) -> dict:
        """Persist a link between an output claim and evidence."""

    @abstractmethod
    async def list_sensitive_surfaces(
        self,
        repository_id: uuid.UUID | None,
        domain_key: str | None,
        limit: int,
        cursor: str | None,
    ) -> Page:
        """Return configured sensitive surfaces."""

    @abstractmethod
    async def save_sensitive_surface(self, surface_id: uuid.UUID, body: dict) -> dict:
        """Create or update a sensitive surface."""

    @abstractmethod
    async def search_knowledge(
        self,
        repository_ids: list[uuid.UUID],
        domain_key: str | None,
        query: str,
        limit: int,
        cursor: str | None,
    ) -> Page:
        """Search reusable knowledge after repository/domain pre-filtering."""

    @abstractmethod
    async def create_knowledge_relationship(self, body: dict) -> dict:
        """Create an explicit knowledge reuse relationship."""

    @abstractmethod
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
        """Grant, disable, or reactivate a privileged permission."""

    @abstractmethod
    async def has_permission(
        self,
        user_id: uuid.UUID,
        permission: AgenticPermissionValue,
        repository_id: uuid.UUID | None,
        domain_key: str | None,
    ) -> bool:
        """Return whether a user has an active privileged permission."""

    @abstractmethod
    async def authorize_external_action(self, body: dict) -> dict:
        """Persist an external action authorization."""

    @abstractmethod
    async def list_metrics(self, cycle_id: uuid.UUID, limit: int, cursor: str | None) -> Page:
        """Return paginated cycle metrics."""

    @abstractmethod
    async def upsert_metric(
        self,
        cycle_id: uuid.UUID,
        name: str,
        value: float | None,
        unit: str,
        source: str,
        text: str | None = None,
    ) -> dict:
        """Persist a metric record."""


class AgenticDeliveryAuditPort(ABC):
    @abstractmethod
    async def record(self, event_type: str, payload: dict) -> None:
        """Record a security or lifecycle audit event."""
