"""Sandbox-backed chat command adapter."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from app.application.use_cases.chat_command_sanitization import sanitize_command_text
from app.domain.chat_commands import (
    CommandAvailability,
    CommandAvailabilityState,
    CommandCatalog,
    CommandCategory,
    CommandExecutionEvent,
    CommandExecutionMode,
    CommandExecutionStatus,
    CommandSource,
    SlashCommand,
)
from app.domain.entities import Conversation, Sandbox
from app.ports.chat_commands import ChatCommandRuntimePort

RUNTIME_VERSION = "v0.24.0"
RUNTIME_COMMIT = "2ff93a10bf88ab6d7030fc4ade5316a7424fa2f9"
_CATALOG_PATH = Path(__file__).resolve().parents[5] / "sandbox" / "openclaude-v024-commands.json"


class SandboxChatCommandRuntime(ChatCommandRuntimePort):
    """Discovers commands from the checked-in v0.24 seed until runtime metadata exists."""

    async def discover(self, conversation: Conversation, sandbox: Sandbox | None) -> CommandCatalog:
        del sandbox
        return CommandCatalog.now(
            conversation_id=conversation.id,
            runtime_version=RUNTIME_VERSION,
            runtime_commit=RUNTIME_COMMIT,
            commands=_load_seed_commands(),
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
        if command.execution_mode is CommandExecutionMode.UNAVAILABLE:
            return CommandExecutionEvent(
                command_name=command.name,
                status=CommandExecutionStatus.UNAVAILABLE,
                summary=command.availability.reason
                or "Este comando nao possui execucao segura no chat.",
                request_id=client_request_id,
            )
        return CommandExecutionEvent(
            command_name=command.name,
            status=CommandExecutionStatus.COMPLETED,
            summary=sanitize_command_text(f"Comando {command.name} processado."),
            request_id=client_request_id,
        )


def _load_seed_commands() -> list[SlashCommand]:
    raw = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    commands: list[SlashCommand] = []
    for item in raw:
        availability = item.get("availability") or {}
        commands.append(
            SlashCommand(
                name=str(item["name"]),
                description=str(item["description"]),
                category=CommandCategory(str(item.get("category") or "other")),
                source=CommandSource(str(item.get("source") or "upstream")),
                availability=CommandAvailability(
                    state=CommandAvailabilityState(str(availability.get("state") or "available")),
                    reason=availability.get("reason"),
                    required_role=availability.get("required_role"),
                    required_capability=availability.get("required_capability"),
                ),
                requires_confirmation=bool(item.get("requires_confirmation")),
                confirmation_reason=item.get("confirmation_reason"),
                execution_mode=CommandExecutionMode(str(item.get("execution_mode") or "unavailable")),
            )
        )
    return commands

