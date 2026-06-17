import uuid

import pytest
from app.application.use_cases.agentic_delivery_prepare import (
    CreateAgenticDeliveryCycle,
    PrepareStructuredWorkPackage,
)
from app.domain.entities import UserRole

from tests.fakes_agentic_delivery import FakeAgenticDeliveryRepository


class AccessFake:
    def __init__(self, allowed: set[uuid.UUID]) -> None:
        self.allowed = allowed

    async def has_access(self, user_id: uuid.UUID, resource_id: uuid.UUID) -> bool:
        del user_id
        return resource_id in self.allowed

    async def list_resources_for_user(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        del user_id
        return list(self.allowed)

    async def grant(self, user_id: uuid.UUID, resource_id: uuid.UUID) -> None:
        del user_id
        self.allowed.add(resource_id)

    async def revoke(self, user_id: uuid.UUID, resource_id: uuid.UUID) -> bool:
        del user_id
        self.allowed.discard(resource_id)
        return True


@pytest.mark.asyncio
async def test_create_and_prepare_cycle_reaches_ready() -> None:
    repo = FakeAgenticDeliveryRepository()
    repo_id = uuid.uuid4()
    create = CreateAgenticDeliveryCycle(repo, AccessFake({repo_id}))
    cycle = await create.execute(
        uuid.uuid4(),
        UserRole.USER,
        {
            "repository_ids": [repo_id],
            "title": "Fiscal",
            "business_goal": "Preparar mudança",
            "scope_boundary": "NFCe",
            "expected_outputs": ["code_change"],
            "acceptance_expectations": ["gates aprovados"],
            "evidence_sources": [],
        },
    )

    result = await PrepareStructuredWorkPackage(repo, AccessFake({repo_id})).execute(
        cycle["id"], uuid.uuid4(), UserRole.USER
    )

    assert result["cycle"]["status"] == "Ready"
    assert result["work_package"]["review_criteria"] == ["gates aprovados"]


@pytest.mark.asyncio
async def test_create_cycle_denies_unauthorized_repository() -> None:
    repo = FakeAgenticDeliveryRepository()
    create = CreateAgenticDeliveryCycle(repo, AccessFake(set()))

    with pytest.raises(PermissionError):
        await create.execute(
            uuid.uuid4(),
            UserRole.USER,
            {
                "repository_ids": [uuid.uuid4()],
                "title": "Fiscal",
                "business_goal": "Preparar mudança",
                "scope_boundary": "NFCe",
                "expected_outputs": ["code_change"],
                "acceptance_expectations": ["gates aprovados"],
                "evidence_sources": [],
            },
        )


@pytest.mark.asyncio
async def test_prepare_triggers_compliance_gate_for_sensitive_surface() -> None:
    repo = FakeAgenticDeliveryRepository()
    repo_id = uuid.uuid4()
    repo.surfaces[uuid.uuid4()] = {
        "id": uuid.uuid4(),
        "repository_id": repo_id,
        "domain_key": None,
        "name": "Fiscal",
        "description": "Fiscal",
        "match_rules": {"keywords": ["NFCe"], "path_prefixes": []},
        "active": True,
    }
    cycle = await CreateAgenticDeliveryCycle(repo, AccessFake({repo_id})).execute(
        uuid.uuid4(),
        UserRole.USER,
        {
            "repository_ids": [repo_id],
            "title": "Fiscal",
            "business_goal": "Preparar NFCe",
            "scope_boundary": "NFCe",
            "expected_outputs": ["code_change"],
            "acceptance_expectations": ["gates aprovados"],
            "evidence_sources": [],
        },
    )

    await PrepareStructuredWorkPackage(repo, AccessFake({repo_id})).execute(
        cycle["id"], uuid.uuid4(), UserRole.USER
    )

    gates = await repo.list_gates(cycle["id"])
    assert any(g["gate_type"] == "compliance" for g in gates)
