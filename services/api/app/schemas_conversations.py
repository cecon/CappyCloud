"""Pydantic schemas for conversation HTTP contracts."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class RepoSelection(BaseModel):
    """Um repositório selecionado para participar da sessão."""

    slug: str = Field(min_length=1, max_length=128)
    alias: str | None = Field(default=None, max_length=128)
    base_branch: str | None = Field(default=None, max_length=255)


class ConversationCreate(BaseModel):
    """Criação de conversa — modelo multi-repo."""

    title: str | None = Field(default="Nova conversa", max_length=512)
    sandbox_id: uuid.UUID | None = None
    repos: list[RepoSelection] = Field(default_factory=list)


class ConversationOut(BaseModel):
    """Metadados da conversa."""

    id: uuid.UUID
    user_id: uuid.UUID | None = None
    user_email: str | None = None
    title: str
    created_at: datetime
    updated_at: datetime
    sandbox_id: uuid.UUID | None = None
    ai_model_id: uuid.UUID | None = None
    repos: list[dict] = Field(default_factory=list)
    session_root: str | None = None
    worktree_exists: bool = False
    lines_added: int = 0
    lines_removed: int = 0
    files_changed: int = 0
    pr_url: str | None = None
    pr_status: str = "none"
    pr_approved: bool = False
    ci_status: str = "unknown"
    ci_url: str | None = None

    model_config = {"from_attributes": True}


class PayloadSizeCategoryOut(BaseModel):
    key: str
    label: str
    size_bytes: int
    percentage: float = 0.0


class PayloadSizeBreakdownOut(BaseModel):
    total_size_bytes: int
    categories: list[PayloadSizeCategoryOut] = Field(default_factory=list)
    source: str = ""
    generated_at: str = ""


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    created_at: datetime
    model_used: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    payload_diagnostics: PayloadSizeBreakdownOut | None = None

    model_config = {"from_attributes": True}


class ConversationUsage(BaseModel):
    """Totais de uso agregados por conversa."""

    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_cost_usd: float = 0.0


class SendMessageBody(BaseModel):
    content: str = Field(min_length=1, max_length=1_000_000)
    model_id: str | None = Field(default=None, max_length=256)
    attachment_ids: list[uuid.UUID] | None = None
