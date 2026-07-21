"""Contract tests for ChatCommandRuntimePort implementations."""

import uuid

from app.domain.chat_commands import (
    CommandAvailability,
    CommandAvailabilityState,
    CommandCategory,
    CommandExecutionMode,
    SlashCommand,
)
from app.domain.entities import Conversation
from tests.fakes_chat_commands import FakeChatCommandRuntime


async def test_runtime_port_discovers_catalog_for_conversation() -> None:
    conversation = Conversation(id=uuid.uuid4(), user_id=uuid.uuid4(), title="Chat")
    runtime = FakeChatCommandRuntime(
        [
            SlashCommand(
                name="/ctx",
                description="Ver contexto",
                category=CommandCategory.CONTEXT,
                execution_mode=CommandExecutionMode.CHAT_ACTION,
            ),
            SlashCommand(
                name="/doctor",
                description="Diagnostico",
                category=CommandCategory.DIAGNOSTIC,
                availability=CommandAvailability(
                    CommandAvailabilityState.UNAVAILABLE,
                    reason="Sem execucao segura.",
                ),
                execution_mode=CommandExecutionMode.UNAVAILABLE,
            ),
        ]
    )

    catalog = await runtime.discover(conversation, None)

    assert catalog.conversation_id == conversation.id
    assert [command.name for command in catalog.commands] == ["/ctx", "/doctor"]
    assert catalog.commands[1].availability.reason == "Sem execucao segura."


async def test_runtime_port_executes_safe_command_event() -> None:
    conversation = Conversation(id=uuid.uuid4(), user_id=uuid.uuid4(), title="Chat")
    command = SlashCommand(
        name="/ctx",
        description="Ver contexto",
        category=CommandCategory.CONTEXT,
        execution_mode=CommandExecutionMode.CHAT_ACTION,
    )
    runtime = FakeChatCommandRuntime([command])

    event = await runtime.execute(
        conversation=conversation,
        command=command,
        arguments={},
        client_request_id="req-1",
    )

    assert event.command_name == "/ctx"
    assert event.request_id == "req-1"
    assert runtime.executed == ["/ctx"]
