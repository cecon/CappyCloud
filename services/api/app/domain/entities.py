"""Domain entities — pure Python dataclasses, no ORM or framework imports."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from app.domain.value_objects import DEFAULT_PERMISSION_MODE


def _utcnow() -> datetime:
    return datetime.now(UTC)


class UserRole(StrEnum):
    ADMIN = "admin"
    USER = "user"


class SandboxRuntime(StrEnum):
    COMPOSE = "compose"
    SWARM = "swarm"


class ModelTier(StrEnum):
    FREE = "free"
    PAID = "paid"
    UNKNOWN = "unknown"


class ContainerStatus(StrEnum):
    NOT_CREATED = "not_created"
    STARTING = "starting"
    RUNNING = "running"
    CONFIGURING = "configuring"
    CONFIGURED = "configured"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class User:
    id: uuid.UUID
    email: str
    hashed_password: str
    role: UserRole = UserRole.USER
    is_super_admin: bool = False
    must_change_password: bool = False
    created_at: datetime = field(default_factory=_utcnow)

    @property
    def is_admin(self) -> bool:
        return self.role is UserRole.ADMIN


@dataclass
class UserPreferences:
    user_id: uuid.UUID
    default_permission_mode: str = DEFAULT_PERMISSION_MODE


@dataclass
class UserRepositoryWorkspace:
    id: uuid.UUID
    user_id: uuid.UUID
    repository_id: uuid.UUID
    sandbox_id: uuid.UUID | None
    sandbox_key: str
    base_branch: str
    workspace_path: str
    status: str
    health_message: str = ""
    last_prepared_at: datetime | None = None
    last_used_at: datetime | None = None
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)


@dataclass
class Sandbox:
    id: uuid.UUID
    name: str
    host: str
    grpc_port: int = 50051
    session_port: int = 8080
    status: str = "active"  # active | draining | offline (lógico)
    runtime: SandboxRuntime = SandboxRuntime.COMPOSE
    image: str = ""
    env_vars: dict[str, str] = field(default_factory=dict)
    container_status: ContainerStatus = ContainerStatus.NOT_CREATED
    register_token: str | None = None
    claude_md: str = ""
    created_at: datetime = field(default_factory=_utcnow)


@dataclass
class GitProvider:
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
    id: uuid.UUID
    name: str
    base_url: str = "https://openrouter.ai/api/v1"
    api_key_encrypted: str = ""
    active: bool = True
    last_synced_at: datetime | None = None
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)


@dataclass
class AiModel:
    id: uuid.UUID
    provider_id: uuid.UUID
    model_id: str
    display_name: str
    capabilities: list[str] = field(default_factory=lambda: ["text"])
    is_default: dict = field(default_factory=dict)
    context_window: int = 200000
    input_cost_per_1m_usd: float | None = None
    output_cost_per_1m_usd: float | None = None
    tier: ModelTier = field(default_factory=lambda: ModelTier.UNKNOWN)
    active: bool = True
    created_at: datetime = field(default_factory=_utcnow)


@dataclass
class UserSandboxAccess:
    id: uuid.UUID
    user_id: uuid.UUID
    sandbox_id: uuid.UUID
    created_at: datetime = field(default_factory=_utcnow)


@dataclass
class UserRepositoryAccess:
    id: uuid.UUID
    user_id: uuid.UUID
    repository_id: uuid.UUID
    created_at: datetime = field(default_factory=_utcnow)


@dataclass
class UserAiModelAccess:
    id: uuid.UUID
    user_id: uuid.UUID
    ai_model_id: uuid.UUID
    created_at: datetime = field(default_factory=_utcnow)


@dataclass
class Repository:
    id: uuid.UUID
    slug: str
    name: str
    clone_url: str
    default_branch: str = "main"
    confluence_url: str = ""
    confluence_space: str = ""
    confluence_labels: list[str] = field(default_factory=list)
    provider_id: uuid.UUID | None = None
    sandbox_id: uuid.UUID | None = None
    sandbox_status: str = "not_cloned"
    sandbox_path: str = ""
    last_sync_at: datetime | None = None
    error_message: str | None = None
    signoz_service_name: str | None = None
    active: bool = True
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)


@dataclass
class SandboxSyncItem:
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
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
    sandbox_id: uuid.UUID | None = None
    ai_model_id: uuid.UUID | None = None
    repos: list[dict] = field(default_factory=list)
    session_root: str | None = None
    permission_mode: str = DEFAULT_PERMISSION_MODE
    worktree_exists: bool = False
    lines_added: int = 0
    lines_removed: int = 0
    files_changed: int = 0
    pr_url: str | None = None
    pr_status: str = "none"  # none | open | draft | merged | closed
    pr_approved: bool = False
    pr_number: int | None = None
    github_repo_slug: str | None = None
    ci_status: str = "unknown"  # unknown | pending | running | passed | failed
    ci_url: str | None = None
    user_email: str | None = None


@dataclass
class PayloadSizeCategory:
    key: str
    label: str
    size_bytes: int
    percentage: float = 0.0


@dataclass
class PayloadSizeBreakdown:
    total_size_bytes: int
    categories: list[PayloadSizeCategory] = field(default_factory=list)
    source: str = ""
    generated_at: str = ""


@dataclass
class Message:
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    created_at: datetime = field(default_factory=_utcnow)
    model_used: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    payload_diagnostics: dict[str, object] | None = None


@dataclass
class MessageAttachment:
    id: uuid.UUID
    conversation_id: uuid.UUID
    mime_type: str
    storage_path: str
    original_filename: str
    size_bytes: int = 0
    kind: str = "image"
    processing_status: str = "uploaded"
    chunks_count: int = 0
    processing_error: str | None = None
    message_id: uuid.UUID | None = None
    vision_description: str | None = None
    vision_model_used: str | None = None
    uploaded_by: uuid.UUID | None = None
    uploaded_at: datetime = field(default_factory=_utcnow)


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


@dataclass
class SandboxSkill:
    id: uuid.UUID
    sandbox_id: uuid.UUID
    name: str  # slug; vira o nome da pasta em ~/.claude/skills/
    description: str = ""
    content: str = ""  # markdown que vira o corpo do SKILL.md
    enabled: bool = True
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)


@dataclass
class SandboxAgent:
    id: uuid.UUID
    sandbox_id: uuid.UUID
    name: str  # slug; vira o nome do arquivo <name>.md
    description: str = ""
    system_prompt: str = ""
    model: str = ""  # ex: "claude-opus-4-7" — opcional, vai como frontmatter
    tools: list[str] = field(default_factory=list)
    enabled: bool = True
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)


@dataclass
class McpServer:
    id: uuid.UUID
    sandbox_id: uuid.UUID
    name: str  # chave única por sandbox (ex: "github", "filesystem")
    command: str  # ex: "npx", "uvx", "python"
    args: list[str] = field(default_factory=list)  # ex: ["-y", "@mcp/server-github"]
    env: dict = field(default_factory=dict)  # ex: {"GITHUB_TOKEN": "..."}
    enabled: bool = True
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)


@dataclass
class UserMcpServer:
    id: uuid.UUID
    user_id: uuid.UUID
    repository_id: uuid.UUID
    name: str
    token_hash: str
    token_preview: str
    enabled: bool = True
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
    last_used_at: datetime | None = None
