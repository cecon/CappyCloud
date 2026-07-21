"""Use cases for chat slash command catalog discovery."""

from __future__ import annotations

import uuid

from app.domain.chat_commands import (
    CommandAvailability,
    CommandAvailabilityState,
    CommandCatalog,
    CommandExecutionMode,
    SlashCommand,
)
from app.domain.entities import Conversation, Sandbox, User, UserRole
from app.ports.chat_commands import ChatCommandRuntimePort
from app.ports.model_profiles import ModelProfileLookupPort
from app.ports.repositories import ConversationRepository, MessageRepository, SandboxRepository


class ListChatCommands:
    def __init__(
        self,
        conversations: ConversationRepository,
        runtime: ChatCommandRuntimePort,
        model_profiles: ModelProfileLookupPort,
        *,
        sandboxes: SandboxRepository | None = None,
    ) -> None:
        self._conversations = conversations
        self._runtime = runtime
        self._model_profiles = model_profiles
        self._sandboxes = sandboxes

    async def execute(self, conversation_id: uuid.UUID, user: User) -> CommandCatalog:
        conversation = await _get_conversation(self._conversations, conversation_id, user)
        sandbox = await _get_sandbox(self._sandboxes, conversation)
        catalog = await self._runtime.discover(conversation, sandbox)
        profiles = await self._model_profiles.list_for_user(user.id, user.role)
        return CommandCatalog(
            conversation_id=catalog.conversation_id,
            runtime_version=catalog.runtime_version,
            runtime_commit=catalog.runtime_commit,
            generated_at=catalog.generated_at,
            commands=[_apply_availability(cmd, profiles, user.role) for cmd in catalog.commands],
        )


def _apply_availability(command: SlashCommand, profiles: object, role: UserRole) -> SlashCommand:
    del profiles
    if command.name == "/update" and role is not UserRole.ADMIN:
        return _blocked(command, "Atualizacao de runtime exige administrador.")
    return command


def _blocked(command: SlashCommand, reason: str) -> SlashCommand:
    return SlashCommand(
        name=command.name,
        description=command.description,
        category=command.category,
        source=command.source,
        arguments=command.arguments,
        availability=CommandAvailability(CommandAvailabilityState.BLOCKED, reason=reason),
        requires_confirmation=command.requires_confirmation,
        confirmation_reason=command.confirmation_reason,
        execution_mode=CommandExecutionMode.UNAVAILABLE,
    )


async def _get_conversation(
    conversations: ConversationRepository, conversation_id: uuid.UUID, user: User
) -> Conversation:
    conversation = await conversations.get(conversation_id, user.id)
    if conversation is None:
        raise LookupError("Conversa nao encontrada.")
    return conversation


async def _get_sandbox(
    sandboxes: SandboxRepository | None, conversation: Conversation
) -> Sandbox | None:
    if sandboxes is None or conversation.sandbox_id is None:
        return None
    return await sandboxes.get(conversation.sandbox_id)


async def command_usage_summary(messages: MessageRepository, conversation_id: uuid.UUID) -> str:
    rows = await messages.list_by_conversation(conversation_id)
    prompt = sum(row.prompt_tokens for row in rows)
    completion = sum(row.completion_tokens for row in rows)
    cost = sum(float(row.cost_usd) for row in rows)
    return (
        f"Contexto usado na conversa: {prompt} tokens de entrada, "
        f"{completion} tokens de saida. Custo registrado: US$ {cost:.6f}."
    )
