"""Ports for chat slash command discovery and execution."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from collections.abc import Mapping

from app.domain.chat_commands import CommandCatalog, CommandExecutionEvent, SlashCommand
from app.domain.entities import Conversation, Sandbox


class ChatCommandRuntimePort(ABC):
    """Runtime adapter for upstream slash command metadata and safe commands."""

    @abstractmethod
    async def discover(self, conversation: Conversation, sandbox: Sandbox | None) -> CommandCatalog:
        """Return command catalog metadata for the active runtime."""

    @abstractmethod
    async def execute(
        self,
        *,
        conversation: Conversation,
        command: SlashCommand,
        arguments: Mapping[str, object],
        client_request_id: str,
    ) -> CommandExecutionEvent:
        """Execute a safe runtime command and return a sanitized timeline event."""


class ChatCommandRuntimeError(Exception):
    """Raised when command runtime discovery or execution fails."""

    def __init__(self, message: str, *, conversation_id: uuid.UUID | None = None) -> None:
        super().__init__(message)
        self.conversation_id = conversation_id

