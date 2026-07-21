"""Use cases for safe chat slash command execution."""

from __future__ import annotations

import uuid
from collections.abc import Mapping

from app.application.use_cases.chat_command_sanitization import sanitize_command_text
from app.application.use_cases.chat_commands import ListChatCommands, command_usage_summary
from app.domain.chat_commands import (
    CommandExecutionDecision,
    CommandExecutionEvent,
    CommandExecutionMode,
    CommandExecutionStatus,
)
from app.domain.entities import User
from app.ports.chat_commands import ChatCommandRuntimePort
from app.ports.repositories import ConversationRepository, MessageRepository


class ExecuteChatCommand:
    def __init__(
        self,
        conversations: ConversationRepository,
        messages: MessageRepository,
        runtime: ChatCommandRuntimePort,
        catalog: ListChatCommands,
    ) -> None:
        self._conversations = conversations
        self._messages = messages
        self._runtime = runtime
        self._catalog = catalog

    async def execute(
        self,
        *,
        conversation_id: uuid.UUID,
        user: User,
        command_name: str,
        arguments: Mapping[str, object],
        confirmed: bool,
        client_request_id: str,
    ) -> CommandExecutionDecision:
        conversation = await self._conversations.get(conversation_id, user.id)
        if conversation is None:
            raise LookupError("Conversa nao encontrada.")
        catalog = await self._catalog.execute(conversation_id, user)
        command = next((item for item in catalog.commands if item.name == command_name), None)
        if command is None:
            return _unavailable(command_name, "Comando nao encontrado no catalogo desta conversa.")
        if command.execution_mode is CommandExecutionMode.UNAVAILABLE:
            return _unavailable(
                command.name,
                command.availability.reason or "Comando indisponivel.",
            )
        missing = [
            arg.label for arg in command.arguments if arg.required and arg.name not in arguments
        ]
        if missing:
            return CommandExecutionDecision(
                status=CommandExecutionStatus.FAILED,
                message="Informe os argumentos obrigatorios: " + ", ".join(missing) + ".",
            )
        if command.requires_confirmation and not confirmed:
            reason = command.confirmation_reason or "Este comando precisa de confirmacao."
            return CommandExecutionDecision(
                status=CommandExecutionStatus.NEEDS_CONFIRMATION,
                message=reason,
                confirmation={
                    "message": reason,
                    "confirm_label": "Executar",
                    "cancel_label": "Cancelar",
                },
            )
        if command.name in {"/ctx", "/cost"}:
            summary = await command_usage_summary(self._messages, conversation_id)
            return CommandExecutionDecision(
                status=CommandExecutionStatus.COMPLETED,
                message=summary,
                event=CommandExecutionEvent(
                    command_name=command.name,
                    status=CommandExecutionStatus.COMPLETED,
                    summary=sanitize_command_text(summary),
                    request_id=client_request_id,
                ),
                client_request_id=client_request_id,
            )
        event = await self._runtime.execute(
            conversation=conversation,
            command=command,
            arguments=arguments,
            client_request_id=client_request_id,
        )
        return CommandExecutionDecision(
            status=event.status,
            message=event.summary,
            event=event,
            client_request_id=client_request_id,
        )


def _unavailable(command_name: str, message: str) -> CommandExecutionDecision:
    return CommandExecutionDecision(
        status=CommandExecutionStatus.UNAVAILABLE,
        message=message,
        event=CommandExecutionEvent(
            command_name=command_name,
            status=CommandExecutionStatus.UNAVAILABLE,
            summary=message,
        ),
    )
