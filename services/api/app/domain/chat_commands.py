"""Domain value objects for CappyCloud chat slash commands."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class CommandCategory(StrEnum):
    MODEL = "model"
    CONTEXT = "context"
    COST = "cost"
    DIAGNOSTIC = "diagnostic"
    ANALYSIS = "analysis"
    REPORT = "report"
    SESSION = "session"
    RUNTIME = "runtime"
    EXTERNAL = "external"
    OTHER = "other"


class CommandSource(StrEnum):
    UPSTREAM = "upstream"
    CAPPYCLOUD = "cappycloud"
    RUNTIME = "runtime"


class CommandAvailabilityState(StrEnum):
    AVAILABLE = "available"
    NEEDS_ARGUMENTS = "needs_arguments"
    NEEDS_CONFIRMATION = "needs_confirmation"
    BLOCKED = "blocked"
    UNAVAILABLE = "unavailable"


class CommandExecutionMode(StrEnum):
    CHAT_ACTION = "chat_action"
    RUNTIME_COMMAND = "runtime_command"
    UNAVAILABLE = "unavailable"


class CommandExecutionStatus(StrEnum):
    NEEDS_CONFIRMATION = "needs_confirmation"
    ACCEPTED = "accepted"
    STARTED = "started"
    WAITING_FOR_INPUT = "waiting_for_input"
    COMPLETED = "completed"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class CommandArgument:
    name: str
    label: str
    required: bool = False
    value_hint: str = ""
    allowed_values: list[str] = field(default_factory=list)
    sensitive: bool = False


@dataclass(frozen=True)
class CommandAvailability:
    state: CommandAvailabilityState
    reason: str | None = None
    required_role: str | None = None
    required_capability: str | None = None


@dataclass(frozen=True)
class SlashCommand:
    name: str
    description: str
    category: CommandCategory
    source: CommandSource = CommandSource.UPSTREAM
    arguments: list[CommandArgument] = field(default_factory=list)
    availability: CommandAvailability = field(
        default_factory=lambda: CommandAvailability(CommandAvailabilityState.AVAILABLE)
    )
    requires_confirmation: bool = False
    confirmation_reason: str | None = None
    execution_mode: CommandExecutionMode = CommandExecutionMode.UNAVAILABLE

    def __post_init__(self) -> None:
        if not self.name.startswith("/"):
            raise ValueError("Slash command names must start with '/'.")
        if self.execution_mode is CommandExecutionMode.UNAVAILABLE and not self.availability.reason:
            raise ValueError("Unavailable commands must include an unavailable reason.")
        if self.requires_confirmation and not self.confirmation_reason:
            raise ValueError("Commands requiring confirmation must include a reason.")


@dataclass(frozen=True)
class CommandCatalog:
    conversation_id: uuid.UUID
    runtime_version: str
    runtime_commit: str
    generated_at: datetime
    commands: list[SlashCommand]

    @classmethod
    def now(
        cls,
        *,
        conversation_id: uuid.UUID,
        runtime_version: str,
        runtime_commit: str,
        commands: list[SlashCommand],
    ) -> "CommandCatalog":
        return cls(
            conversation_id=conversation_id,
            runtime_version=runtime_version,
            runtime_commit=runtime_commit,
            generated_at=datetime.now(UTC),
            commands=commands,
        )


@dataclass(frozen=True)
class CommandExecutionEvent:
    command_name: str
    status: CommandExecutionStatus
    summary: str
    details_markdown: str | None = None
    request_id: str | None = None
    result_artifacts: list[dict[str, object]] = field(default_factory=list)


@dataclass(frozen=True)
class CommandExecutionDecision:
    status: CommandExecutionStatus
    message: str
    event: CommandExecutionEvent | None = None
    confirmation: dict[str, str] | None = None
    client_request_id: str | None = None

