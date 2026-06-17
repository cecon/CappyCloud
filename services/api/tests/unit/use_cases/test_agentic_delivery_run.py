import uuid
from collections.abc import Generator

import pytest
from app.application.use_cases.agentic_delivery_prepare import (
    CreateAgenticDeliveryCycle,
    PrepareStructuredWorkPackage,
    RunAgenticDeliveryCycle,
)
from app.domain.entities import UserRole
from app.ports.agent import AgentPort

from tests.fakes_agentic_delivery import FakeAgenticDeliveryRepository
from tests.unit.use_cases.test_agentic_delivery_prepare import AccessFake


class RecordingAgent(AgentPort):
    def __init__(self) -> None:
        self.dispatched: dict = {}

    def pipe(
        self, user_message: str, model_id: str, messages: list[dict], body: dict
    ) -> Generator[str]:
        del user_message, model_id, messages, body
        yield 'data: {"type":"done"}\n\n'

    async def dispatch(self, prompt: str, **kwargs) -> str:
        self.dispatched = {"prompt": prompt, **kwargs}
        return str(uuid.uuid4())

    async def on_startup(self) -> None:
        pass

    async def on_shutdown(self) -> None:
        pass

    def cancel_conversation(self, conversation_id: str) -> bool:
        del conversation_id
        return False


class ModelPolicy:
    async def resolve_model_for_user(
        self, user_id: uuid.UUID, user_role: UserRole, requested_model_id: str | None
    ) -> str | None:
        del user_id, user_role
        return requested_model_id or "model-a"


@pytest.mark.asyncio
async def test_run_cycle_dispatches_review_only_context() -> None:
    repo = FakeAgenticDeliveryRepository()
    agent = RecordingAgent()
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

    result = await RunAgenticDeliveryCycle(
        repo, agent, ModelPolicy(), AccessFake({repo_id})
    ).execute(cycle["id"], uuid.uuid4(), UserRole.USER, None, "curta")

    assert result["cycle"]["status"] == "Running"
    assert agent.dispatched["trigger_payload"]["review_only"] is True
    assert "Não faça push" in agent.dispatched["prompt"]


@pytest.mark.asyncio
async def test_run_cycle_rejects_non_ready_cycle() -> None:
    repo = FakeAgenticDeliveryRepository()
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

    with pytest.raises(RuntimeError):
        await RunAgenticDeliveryCycle(
            repo, RecordingAgent(), ModelPolicy(), AccessFake({repo_id})
        ).execute(cycle["id"], uuid.uuid4(), UserRole.USER, None, None)
