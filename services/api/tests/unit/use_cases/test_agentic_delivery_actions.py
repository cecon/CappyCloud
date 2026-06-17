import uuid

import pytest
from app.application.use_cases.agentic_delivery_actions import AuthorizeExternalAction
from app.domain.agentic_delivery import (
    AgenticPermissionValue,
    CycleStatus,
    DeniedExternalActionError,
)
from app.ports.agentic_delivery import CycleCreate

from tests.fakes_agentic_delivery import FakeAgenticDeliveryRepository


@pytest.mark.asyncio
async def test_external_action_requires_active_permission_and_approved_gates() -> None:
    repo = FakeAgenticDeliveryRepository()
    user_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    cycle = await repo.create_cycle(
        CycleCreate(
            created_by_user_id=user_id,
            repository_ids=[repo_id],
            title="Fiscal",
            business_goal="Goal",
            scope_boundary="Scope",
            expected_outputs=["code_change"],
            acceptance_expectations=["approved"],
        )
    )
    for gate in repo.gates:
        gate["status"] = "approved"
    cycle["status"] = CycleStatus.APPROVED.value
    repo.cycles[cycle["id"]] = cycle

    with pytest.raises(DeniedExternalActionError):
        await AuthorizeExternalAction(repo).execute(
            cycle["id"],
            user_id,
            {"action_type": "pull_request", "repository_id": repo_id, "rationale": "ok"},
        )

    await repo.upsert_permission(
        uuid.uuid4(),
        user_id,
        uuid.uuid4(),
        AgenticPermissionValue.AUTHORIZE_EXTERNAL_ACTION,
        True,
        repository_id=repo_id,
    )
    auth = await AuthorizeExternalAction(repo).execute(
        cycle["id"],
        user_id,
        {"action_type": "pull_request", "repository_id": repo_id, "rationale": "ok"},
    )

    assert auth["execution_status"] == "authorized"
