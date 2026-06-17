from __future__ import annotations

import uuid

import pytest
from app.adapters.primary.http.deps_agentic_delivery import get_agentic_delivery_repo
from app.domain.agentic_delivery import (
    AgenticPermissionValue,
    GateStatus,
    GateType,
)
from app.domain.entities import UserRole
from app.main import app
from httpx import AsyncClient

from tests.conftest import InMemoryUserRepository
from tests.fakes_agentic_delivery import FakeAgenticDeliveryRepository
from tests.integration.conftest import seed_user


@pytest.fixture
async def agentic_repo() -> FakeAgenticDeliveryRepository:
    repo = FakeAgenticDeliveryRepository()
    app.dependency_overrides[get_agentic_delivery_repo] = lambda: repo
    try:
        yield repo
    finally:
        app.dependency_overrides.pop(get_agentic_delivery_repo, None)


async def _headers(
    client: AsyncClient, users: InMemoryUserRepository
) -> tuple[dict[str, str], uuid.UUID]:
    user = await seed_user(users, f"agentic-{uuid.uuid4()}@test.com", role=UserRole.ADMIN)
    r = await client.post(
        "/api/auth/login",
        data={"username": user.email, "password": "password123"},
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, user.id


async def _create_ready_cycle(
    client: AsyncClient,
    headers: dict[str, str],
    repo_id: uuid.UUID,
) -> dict:
    created = await client.post(
        "/api/agentic-cycles",
        headers=headers,
        json={
            "repository_ids": [str(repo_id)],
            "domain_key": "erp-a",
            "title": "Mudança fiscal",
            "business_goal": "Ajustar NFCe com ICMS",
            "scope_boundary": "Somente fiscal",
            "expected_outputs": ["code_change"],
            "acceptance_expectations": ["evidência citada"],
        },
    )
    assert created.status_code == 201
    prepared = await client.post(
        f"/api/agentic-cycles/{created.json()['id']}/prepare",
        headers=headers,
    )
    assert prepared.status_code == 200
    return {"cycle": created.json(), "prepared": prepared.json()}


class TestAgenticDeliveryHttp:
    async def test_create_prepare_and_sensitive_surface_gate(
        self,
        client: AsyncClient,
        user_repo: InMemoryUserRepository,
        agentic_repo: FakeAgenticDeliveryRepository,
    ) -> None:
        del agentic_repo
        headers, _user_id = await _headers(client, user_repo)
        repo_id = uuid.uuid4()
        surface = await client.put(
            f"/api/agentic-cycles/sensitive-surfaces/{uuid.uuid4()}",
            headers=headers,
            json={
                "repository_id": str(repo_id),
                "domain_key": "erp-a",
                "name": "Fiscal",
                "description": "Fiscal",
                "match_rules": {"keywords": ["ICMS"], "path_prefixes": []},
                "active": True,
            },
        )

        result = await _create_ready_cycle(client, headers, repo_id)

        assert surface.status_code == 200
        assert result["prepared"]["status"] == "Ready"
        assert "compliance" in result["prepared"]["required_gates"]

    async def test_review_knowledge_metrics_and_external_action_flow(
        self,
        client: AsyncClient,
        user_repo: InMemoryUserRepository,
        agentic_repo: FakeAgenticDeliveryRepository,
    ) -> None:
        headers, user_id = await _headers(client, user_repo)
        repo_id = uuid.uuid4()
        result = await _create_ready_cycle(client, headers, repo_id)
        cycle_id = result["cycle"]["id"]

        run = await client.post(f"/api/agentic-cycles/{cycle_id}/run", headers=headers, json={})
        assert run.status_code == 202

        output = await agentic_repo.create_agent_output(
            uuid.UUID(cycle_id),
            {
                "output_type": "recommendation",
                "title": "Regra",
                "content": "Sem evidência",
                "worktree_path": None,
                "validation_status": "not_run",
                "unsupported_claims_count": 0,
            },
        )
        link = await client.post(
            f"/api/agentic-cycles/{cycle_id}/outputs/{output['id']}/evidence-links",
            headers=headers,
            json={"claim_summary": "sem fonte", "support_status": "unsupported"},
        )
        assert link.status_code == 201
        decision = await client.post(
            f"/api/agentic-cycles/{cycle_id}/review-decisions",
            headers=headers,
            json={
                "agent_output_id": str(output["id"]),
                "decision": "comment",
                "rationale": "precisa de fonte",
            },
        )
        assert decision.status_code == 201

        await client.post(
            f"/api/agentic-cycles/{cycle_id}/transition",
            headers=headers,
            json={"to_status": "Review", "reason": "outputs disponíveis"},
        )
        for gate in agentic_repo.gates:
            if gate["cycle_id"] != uuid.UUID(cycle_id):
                continue
            gate["status"] = GateStatus.APPROVED.value
            gate["gate_type"] = GateType(gate["gate_type"]).value
        transition = await client.post(
            f"/api/agentic-cycles/{cycle_id}/transition",
            headers=headers,
            json={"to_status": "Approved", "reason": "gates aprovados"},
        )

        await agentic_repo.upsert_permission(
            uuid.uuid4(),
            user_id,
            user_id,
            AgenticPermissionValue.AUTHORIZE_EXTERNAL_ACTION,
            True,
            repository_id=repo_id,
            domain_key="erp-a",
        )
        action = await client.post(
            f"/api/agentic-cycles/{cycle_id}/external-actions/authorize",
            headers=headers,
            json={
                "action_type": "pull_request",
                "repository_id": str(repo_id),
                "domain_key": "erp-a",
                "requested_payload": {"target_branch": "main"},
                "rationale": "aprovado",
            },
        )
        metrics = await client.get(f"/api/agentic-cycles/{cycle_id}/metrics", headers=headers)
        review = await client.get(
            f"/api/agentic-cycles/{cycle_id}/review?outputs_limit=1&decisions_limit=1",
            headers=headers,
        )

        assert transition.status_code == 200
        assert action.status_code == 201
        assert metrics.status_code == 200
        assert review.status_code == 200

    async def test_knowledge_search_marks_items_that_need_review(
        self,
        client: AsyncClient,
        user_repo: InMemoryUserRepository,
        agentic_repo: FakeAgenticDeliveryRepository,
    ) -> None:
        headers, _user_id = await _headers(client, user_repo)
        repo_id = uuid.uuid4()
        agentic_repo.knowledge.append(
            {
                "id": uuid.uuid4(),
                "repository_id": repo_id,
                "domain_key": "erp-a",
                "knowledge_type": "decision",
                "title": "NFCe",
                "content": "regra fiscal",
                "needs_review": False,
                "evidence_source_ids": [],
            }
        )

        response = await client.post(
            "/api/agentic-cycles/knowledge/search",
            headers=headers,
            json={"repository_ids": [str(repo_id)], "domain_key": "erp-a", "query": "fiscal"},
        )

        assert response.status_code == 200
        assert response.json()["items"][0]["needs_review"] is True
