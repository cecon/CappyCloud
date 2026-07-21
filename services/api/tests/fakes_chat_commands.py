"""In-memory fakes for chat command ports."""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from app.domain.chat_commands import (
    CommandCatalog,
    CommandExecutionEvent,
    CommandExecutionStatus,
    SlashCommand,
)
from app.domain.entities import Conversation, Sandbox, UserRole
from app.ports.chat_commands import ChatCommandRuntimePort
from app.ports.model_profiles import AuthorizedModelProfile, ModelProfileLookupPort


class FakeChatCommandRuntime(ChatCommandRuntimePort):
    def __init__(self, commands: list[SlashCommand]) -> None:
        self.commands = commands
        self.executed: list[str] = []

    async def discover(self, conversation: Conversation, sandbox: Sandbox | None) -> CommandCatalog:
        del sandbox
        return CommandCatalog.now(
            conversation_id=conversation.id,
            runtime_version="v0.24.0",
            runtime_commit="2ff93a10bf88ab6d7030fc4ade5316a7424fa2f9",
            commands=self.commands,
        )

    async def execute(
        self,
        *,
        conversation: Conversation,
        command: SlashCommand,
        arguments: Mapping[str, object],
        client_request_id: str,
    ) -> CommandExecutionEvent:
        del conversation, arguments
        self.executed.append(command.name)
        return CommandExecutionEvent(
            command_name=command.name,
            status=CommandExecutionStatus.COMPLETED,
            summary="Comando concluido.",
            request_id=client_request_id,
        )


class FakeModelProfileLookup(ModelProfileLookupPort):
    def __init__(self, profiles: list[AuthorizedModelProfile]) -> None:
        self.profiles = profiles

    async def list_for_user(
        self, user_id: UUID, role: UserRole
    ) -> list[AuthorizedModelProfile]:
        del user_id, role
        return self.profiles
