"""Domain entities — pure Python dataclasses, no ORM or framework imports."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass
class User:
    id: uuid.UUID
    email: str
    hashed_password: str
    created_at: datetime = field(default_factory=_utcnow)


# ── Platform control plane ────────────────────────────────────


@dataclass
class Sandbox:
    """Container sandbox hospedando openclaude gRPC + session_server HTTP."""

    id: uuid.UUID
    name: str
    host: str
    grpc_port: int = 50051
    session_port: int = 8080
    status: str = "active"  # active | draining | offline
    created_at: datetime = field(default_factory=_utcnow)


@dataclass
class GitProvider:
    """Provedor de repositórios git com credenciais criptografadas."""

    id: uuid.UUID
    name: str
    provider_type: str  # github | azure_devops | gitlab | bitbucket
    base_url: str = ""
    org_or_project: str = ""
    token_encrypted: str = ""
    active: bool = True
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)


@dataclass
class AiProvider:
    """Provedor de modelos IA (OpenRouter, Anthropic, OpenAI…)."""

    id: uuid.UUID
    name: str
    base_url: str = "https://openrouter.ai/api/v1"
    api_key_encrypted: str = ""
    active: bool = True
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)


@dataclass
class AiModel:
    """Modelo IA com capabilities e flags de default por capability.

    capabilities: ['text', 'vision', 'embedding', 'video']
    is_default:   {'text': True, 'vision': False, ...}
    """

    id: uuid.UUID
    provider_id: uuid.UUID
    model_id: str
    display_name: str
    capabilities: list[str] = field(default_factory=lambda: ["text"])
    is_default: dict = field(default_factory=dict)
    context_window: int = 200000
    active: bool = True
    created_at: datetime = field(default_factory=_utcnow)


@dataclass
class Repository:
    """Repositório git com estado de sincronização no sandbox.

    sandbox_status: not_cloned | cloning | cloned | error
    """

    id: uuid.UUID
    slug: str
    name: str
    clone_url: str
    default_branch: str = "main"
    provider_id: uuid.UUID | None = None
    sandbox_id: uuid.UUID | None = None
    sandbox_status: str = "not_cloned"
    sandbox_path: str = ""
    last_sync_at: datetime | None = None
    error_message: str | None = None
    active: bool = True
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)


@dataclass
class SandboxSyncItem:
    """Item na fila de sincronização DB → sandbox VM.

    operation: clone_repo | remove_repo | update_git_auth | reconfigure_model
    status:    pending | processing | done | error
    """

    id: uuid.UUID
    sandbox_id: uuid.UUID
    operation: str
    payload: dict = field(default_factory=dict)
    priority: int = 5
    status: str = "pending"
    retries: int = 0
    last_error: str | None = None
    created_at: datetime = field(default_factory=_utcnow)
    processed_at: datetime | None = None


# ── Conversations ─────────────────────────────────────────────


@dataclass
class RepoEnvironment:
    id: uuid.UUID
    slug: str
    name: str
    repo_url: str
    branch: str = "main"
    created_at: datetime = field(default_factory=_utcnow)


@dataclass
class Conversation:
    """Thread de conversa com rastreamento completo de sessão, PR e CI."""

    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
    # Infra
    sandbox_id: uuid.UUID | None = None
    ai_model_id: uuid.UUID | None = None
    # Multi-repo session
    repos: list[dict] = field(default_factory=list)
    session_root: str | None = None
    # Worktree state
    worktree_exists: bool = False
    lines_added: int = 0
    lines_removed: int = 0
    files_changed: int = 0
    # PR tracking
    pr_url: str | None = None
    pr_status: str = "none"  # none | open | draft | merged | closed
    pr_approved: bool = False
    pr_number: int | None = None
    github_repo_slug: str | None = None
    # CI tracking
    ci_status: str = "unknown"  # unknown | pending | running | passed | failed
    ci_url: str | None = None


@dataclass
class Message:
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    created_at: datetime = field(default_factory=_utcnow)
