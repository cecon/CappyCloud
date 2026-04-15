"""Domain entities — pure Python dataclasses with no ORM or framework imports."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Optional


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass
class User:
    """Utilizador registado na plataforma."""

    id: uuid.UUID
    email: str
    hashed_password: str
    created_at: datetime = field(default_factory=_utcnow)


@dataclass
class RepoEnvironment:
    """Ambiente global (repositório git) partilhado por todos os utilizadores."""

    id: uuid.UUID
    slug: str
    name: str
    repo_url: str
    branch: str = "main"
    created_at: datetime = field(default_factory=_utcnow)


@dataclass
class Conversation:
    """Thread de conversa pertencente a um utilizador."""

    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
    environment_id: Optional[uuid.UUID] = None
    env_slug: Optional[str] = None
    base_branch: Optional[str] = None


@dataclass
class Message:
    """Mensagem persistida numa conversa."""

    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str  # "user" | "assistant" | "system"
    content: str
    created_at: datetime = field(default_factory=_utcnow)
