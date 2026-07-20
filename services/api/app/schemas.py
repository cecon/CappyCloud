"""Esquemas Pydantic para pedidos e respostas HTTP da API."""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.domain.entities import ContainerStatus, SandboxRuntime, UserRole
from app.domain.value_objects import validate_email, validate_password, validate_permission_mode

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{1,62}[a-z0-9]$")


class UserCreate(BaseModel):
    """Payload de criação de utilizador (uso administrativo).

    O campo ``role`` é opcional; quando omitido, o novo utilizador é criado
    como :attr:`UserRole.USER`. Apenas ADMINs podem chamar endpoints que
    aceitam este body (ADR-005).
    """

    email: str = Field(max_length=320)
    password: str = Field(max_length=128)
    role: UserRole = UserRole.USER
    must_change_password: bool = True

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
    role: UserRole
    is_super_admin: bool = False
    must_change_password: bool = False

    model_config = {"from_attributes": True}


class UserPreferencesOut(BaseModel):
    default_permission_mode: str


class UserPreferencesUpdate(BaseModel):
    default_permission_mode: str | None = Field(default=None, max_length=32)

    @field_validator("default_permission_mode")
    @classmethod
    def default_permission_mode_valid(cls, v: str | None) -> str | None:
        return validate_permission_mode(v) if v is not None else None


class PasswordChangeBody(BaseModel):
    """Payload para troca de senha do próprio utilizador autenticado."""

    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(max_length=128)

    @field_validator("new_password")
    @classmethod
    def new_password_min_len(cls, v: str) -> str:
        return validate_password(v)


class UserRoleUpdate(BaseModel):
    """Payload para alterar o papel de um utilizador (ADR-005)."""

    role: UserRole


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
    runtime: SandboxRuntime
    image: str
    env_vars: dict[str, str]
    container_status: ContainerStatus
    active_sessions: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class SandboxAdminOut(SandboxOut):
    claude_md: str = ""


class SandboxRegister(BaseModel):
    """Payload de auto-registro enviado pelo container ao iniciar."""

    name: str = Field(min_length=1, max_length=128)
    host: str = Field(min_length=1, max_length=256)
    grpc_port: int = Field(default=50051, ge=1, le=65535)
    session_port: int = Field(default=8080, ge=1, le=65535)
    register_token: str = Field(min_length=1, max_length=256)


class SandboxAdminCreate(BaseModel):
    """Payload para cadastro administrativo de sandbox (ADR-004)."""

    name: str = Field(min_length=1, max_length=128)
    runtime: SandboxRuntime = SandboxRuntime.COMPOSE
    image: str = Field(default="", max_length=512)
    claude_md: str = Field(default="", max_length=20000)
    env_vars: dict[str, str] = Field(default_factory=dict)
    host: str | None = Field(default=None, max_length=256)
    grpc_port: int = Field(default=50051, ge=1, le=65535)
    session_port: int = Field(default=8080, ge=1, le=65535)


class SandboxAdminUpdate(BaseModel):
    """Patch de campos editáveis. ``name`` é imutável após criação."""

    image: str | None = Field(default=None, max_length=512)
    claude_md: str | None = Field(default=None, max_length=20000)
    env_vars: dict[str, str] | None = None
    host: str | None = Field(default=None, max_length=256)
    grpc_port: int | None = Field(default=None, ge=1, le=65535)
    session_port: int | None = Field(default=None, ge=1, le=65535)
    status: str | None = Field(default=None, max_length=32)


class SandboxCloneBody(BaseModel):
    new_name: str = Field(min_length=1, max_length=128)


from app.schemas_agents import (  # noqa: E402, F401
    SkillCreate,
    SkillImportFromUrlBody,
    SkillOut,
    SkillSearchResult,
    SkillUpdate,
)
from app.schemas_attachments import AttachmentOut  # noqa: E402, F401
from app.schemas_conversations import (  # noqa: E402, F401
    ConversationCreate,
    ConversationOut,
    ConversationUsage,
    MessageOut,
    PayloadSizeBreakdownOut,
    PayloadSizeCategoryOut,
    RepoSelection,
    SendMessageBody,
)
from app.schemas_document_graph import DocumentGraphSearchResult  # noqa: E402, F401
from app.schemas_documents import (  # noqa: E402, F401
    DocumentCreate,
    DocumentGraphSummary,
    DocumentOut,
)
from app.schemas_mcp import McpServerCreate, McpServerOut, McpServerUpdate  # noqa: E402, F401
from app.schemas_platform import (  # noqa: E402, F401
    AiModelCreate,
    AiModelOut,
    AiModelSyncResult,
    AiProviderCreate,
    AiProviderOut,
    GitProviderCreate,
    GitProviderOut,
    RepositoryCreate,
    RepositoryOut,
)
from app.schemas_user_workspaces import (  # noqa: E402, F401
    UserWorkspaceEnsureBody,
    UserWorkspaceOut,
)
