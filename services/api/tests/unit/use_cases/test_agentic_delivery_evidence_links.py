import uuid

import pytest
from app.application.use_cases.agentic_delivery_review import LinkAgentOutputEvidence
from app.domain.agentic_delivery import EvidenceSupportStatus
from app.domain.entities import UserRole

from tests.fakes_agentic_delivery import FakeAgenticDeliveryRepository
from tests.unit.use_cases.test_agentic_delivery_prepare import AccessFake


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "source_required"),
    [
        (EvidenceSupportStatus.SUPPORTED, True),
        (EvidenceSupportStatus.UNSUPPORTED, False),
        (EvidenceSupportStatus.CONTRADICTED, False),
        (EvidenceSupportStatus.STALE, False),
    ],
)
async def test_evidence_link_support_states(
    status: EvidenceSupportStatus, source_required: bool
) -> None:
    repo = FakeAgenticDeliveryRepository()
    cycle_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    repo.cycles[cycle_id] = {
        "id": cycle_id,
        "repository_ids": [repo_id],
        "status": "Review",
    }
    output = await repo.create_agent_output(
        cycle_id,
        {
            "output_type": "recommendation",
            "title": "Decisão",
            "content": "conteúdo",
            "worktree_path": None,
            "validation_status": "not_run",
            "unsupported_claims_count": 0,
        },
    )
    evidence_id = uuid.uuid4() if source_required else None

    link = await LinkAgentOutputEvidence(repo, AccessFake({repo_id})).execute(
        cycle_id, uuid.uuid4(), UserRole.USER, output["id"], evidence_id, "afirmação", status
    )

    assert link["support_status"] == status.value
    if status is not EvidenceSupportStatus.SUPPORTED:
        assert repo.metrics[-1]["metric_name"] == "unsupported_claims"
