"""Domain model for agentic delivery cycles."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


def utcnow() -> datetime:
    return datetime.now(UTC)


class CycleStatus(StrEnum):
    DRAFT = "Draft"
    READY = "Ready"
    RUNNING = "Running"
    REVIEW = "Review"
    REWORK = "Rework"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    CANCELLED = "Cancelled"
    FAILED = "Failed"


class GateType(StrEnum):
    PRODUCT = "product"
    ARCHITECTURE = "architecture"
    QUALITY = "quality"
    COMPLIANCE = "compliance"


class GateStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    BLOCKED = "blocked"


class ReviewDecisionValue(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_REWORK = "request_rework"
    COMMENT = "comment"


class OutputType(StrEnum):
    REQUIREMENTS = "requirements"
    DESIGN = "design"
    CODE_CHANGE = "code_change"
    TEST_RESULT = "test_result"
    RISK = "risk"
    RECOMMENDATION = "recommendation"
    SUMMARY = "summary"


class ValidationStatus(StrEnum):
    NOT_RUN = "not_run"
    PASSED = "passed"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"


class EvidenceSourceType(StrEnum):
    REPOSITORY = "repository"
    ATTACHMENT = "attachment"
    EXTERNAL_DOC = "external_doc"
    PRIOR_DECISION = "prior_decision"
    OPERATIONAL_SIGNAL = "operational_signal"


class EvidenceSupportStatus(StrEnum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    CONTRADICTED = "contradicted"
    STALE = "stale"


class KnowledgeType(StrEnum):
    DECISION = "decision"
    CONSTRAINT = "constraint"
    LESSON = "lesson"
    SOURCE_RELATIONSHIP = "source_relationship"


class AgenticPermissionValue(StrEnum):
    MANAGE_SENSITIVE_SURFACES = "manage_sensitive_surfaces"
    AUTHORIZE_EXTERNAL_ACTION = "authorize_external_action"


class ExternalActionType(StrEnum):
    PUSH = "push"
    PULL_REQUEST = "pull_request"
    DEPLOYMENT = "deployment"
    NETWORK_CALL = "network_call"
    CONTAINER_CHANGE = "container_change"
    OTHER = "other"


class ExternalActionStatus(StrEnum):
    AUTHORIZED = "authorized"
    EXECUTED = "executed"
    DENIED = "denied"
    FAILED = "failed"


class CycleMetricSource(StrEnum):
    SYSTEM = "system"
    PROVIDER_USAGE = "provider_usage"
    REVIEWER = "reviewer"
    IMPORTED_BASELINE = "imported_baseline"


class AgenticDeliveryError(Exception):
    """Base exception for agentic delivery domain failures."""


class InvalidTransitionError(AgenticDeliveryError):
    """Raised when a lifecycle transition is not allowed."""


class IncompleteGatesError(AgenticDeliveryError):
    """Raised when approval or external action lacks completed gates."""


class UnauthorizedKnowledgeError(AgenticDeliveryError):
    """Raised when retrieval would cross an unauthorized repository/domain."""


class DeniedExternalActionError(AgenticDeliveryError):
    """Raised when external action authorization is denied."""


class InvalidSensitiveSurfaceError(AgenticDeliveryError):
    """Raised when a sensitive surface rule is invalid."""


class UnsupportedEvidenceClaimError(AgenticDeliveryError):
    """Raised when required evidence support is missing."""


FINAL_STATUSES = {
    CycleStatus.APPROVED,
    CycleStatus.REJECTED,
    CycleStatus.CANCELLED,
    CycleStatus.FAILED,
}

VALID_TRANSITIONS: dict[CycleStatus, set[CycleStatus]] = {
    CycleStatus.DRAFT: {CycleStatus.READY, CycleStatus.CANCELLED},
    CycleStatus.READY: {CycleStatus.RUNNING, CycleStatus.CANCELLED},
    CycleStatus.RUNNING: {CycleStatus.REVIEW, CycleStatus.FAILED, CycleStatus.CANCELLED},
    CycleStatus.REVIEW: {
        CycleStatus.REWORK,
        CycleStatus.APPROVED,
        CycleStatus.REJECTED,
        CycleStatus.CANCELLED,
    },
    CycleStatus.REWORK: {CycleStatus.READY, CycleStatus.RUNNING, CycleStatus.CANCELLED},
    CycleStatus.APPROVED: set(),
    CycleStatus.REJECTED: set(),
    CycleStatus.CANCELLED: set(),
    CycleStatus.FAILED: set(),
}


@dataclass
class ReviewGate:
    id: uuid.UUID
    cycle_id: uuid.UUID
    gate_type: GateType
    status: GateStatus = GateStatus.PENDING
    required: bool = True
    trigger_reason: str = ""
    assigned_user_id: uuid.UUID | None = None
    decided_by_user_id: uuid.UUID | None = None
    decision_rationale: str | None = None
    decided_at: datetime | None = None


@dataclass
class AgenticDeliveryCycle:
    id: uuid.UUID
    created_by_user_id: uuid.UUID
    repository_ids: list[uuid.UUID]
    title: str
    business_goal: str
    scope_boundary: str
    expected_outputs: list[str]
    acceptance_expectations: list[str]
    conversation_id: uuid.UUID | None = None
    domain_key: str | None = None
    status: CycleStatus = CycleStatus.DRAFT
    execution_window_started_at: datetime | None = None
    execution_window_finished_at: datetime | None = None
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def missing_ready_inputs(self) -> list[str]:
        missing: list[str] = []
        if not self.repository_ids:
            missing.append("repository_ids")
        for attr in ("business_goal", "scope_boundary", "title"):
            if not getattr(self, attr).strip():
                missing.append(attr)
        if not self.expected_outputs:
            missing.append("expected_outputs")
        if not self.acceptance_expectations:
            missing.append("acceptance_expectations")
        return missing


@dataclass
class StructuredWorkPackage:
    id: uuid.UUID
    cycle_id: uuid.UUID
    version: int
    instructions: str
    constraints: list[str]
    review_criteria: list[str]
    source_summary: dict[str, Any]
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class EvidenceSource:
    id: uuid.UUID
    cycle_id: uuid.UUID
    source_type: EvidenceSourceType
    title: str
    scope_note: str
    repository_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None
    attachment_id: uuid.UUID | None = None
    source_url: str | None = None
    available: bool = True
    created_at: datetime = field(default_factory=utcnow)


def validate_transition(
    from_status: CycleStatus,
    to_status: CycleStatus,
    gates: list[ReviewGate] | None = None,
    *,
    has_review_history: bool = False,
) -> None:
    if to_status not in VALID_TRANSITIONS[from_status]:
        raise InvalidTransitionError(f"Transição inválida: {from_status} -> {to_status}.")
    if to_status is CycleStatus.APPROVED:
        if not has_review_history and from_status is not CycleStatus.REVIEW:
            raise InvalidTransitionError("Aprovação final exige passagem por Review.")
        incomplete = [
            g.gate_type.value for g in gates or [] if g.required and g.status != GateStatus.APPROVED
        ]
        if incomplete:
            raise IncompleteGatesError("Gates pendentes: " + ", ".join(incomplete))


def required_initial_gates() -> list[GateType]:
    return [GateType.PRODUCT, GateType.ARCHITECTURE, GateType.QUALITY]


def validate_sensitive_surface_rules(match_rules: dict[str, Any]) -> None:
    if not isinstance(match_rules, dict) or not match_rules:
        raise InvalidSensitiveSurfaceError("Regras de superfície sensível são obrigatórias.")
    path_prefixes = match_rules.get("path_prefixes", [])
    keywords = match_rules.get("keywords", [])
    if path_prefixes is not None and not isinstance(path_prefixes, list):
        raise InvalidSensitiveSurfaceError("path_prefixes deve ser uma lista.")
    if keywords is not None and not isinstance(keywords, list):
        raise InvalidSensitiveSurfaceError("keywords deve ser uma lista.")
    if not path_prefixes and not keywords:
        raise InvalidSensitiveSurfaceError("Informe ao menos path_prefixes ou keywords.")


def surface_matches(match_rules: dict[str, Any], texts: list[str], paths: list[str]) -> bool:
    validate_sensitive_surface_rules(match_rules)
    lowered_text = "\n".join(texts).lower()
    lowered_paths = [p.lower() for p in paths]
    for keyword in match_rules.get("keywords", []) or []:
        if str(keyword).lower() in lowered_text:
            return True
    for prefix in match_rules.get("path_prefixes", []) or []:
        pfx = str(prefix).lower()
        if any(path.startswith(pfx) or f"/{pfx}" in path for path in lowered_paths):
            return True
    return False
