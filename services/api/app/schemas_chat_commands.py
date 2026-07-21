"""Pydantic schemas for chat slash command endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class CommandArgumentOut(BaseModel):
    name: str
    label: str
    required: bool = False
    value_hint: str = ""
    allowed_values: list[str] = Field(default_factory=list)
    sensitive: bool = False


class CommandAvailabilityOut(BaseModel):
    state: str
    reason: str | None = None
    required_role: str | None = None
    required_capability: str | None = None


class SlashCommandOut(BaseModel):
    name: str
    description: str
    source: str
    category: str
    arguments: list[CommandArgumentOut]
    availability: CommandAvailabilityOut
    requires_confirmation: bool
    confirmation_reason: str | None = None
    execution_mode: str


class CommandCatalogOut(BaseModel):
    runtime_version: str
    runtime_commit: str
    generated_at: datetime
    commands: list[SlashCommandOut]


class CommandExecuteIn(BaseModel):
    command: str = Field(min_length=1, max_length=128)
    arguments: dict[str, Any] = Field(default_factory=dict)
    confirmed: bool = False
    client_request_id: str = Field(min_length=1, max_length=128)


class CommandConfirmationOut(BaseModel):
    message: str
    confirm_label: str = "Executar"
    cancel_label: str = "Cancelar"


class CommandStreamOut(BaseModel):
    conversation_id: str
    client_request_id: str


class CommandExecuteOut(BaseModel):
    status: Literal[
        "needs_confirmation",
        "accepted",
        "started",
        "waiting_for_input",
        "completed",
        "unavailable",
        "failed",
        "cancelled",
    ]
    message: str | None = None
    confirmation: CommandConfirmationOut | None = None
    stream: CommandStreamOut | None = None
