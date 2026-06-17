import uuid

import pytest
from app.domain.agentic_delivery import (
    CycleStatus,
    GateStatus,
    GateType,
    IncompleteGatesError,
    InvalidSensitiveSurfaceError,
    InvalidTransitionError,
    ReviewGate,
    validate_sensitive_surface_rules,
    validate_transition,
)


def test_approved_requires_review_transition_and_completed_gates() -> None:
    gate = ReviewGate(
        id=uuid.uuid4(),
        cycle_id=uuid.uuid4(),
        gate_type=GateType.QUALITY,
        status=GateStatus.APPROVED,
    )

    validate_transition(CycleStatus.REVIEW, CycleStatus.APPROVED, [gate], has_review_history=True)

    with pytest.raises(InvalidTransitionError):
        validate_transition(CycleStatus.READY, CycleStatus.APPROVED, [gate])


def test_approved_blocks_incomplete_required_gate() -> None:
    gate = ReviewGate(
        id=uuid.uuid4(),
        cycle_id=uuid.uuid4(),
        gate_type=GateType.QUALITY,
        status=GateStatus.PENDING,
    )

    with pytest.raises(IncompleteGatesError):
        validate_transition(
            CycleStatus.REVIEW,
            CycleStatus.APPROVED,
            [gate],
            has_review_history=True,
        )


def test_sensitive_surface_rules_require_matcher() -> None:
    validate_sensitive_surface_rules({"keywords": ["NFCe"]})

    with pytest.raises(InvalidSensitiveSurfaceError):
        validate_sensitive_surface_rules({})
