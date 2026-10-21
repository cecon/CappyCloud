"""Entidades de catálogo e anexos (reexportadas por ``app.domain.entities``)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass
class ConversationArtifactChunk:
    id: uuid.UUID
    attachment_id: uuid.UUID
    conversation_id: uuid.UUID
    chunk_index: int
    content: str
    line_start: int | None = None
    line_end: int | None = None
    page_start: int | None = None
    page_end: int | None = None
    meta: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utcnow)


@dataclass
class GlobalSkill:
    id: uuid.UUID
    name: str
    description: str = ""
    content: str = ""
    enabled: bool = True
    sandbox_ids: list[uuid.UUID] = field(default_factory=list)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
