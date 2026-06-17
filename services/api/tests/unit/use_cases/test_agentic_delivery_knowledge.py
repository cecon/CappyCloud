import uuid

import pytest
from app.application.use_cases.agentic_delivery_knowledge import SearchReusableKnowledge
from app.domain.entities import UserRole

from tests.fakes_agentic_delivery import FakeAgenticDeliveryAudit, FakeAgenticDeliveryRepository
from tests.unit.use_cases.test_agentic_delivery_prepare import AccessFake


@pytest.mark.asyncio
async def test_knowledge_search_filters_unauthorized_repositories_before_results() -> None:
    repo = FakeAgenticDeliveryRepository()
    allowed_repo = uuid.uuid4()
    denied_repo = uuid.uuid4()
    repo.knowledge.extend(
        [
            {
                "id": uuid.uuid4(),
                "repository_id": allowed_repo,
                "domain_key": "erp-a",
                "knowledge_type": "decision",
                "title": "NFCe autorizada",
                "content": "parametrização NFCe",
                "needs_review": False,
            },
            {
                "id": uuid.uuid4(),
                "repository_id": denied_repo,
                "domain_key": "erp-b",
                "knowledge_type": "decision",
                "title": "NFCe cliente B",
                "content": "parametrização NFCe",
                "needs_review": False,
            },
        ]
    )
    audit = FakeAgenticDeliveryAudit()

    result = await SearchReusableKnowledge(repo, AccessFake({allowed_repo}), audit).execute(
        uuid.uuid4(),
        UserRole.USER,
        [allowed_repo, denied_repo],
        None,
        "NFCe",
        10,
        None,
    )

    assert [item["repository_id"] for item in result["items"]] == [allowed_repo]
    assert audit.events
