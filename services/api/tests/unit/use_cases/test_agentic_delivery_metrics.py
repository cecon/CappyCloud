import uuid

import pytest
from app.application.use_cases.agentic_delivery_metrics import GetCycleMetrics, PersistCycleMetric
from app.domain.entities import UserRole

from tests.fakes_agentic_delivery import FakeAgenticDeliveryRepository
from tests.unit.use_cases.test_agentic_delivery_prepare import AccessFake


@pytest.mark.asyncio
async def test_cycle_metrics_are_paginated_and_preserved() -> None:
    repo = FakeAgenticDeliveryRepository()
    cycle_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    repo.cycles[cycle_id] = {"id": cycle_id, "repository_ids": [repo_id], "status": "Review"}
    await PersistCycleMetric(repo).execute(cycle_id, "rework_count", 2, "count")
    await PersistCycleMetric(repo).execute(
        cycle_id, "provider_usage_available", None, "state", text="not_available"
    )

    result = await GetCycleMetrics(repo, AccessFake({repo_id})).execute(
        cycle_id, uuid.uuid4(), UserRole.USER, limit=1, cursor=None
    )

    assert result["metrics"][0]["metric_name"] == "rework_count"
    assert result["next_cursor"] == "1"
