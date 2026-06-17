"""ORM models for the agentic delivery factory."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.orm_base import Base, JSONBType, UUIDType


class AgenticDeliveryCycle(Base):
    __tablename__ = "agentic_delivery_cycles"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("conversations.id", ondelete="SET NULL"), index=True
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    repository_ids: Mapped[list] = mapped_column(JSONBType, nullable=False, default=list)
    domain_key: Mapped[str | None] = mapped_column(String(128), index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    business_goal: Mapped[str] = mapped_column(Text, nullable=False)
    scope_boundary: Mapped[str] = mapped_column(Text, nullable=False)
    expected_outputs: Mapped[list] = mapped_column(JSONBType, nullable=False, default=list)
    acceptance_expectations: Mapped[list] = mapped_column(JSONBType, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="Draft", index=True)
    execution_window_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    execution_window_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LifecycleTransition(Base):
    __tablename__ = "agentic_delivery_lifecycle_transitions"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    cycle_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("agentic_delivery_cycles.id", ondelete="CASCADE"), index=True
    )
    from_status: Mapped[str] = mapped_column(String(32), nullable=False)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("users.id", ondelete="SET NULL")
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StructuredWorkPackage(Base):
    __tablename__ = "agentic_delivery_work_packages"
    __table_args__ = (
        Index("ix_agentic_delivery_work_packages_cycle_version", "cycle_id", "version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    cycle_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("agentic_delivery_cycles.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    constraints: Mapped[list] = mapped_column(JSONBType, nullable=False, default=list)
    review_criteria: Mapped[list] = mapped_column(JSONBType, nullable=False, default=list)
    source_summary: Mapped[dict] = mapped_column(JSONBType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EvidenceSource(Base):
    __tablename__ = "agentic_delivery_evidence_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    cycle_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("agentic_delivery_cycles.id", ondelete="CASCADE"), index=True
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    repository_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("repositories.id", ondelete="SET NULL"), index=True
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, index=True)
    attachment_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, index=True)
    source_url: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    scope_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentOutput(Base):
    __tablename__ = "agentic_delivery_outputs"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    cycle_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("agentic_delivery_cycles.id", ondelete="CASCADE"), index=True
    )
    output_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    worktree_path: Mapped[str | None] = mapped_column(Text)
    validation_status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_run")
    unsupported_claims_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentOutputEvidenceLink(Base):
    __tablename__ = "agentic_delivery_output_evidence_links"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    agent_output_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("agentic_delivery_outputs.id", ondelete="CASCADE"), index=True
    )
    evidence_source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("agentic_delivery_evidence_sources.id", ondelete="SET NULL")
    )
    claim_summary: Mapped[str] = mapped_column(Text, nullable=False)
    support_status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReviewGate(Base):
    __tablename__ = "agentic_delivery_review_gates"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    cycle_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("agentic_delivery_cycles.id", ondelete="CASCADE"), index=True
    )
    gate_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    trigger_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, index=True)
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, index=True)
    decision_rationale: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReviewDecision(Base):
    __tablename__ = "agentic_delivery_review_decisions"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    cycle_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("agentic_delivery_cycles.id", ondelete="CASCADE"), index=True
    )
    agent_output_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, index=True)
    review_gate_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, index=True)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    decided_by_user_id: Mapped[uuid.UUID] = mapped_column(UUIDType, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgenticDeliveryPermission(Base):
    __tablename__ = "agentic_delivery_permissions"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUIDType, nullable=False, index=True)
    repository_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, index=True)
    domain_key: Mapped[str | None] = mapped_column(String(128), index=True)
    permission: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    granted_by_user_id: Mapped[uuid.UUID] = mapped_column(UUIDType, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SensitiveSurface(Base):
    __tablename__ = "agentic_delivery_sensitive_surfaces"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, index=True)
    domain_key: Mapped[str | None] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    match_rules: Mapped[dict] = mapped_column(JSONBType, nullable=False, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReusableKnowledgeItem(Base):
    __tablename__ = "agentic_delivery_knowledge_items"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(UUIDType, nullable=False, index=True)
    domain_key: Mapped[str | None] = mapped_column(String(128), index=True)
    cycle_id: Mapped[uuid.UUID] = mapped_column(UUIDType, nullable=False, index=True)
    knowledge_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_source_ids: Mapped[list] = mapped_column(JSONBType, nullable=False, default=list)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KnowledgeReuseRelationship(Base):
    __tablename__ = "agentic_delivery_knowledge_reuse_relationships"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    source_repository_id: Mapped[uuid.UUID] = mapped_column(UUIDType, nullable=False, index=True)
    target_repository_id: Mapped[uuid.UUID] = mapped_column(UUIDType, nullable=False, index=True)
    source_domain_key: Mapped[str | None] = mapped_column(String(128), index=True)
    target_domain_key: Mapped[str | None] = mapped_column(String(128), index=True)
    authorized_by_user_id: Mapped[uuid.UUID] = mapped_column(UUIDType, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExternalActionAuthorization(Base):
    __tablename__ = "agentic_delivery_external_action_authorizations"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    cycle_id: Mapped[uuid.UUID] = mapped_column(UUIDType, nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_payload: Mapped[dict] = mapped_column(JSONBType, nullable=False, default=dict)
    authorized_by_user_id: Mapped[uuid.UUID] = mapped_column(UUIDType, nullable=False, index=True)
    repository_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, index=True)
    domain_key: Mapped[str | None] = mapped_column(String(128), index=True)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    authorized_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    execution_status: Mapped[str] = mapped_column(String(32), nullable=False, default="authorized")


class CycleMetric(Base):
    __tablename__ = "agentic_delivery_metrics"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    cycle_id: Mapped[uuid.UUID] = mapped_column(UUIDType, nullable=False, index=True)
    metric_name: Mapped[str] = mapped_column(String(128), nullable=False)
    metric_value: Mapped[float | None] = mapped_column(Numeric(18, 6))
    metric_text: Mapped[str | None] = mapped_column(Text)
    metric_unit: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
