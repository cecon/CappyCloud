"""Tests for chat command execution use case."""

import uuid

from app.application.use_cases.chat_command_execution import ExecuteChatCommand
from app.application.use_cases.chat_commands import ListChatCommands
from app.domain.chat_commands import (
    CommandArgument,
    CommandCategory,
    CommandExecutionEvent,
    CommandExecutionMode,
    CommandExecutionStatus,
    SlashCommand,
)
from app.domain.entities import Conversation, Message, User

from tests.conftest import InMemoryConversationRepository, InMemoryMessageRepository
from tests.fakes_chat_commands import FakeChatCommandRuntime, FakeModelProfileLookup


async def test_execute_requires_confirmation_before_state_change() -> None:
    user = User(id=uuid.uuid4(), email="u@test.com", hashed_password="x")
    conv = Conversation(id=uuid.uuid4(), user_id=user.id, title="Chat")
    convs = InMemoryConversationRepository()
    msgs = InMemoryMessageRepository()
    await convs.save(conv)
    runtime = FakeChatCommandRuntime(
        [
            SlashCommand(
                name="/model",
                description="Modelo",
                category=CommandCategory.MODEL,
                arguments=[CommandArgument(name="model", label="Modelo", required=True)],
                requires_confirmation=True,
                confirmation_reason="Pode alterar o modelo da conversa.",
                execution_mode=CommandExecutionMode.CHAT_ACTION,
            )
        ]
    )
    catalog = ListChatCommands(convs, runtime, FakeModelProfileLookup([]))

    decision = await ExecuteChatCommand(convs, msgs, runtime, catalog).execute(
        conversation_id=conv.id,
        user=user,
        command_name="/model",
        arguments={"model": "openrouter/free"},
        confirmed=False,
        client_request_id="req-1",
    )

    assert decision.status is CommandExecutionStatus.NEEDS_CONFIRMATION
    assert decision.confirmation is not None


async def test_execute_blocks_missing_arguments() -> None:
    user = User(id=uuid.uuid4(), email="u@test.com", hashed_password="x")
    conv = Conversation(id=uuid.uuid4(), user_id=user.id, title="Chat")
    convs = InMemoryConversationRepository()
    msgs = InMemoryMessageRepository()
    await convs.save(conv)
    runtime = FakeChatCommandRuntime(
        [
            SlashCommand(
                name="/model",
                description="Modelo",
                category=CommandCategory.MODEL,
                arguments=[CommandArgument(name="model", label="Modelo", required=True)],
                execution_mode=CommandExecutionMode.CHAT_ACTION,
            )
        ]
    )
    catalog = ListChatCommands(convs, runtime, FakeModelProfileLookup([]))

    decision = await ExecuteChatCommand(convs, msgs, runtime, catalog).execute(
        conversation_id=conv.id,
        user=user,
        command_name="/model",
        arguments={},
        confirmed=True,
        client_request_id="req-1",
    )

    assert decision.status is CommandExecutionStatus.FAILED
    assert "Modelo" in decision.message


async def test_ctx_and_cost_return_provider_usage_summary() -> None:
    user = User(id=uuid.uuid4(), email="u@test.com", hashed_password="x")
    conv = Conversation(id=uuid.uuid4(), user_id=user.id, title="Chat")
    convs = InMemoryConversationRepository()
    msgs = InMemoryMessageRepository()
    await convs.save(conv)
    await msgs.save(
        Message(
            id=uuid.uuid4(),
            conversation_id=conv.id,
            role="assistant",
            content="ok",
            prompt_tokens=10,
            completion_tokens=5,
            cost_usd=0.01,
        )
    )
    runtime = FakeChatCommandRuntime(
        [
            SlashCommand(
                name="/ctx",
                description="Contexto",
                category=CommandCategory.CONTEXT,
                execution_mode=CommandExecutionMode.CHAT_ACTION,
            )
        ]
    )
    catalog = ListChatCommands(convs, runtime, FakeModelProfileLookup([]))

    decision = await ExecuteChatCommand(convs, msgs, runtime, catalog).execute(
        conversation_id=conv.id,
        user=user,
        command_name="/ctx",
        arguments={},
        confirmed=False,
        client_request_id="req-ctx",
    )

    assert decision.status is CommandExecutionStatus.COMPLETED
    assert "10 tokens de entrada" in decision.message
    assert decision.event is not None
    assert decision.event.request_id == "req-ctx"


class StatusRuntime(FakeChatCommandRuntime):
    def __init__(self, command: SlashCommand, status: CommandExecutionStatus) -> None:
        super().__init__([command])
        self.status = status

    async def execute(
        self,
        *,
        conversation: Conversation,
        command: SlashCommand,
        arguments: object,
        client_request_id: str,
    ) -> CommandExecutionEvent:
        del conversation, arguments
        return CommandExecutionEvent(
            command_name=command.name,
            status=self.status,
            summary=f"status={self.status.value}",
            request_id=client_request_id,
        )


async def test_execute_preserves_runtime_result_statuses() -> None:
    for status in [
        CommandExecutionStatus.STARTED,
        CommandExecutionStatus.WAITING_FOR_INPUT,
        CommandExecutionStatus.COMPLETED,
        CommandExecutionStatus.CANCELLED,
    ]:
        user = User(id=uuid.uuid4(), email="u@test.com", hashed_password="x")
        conv = Conversation(id=uuid.uuid4(), user_id=user.id, title="Chat")
        convs = InMemoryConversationRepository()
        msgs = InMemoryMessageRepository()
        await convs.save(conv)
        command = SlashCommand(
            name="/doctor",
            description="Diagnostico",
            category=CommandCategory.DIAGNOSTIC,
            execution_mode=CommandExecutionMode.RUNTIME_COMMAND,
        )
        runtime = StatusRuntime(command, status)
        catalog = ListChatCommands(convs, runtime, FakeModelProfileLookup([]))

        decision = await ExecuteChatCommand(convs, msgs, runtime, catalog).execute(
            conversation_id=conv.id,
            user=user,
            command_name="/doctor",
            arguments={},
            confirmed=False,
            client_request_id=f"req-{status.value}",
        )

        assert decision.status is status
        assert decision.event is not None
        assert decision.event.status is status


async def test_execute_reports_unknown_command_as_unavailable() -> None:
    user = User(id=uuid.uuid4(), email="u@test.com", hashed_password="x")
    conv = Conversation(id=uuid.uuid4(), user_id=user.id, title="Chat")
    convs = InMemoryConversationRepository()
    msgs = InMemoryMessageRepository()
    await convs.save(conv)
    runtime = FakeChatCommandRuntime([])
    catalog = ListChatCommands(convs, runtime, FakeModelProfileLookup([]))

    decision = await ExecuteChatCommand(convs, msgs, runtime, catalog).execute(
        conversation_id=conv.id,
        user=user,
        command_name="/nope",
        arguments={},
        confirmed=False,
        client_request_id="req-nope",
    )

    assert decision.status is CommandExecutionStatus.UNAVAILABLE
    assert decision.event is not None
    assert decision.event.status is CommandExecutionStatus.UNAVAILABLE
