"""Tests for chat command catalog use cases."""

import uuid

from app.application.use_cases.chat_commands import ListChatCommands
from app.domain.chat_commands import (
    CommandAvailability,
    CommandAvailabilityState,
    CommandCategory,
    CommandExecutionMode,
    SlashCommand,
)
from app.domain.entities import Conversation, User, UserRole
from app.ports.model_profiles import AuthorizedModelProfile

from tests.conftest import InMemoryConversationRepository
from tests.fakes_chat_commands import FakeChatCommandRuntime, FakeModelProfileLookup


async def test_list_chat_commands_returns_runtime_catalog() -> None:
    user = User(id=uuid.uuid4(), email="u@test.com", hashed_password="x")
    conversation = Conversation(id=uuid.uuid4(), user_id=user.id, title="Chat")
    convs = InMemoryConversationRepository()
    await convs.save(conversation)
    uc = ListChatCommands(
        convs,
        FakeChatCommandRuntime(
            [
                SlashCommand(
                    name="/ctx",
                    description="Ver contexto",
                    category=CommandCategory.CONTEXT,
                    execution_mode=CommandExecutionMode.CHAT_ACTION,
                )
            ]
        ),
        FakeModelProfileLookup(
            [
                AuthorizedModelProfile(
                    model_id="openrouter/free",
                    display_name="Free",
                    provider="OpenRouter",
                    active=True,
                    provider_active=True,
                    capabilities=["text"],
                    context_window=128000,
                )
            ]
        ),
    )

    catalog = await uc.execute(conversation.id, user)

    assert catalog.commands[0].name == "/ctx"
    assert catalog.runtime_commit == "2ff93a10bf88ab6d7030fc4ade5316a7424fa2f9"


async def test_non_admin_update_command_is_blocked() -> None:
    user = User(id=uuid.uuid4(), email="u@test.com", hashed_password="x", role=UserRole.USER)
    conversation = Conversation(id=uuid.uuid4(), user_id=user.id, title="Chat")
    convs = InMemoryConversationRepository()
    await convs.save(conversation)
    uc = ListChatCommands(
        convs,
        FakeChatCommandRuntime(
            [
                SlashCommand(
                    name="/update",
                    description="Atualizar",
                    category=CommandCategory.RUNTIME,
                    requires_confirmation=True,
                    confirmation_reason="Altera runtime.",
                    execution_mode=CommandExecutionMode.CHAT_ACTION,
                )
            ]
        ),
        FakeModelProfileLookup([]),
    )

    catalog = await uc.execute(conversation.id, user)

    assert catalog.commands[0].execution_mode is CommandExecutionMode.UNAVAILABLE
    assert catalog.commands[0].availability.reason == "Atualizacao de runtime exige administrador."


async def test_catalog_includes_all_v024_seed_commands_and_unavailable_states() -> None:
    user = User(id=uuid.uuid4(), email="u@test.com", hashed_password="x", role=UserRole.USER)
    conversation = Conversation(id=uuid.uuid4(), user_id=user.id, title="Chat")
    convs = InMemoryConversationRepository()
    await convs.save(conversation)
    runtime = FakeChatCommandRuntime(
        [
            SlashCommand(
                name="/model",
                description="Modelo",
                category=CommandCategory.MODEL,
                execution_mode=CommandExecutionMode.CHAT_ACTION,
            ),
            SlashCommand(
                name="/ctx",
                description="Contexto",
                category=CommandCategory.CONTEXT,
                execution_mode=CommandExecutionMode.CHAT_ACTION,
            ),
            SlashCommand(
                name="/cost",
                description="Custo",
                category=CommandCategory.COST,
                execution_mode=CommandExecutionMode.CHAT_ACTION,
            ),
            *[
                SlashCommand(
                    name=name,
                    description="Indisponivel no chat",
                    category=category,
                    availability=CommandAvailability(
                        CommandAvailabilityState.UNAVAILABLE,
                        reason="Sem caminho seguro no chat.",
                    ),
                    execution_mode=CommandExecutionMode.UNAVAILABLE,
                )
                for name, category in [
                    ("/doctor", CommandCategory.DIAGNOSTIC),
                    ("/bughunter", CommandCategory.ANALYSIS),
                    ("/bughunter-security", CommandCategory.ANALYSIS),
                    ("/bughunter-perf", CommandCategory.ANALYSIS),
                    ("/set-context-window", CommandCategory.CONTEXT),
                    ("/clear-context-window", CommandCategory.CONTEXT),
                    ("/goal", CommandCategory.SESSION),
                    ("/update", CommandCategory.RUNTIME),
                ]
            ],
        ]
    )
    uc = ListChatCommands(convs, runtime, FakeModelProfileLookup([]))

    catalog = await uc.execute(conversation.id, user)

    names = {command.name for command in catalog.commands}
    assert names == {
        "/model",
        "/ctx",
        "/cost",
        "/doctor",
        "/bughunter",
        "/bughunter-security",
        "/bughunter-perf",
        "/set-context-window",
        "/clear-context-window",
        "/goal",
        "/update",
    }
    unavailable = {
        command.name: command.availability.reason
        for command in catalog.commands
        if command.execution_mode is CommandExecutionMode.UNAVAILABLE
    }
    assert unavailable["/doctor"] == "Sem caminho seguro no chat."
    assert unavailable["/update"] == "Atualizacao de runtime exige administrador."
