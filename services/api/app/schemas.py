"""Esquemas Pydantic para pedidos e respostas HTTP da API."""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.domain.value_objects import validate_email, validate_password

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{1,62}[a-z0-9]$")


class UserCreate(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=128)

    @field_validator("email")
    @classmethod
    def email_normalizado(cls, v: object) -> str:
        return validate_email(str(v))

    @field_validator("password")
    @classmethod
    def password_min_len(cls, v: str) -> str:
        return validate_password(v)


class UserOut(BaseModel):
    id: uuid.UUID
    email: str

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RepoEnvCreate(BaseModel):
    slug: str = Field(min_length=3, max_length=64)
    name: str = Field(min_length=1, max_length=256)
    repo_url: str = Field(min_length=1, max_length=2048)
    branch: str = Field(default="main", min_length=1, max_length=256)

    @field_validator("slug")
    @classmethod
    def slug_valido(cls, v: str) -> str:
        if not _SLUG_RE.match(v):
            raise ValueError(
                "Slug inválido. Use apenas minúsculas, números e hífens "
                "(ex.: meu-projeto). Deve começar e terminar em letra/número."
            )
        return v


class RepoEnvOut(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    repo_url: str
    branch: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Sandboxes ─────────────────────────────────────────────────


class SandboxOut(BaseModel):
    """Dados públicos de uma instância sandbox."""

    id: uuid.UUID
    name: str
    host: str
    grpc_port: int
    session_port: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Conversations ─────────────────────────────────────────────


class RepoSelection(BaseModel):
    """Um repositório selecionado para participar da sessão.

    slug        — slug do repo em WORKSPACE_REPOS (ex.: 'cappycloud')
    alias       — nome do subdiretório em session_root (ex.: 'cappycloud-main').
                  Se omitido, usa o slug.
    base_branch — branch de origem do worktree (ex.: 'main', 'feat/xyz').
                  Se omitido, usa o default do repo.
    """

    slug: str = Field(min_length=1, max_length=128)
    alias: str | None = Field(default=None, max_length=128)
    base_branch: str | None = Field(default=None, max_length=255)


class ConversationCreate(BaseModel):
    """Criação de conversa — modelo multi-repo."""

    title: str | None = Field(default="Nova conversa", max_length=512)
    sandbox_id: uuid.UUID | None = None
    repos: list[RepoSelection] = Field(default_factory=list)
    agent_id: uuid.UUID | None = None


class ConversationOut(BaseModel):
    """Metadados da conversa."""

    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime
    sandbox_id: uuid.UUID | None = None
    ai_model_id: uuid.UUID | None = None
    agent_id: uuid.UUID | None = None
    repos: list[dict] = Field(default_factory=list)
    session_root: str | None = None
    # Worktree state
    worktree_exists: bool = False
    lines_added: int = 0
    lines_removed: int = 0
    files_changed: int = 0
    # PR tracking
    pr_url: str | None = None
    pr_status: str = "none"
    pr_approved: bool = False
    # CI tracking
    ci_status: str = "unknown"
    ci_url: str | None = None

    model_config = {"from_attributes": True}


# ── Platform control plane schemas ────────────────────────────


class GitProviderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    provider_type: str = Field(default="github", max_length=32)
    base_url: str = Field(default="", max_length=2048)
    org_or_project: str = Field(default="", max_length=512)
    token: str = Field(default="", description="PAT em texto plano — será criptografado")


class GitProviderOut(BaseModel):
    id: uuid.UUID
    name: str
    provider_type: str
    base_url: str
    org_or_project: str
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AiProviderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    base_url: str = Field(default="https://openrouter.ai/api/v1", max_length=2048)
    api_key: str = Field(default="", description="API key em texto plano — será criptografada")


class AiProviderOut(BaseModel):
    id: uuid.UUID
    name: str
    base_url: str
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AiModelCreate(BaseModel):
    provider_id: uuid.UUID
    model_id: str = Field(min_length=1, max_length=256)
    display_name: str = Field(min_length=1, max_length=256)
    capabilities: list[str] = Field(default_factory=lambda: ["text"])
    is_default: dict = Field(default_factory=dict)
    context_window: int = Field(default=200000, ge=1)


class AiModelOut(BaseModel):
    id: uuid.UUID
    provider_id: uuid.UUID
    model_id: str
    display_name: str
    capabilities: list[str]
    is_default: dict
    context_window: int
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class RepositoryCreate(BaseModel):
    slug: str = Field(min_length=2, max_length=128)
    name: str = Field(min_length=1, max_length=256)
    clone_url: str = Field(min_length=1, max_length=2048)
    default_branch: str = Field(default="main", max_length=256)
    provider_id: uuid.UUID | None = None
    sandbox_id: uuid.UUID | None = None
    # Inline PAT: se preenchido, cria/atualiza um provider implícito e associa.
    pat_token: str | None = Field(default=None, max_length=4096)
    provider_type: str | None = Field(default=None, max_length=32)


class RepositoryOut(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    clone_url: str
    default_branch: str
    provider_id: uuid.UUID | None = None
    sandbox_id: uuid.UUID | None = None
    sandbox_status: str
    sandbox_path: str
    last_sync_at: datetime | None = None
    error_message: str | None = None
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SendMessageBody(BaseModel):
    content: str = Field(min_length=1, max_length=1_000_000)
    model_id: str | None = Field(
        default=None,
        max_length=256,
        description="OpenRouter model ID (ex: anthropic/claude-3.5-sonnet). Se None, usa o default da env var.",
    )


# ── Re-export schemas de Agents & Skills (definidos em ``schemas_agents``) ──
from app.schemas_agents import (  # noqa: E402, F401
    AgentCreate,
    AgentOut,
    AgentUpdate,
    SkillCreate,
    SkillImportFromUrlBody,
    SkillOut,
    SkillSearchResult,
    SkillUpdate,
)
