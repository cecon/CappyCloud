import uuid

import pytest
from app.application.use_cases.agentic_delivery_prepare import (
    CreateAgenticDeliveryCycle,
    PrepareStructuredWorkPackage,
)
from app.application.use_cases.agentic_delivery_review import (
    GetReviewPackage,
    LinkAgentOutputEvidence,
    RecordReviewDecision,
)
from app.domain.agentic_delivery import CycleStatus, EvidenceSupportStatus, ReviewDecisionValue
from app.domain.entities import UserRole

from tests.fakes_agentic_delivery import FakeAgenticDeliveryRepository
from tests.unit.use_cases.test_agentic_delivery_prepare import AccessFake


async def _ready_cycle(repo: FakeAgenticDeliveryRepository) -> dict:
    repo_id = uuid.uuid4()
    cycle = await CreateAgenticDeliveryCycle(repo, AccessFake({repo_id})).execute(
        uuid.uuid4(),
        UserRole.USER,
        {
            "repository_ids": [repo_id],
            "title": "Mudança fiscal",
            "business_goal": "Ajustar NFCe",
            "scope_boundary": "Somente fiscal",
            "expected_outputs": ["code_change"],
            "acceptance_expectations": ["evidência citada"],
            "evidence_sources": [],
        },
    )
    await PrepareStructuredWorkPackage(repo, AccessFake({repo_id})).execute(
        cycle["id"], uuid.uuid4(), UserRole.USER
    )
    ready = await repo.get_cycle(cycle["id"])
    assert ready is not None
    return ready


@pytest.mark.asyncio
async def test_review_package_triggers_compliance_gate_from_output_surface() -> None:
    repo = FakeAgenticDeliveryRepository()
    cycle = await _ready_cycle(repo)
    repo.surfaces[uuid.uuid4()] = {
        "id": uuid.uuid4(),
        "repository_id": cycle["repository_ids"][0],
        "domain_key": None,
        "name": "Fiscal",
        "description": "Fiscal",
        "match_rules": {"keywords": ["ICMS"], "path_prefixes": []},
        "active": True,
    }
    await repo.create_agent_output(
        cycle["id"],
        {
            "output_type": "code_change",
            "title": "Ajuste ICMS",
            "content": "Altera cálculo de ICMS",
            "worktree_path": "fiscal/nfce.py",
            "validation_status": "passed",
            "unsupported_claims_count": 0,
        },
    )

    result = await GetReviewPackage(repo, AccessFake(set(cycle["repository_ids"]))).execute(
        cycle["id"], uuid.uuid4(), UserRole.USER, 50, None, 20, None
    )

    assert any(g["gate_type"] == "compliance" for g in result["gates"])


@pytest.mark.asyncio
async def test_link_output_evidence_requires_source_for_supported_claim() -> None:
    repo = FakeAgenticDeliveryRepository()
    cycle = await _ready_cycle(repo)
    output = await repo.create_agent_output(
        cycle["id"],
        {
            "output_type": "recommendation",
            "title": "Recomendação",
            "content": "usar regra fiscal",
            "worktree_path": None,
            "validation_status": "not_run",
            "unsupported_claims_count": 0,
        },
    )

    with pytest.raises(ValueError):
        await LinkAgentOutputEvidence(repo, AccessFake(set(cycle["repository_ids"]))).execute(
            cycle["id"],
            uuid.uuid4(),
            UserRole.USER,
            output["id"],
            None,
            "regra fiscal",
            EvidenceSupportStatus.SUPPORTED,
        )


@pytest.mark.asyncio
async def test_request_rework_moves_review_cycle_to_rework() -> None:
    repo = FakeAgenticDeliveryRepository()
    cycle = await _ready_cycle(repo)
    await repo.update_cycle_status(
        cycle["id"], CycleStatus.READY, CycleStatus.REVIEW, None, "em revisão"
    )

    result = await RecordReviewDecision(repo, AccessFake(set(cycle["repository_ids"]))).execute(
        cycle["id"],
        uuid.uuid4(),
        UserRole.USER,
        ReviewDecisionValue.REQUEST_REWORK,
        "ajustar",
        None,
        None,
    )

    assert result["cycle"]["status"] == "Rework"
