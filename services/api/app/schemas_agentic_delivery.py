"""Pydantic schemas for the agentic delivery HTTP API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


def _non_empty_list(value: list[str], field_name: str) -> list[str]:
    cleaned = [str(item).strip() for item in value if str(item).strip()]
    if not cleaned:
        raise ValueError(f"{field_name} deve conter ao menos um item.")
    return cleaned


class EvidenceSourceIn(BaseModel):
    source_type: Literal[
        "repository",
        "attachment",
        "external_doc",
        "prior_decision",
        "operational_signal",
    ]
    title: str = Field(min_length=1, max_length=256)
    scope_note: str = ""
    repository_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None
    attachment_id: uuid.UUID | None = None
    source_url: str | None = None


class CreateCycleRequest(BaseModel):
    conversation_id: uuid.UUID | None = None
    repository_ids: list[uuid.UUID]
    domain_key: str | None = Field(default=None, max_length=128)
    title: str = Field(min_length=1, max_length=256)
    business_goal: str = Field(min_length=1)
    scope_boundary: str = Field(min_length=1)
    expected_outputs: list[str]
    acceptance_expectations: list[str]
    evidence_sources: list[EvidenceSourceIn] = Field(default_factory=list)

    @field_validator("repository_ids")
    @classmethod
    def repositories_required(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        if not value:
            raise ValueError("Selecione ao menos um repositório.")
        return value

    @field_validator("expected_outputs")
    @classmethod
    def outputs_required(cls, value: list[str]) -> list[str]:
        return _non_empty_list(value, "expected_outputs")

    @field_validator("acceptance_expectations")
    @classmethod
    def acceptance_required(cls, value: list[str]) -> list[str]:
        return _non_empty_list(value, "acceptance_expectations")


class CycleCreatedResponse(BaseModel):
    id: uuid.UUID
    status: str
    required_gates: list[str]
    created_at: datetime


class PrepareWorkPackageResponse(BaseModel):
    cycle_id: uuid.UUID
    status: str
    work_package_id: uuid.UUID
    missing_inputs: list[str]
    required_gates: list[str]


class RunCycleRequest(BaseModel):
    model_id: str | None = Field(default=None, max_length=256)
    execution_window: str | None = Field(default=None, max_length=128)


class RunCycleResponse(BaseModel):
    cycle_id: uuid.UUID
    status: str
    agent_task_id: uuid.UUID | None


class EvidenceLinkOut(BaseModel):
    id: uuid.UUID | None = None
    evidence_source_id: uuid.UUID | None = None
    claim_summary: str
    support_status: str


class EvidenceLinkRequest(BaseModel):
    evidence_source_id: uuid.UUID | None = None
    claim_summary: str = Field(min_length=1)
    support_status: Literal["supported", "unsupported", "contradicted", "stale"]


class AgentOutputOut(BaseModel):
    id: uuid.UUID
    output_type: str
    title: str
    validation_status: str
    unsupported_claims_count: int = 0
    evidence_links: list[EvidenceLinkOut] = Field(default_factory=list)


class ReviewGateOut(BaseModel):
    id: uuid.UUID
    gate_type: str
    status: str
    required: bool


class CycleMetricOut(BaseModel):
    metric_name: str
    metric_value: float | None = None
    metric_text: str | None = None
    metric_unit: str
    source: str = "system"


class ReviewPackageResponse(BaseModel):
    cycle: dict[str, Any]
    work_package: dict[str, Any] | None
    outputs: list[AgentOutputOut]
    gates: list[ReviewGateOut]
    metrics: list[CycleMetricOut] = Field(default_factory=list)
    outputs_next_cursor: str | None = None
    decisions_next_cursor: str | None = None


class RecordReviewDecisionRequest(BaseModel):
    agent_output_id: uuid.UUID | None = None
    review_gate_id: uuid.UUID | None = None
    decision: Literal["approve", "reject", "request_rework", "comment"]
    rationale: str = Field(min_length=1)


class ReviewDecisionResponse(BaseModel):
    id: uuid.UUID
    cycle_id: uuid.UUID
    decision: str
    cycle_status: str


class TransitionCycleRequest(BaseModel):
    to_status: Literal[
        "Draft",
        "Ready",
        "Running",
        "Review",
        "Rework",
        "Approved",
        "Rejected",
        "Cancelled",
        "Failed",
    ]
    reason: str = Field(min_length=1)


class TransitionCycleResponse(BaseModel):
    cycle_id: uuid.UUID
    from_status: str
    to_status: str


class KnowledgeSearchRequest(BaseModel):
    repository_ids: list[uuid.UUID]
    domain_key: str | None = None
    query: str = Field(default="", max_length=1000)
    limit: int = Field(default=10, ge=1, le=100)
    cursor: str | None = None


class KnowledgeItemOut(BaseModel):
    id: uuid.UUID
    repository_id: uuid.UUID
    domain_key: str | None = None
    knowledge_type: str
    title: str
    needs_review: bool


class KnowledgeSearchResponse(BaseModel):
    items: list[KnowledgeItemOut]
    next_cursor: str | None = None


class AgenticDeliveryPermissionRequest(BaseModel):
    user_id: uuid.UUID
    repository_id: uuid.UUID | None = None
    domain_key: str | None = Field(default=None, max_length=128)
    permission: Literal["manage_sensitive_surfaces", "authorize_external_action"]
    active: bool = True

    @field_validator("domain_key")
    @classmethod
    def normalize_domain(cls, value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None


class AgenticDeliveryPermissionResponse(AgenticDeliveryPermissionRequest):
    id: uuid.UUID


class SensitiveSurfaceRequest(BaseModel):
    repository_id: uuid.UUID | None = None
    domain_key: str | None = Field(default=None, max_length=128)
    name: str = Field(min_length=1, max_length=256)
    description: str = ""
    match_rules: dict[str, Any]
    active: bool = True


class SensitiveSurfaceOut(SensitiveSurfaceRequest):
    id: uuid.UUID


class SensitiveSurfaceListResponse(BaseModel):
    items: list[SensitiveSurfaceOut]
    next_cursor: str | None = None


class ExternalActionAuthorizationRequest(BaseModel):
    action_type: Literal[
        "push",
        "pull_request",
        "deployment",
        "network_call",
        "container_change",
        "other",
    ]
    repository_id: uuid.UUID | None = None
    domain_key: str | None = None
    requested_payload: dict[str, Any] = Field(default_factory=dict)
    rationale: str = Field(min_length=1)


class ExternalActionAuthorizationResponse(BaseModel):
    id: uuid.UUID
    cycle_id: uuid.UUID
    execution_status: str


class MetricsResponse(BaseModel):
    cycle_id: uuid.UUID
    metrics: list[CycleMetricOut]
    next_cursor: str | None = None
