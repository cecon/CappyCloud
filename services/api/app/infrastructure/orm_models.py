"""ORM models — SQLAlchemy mapped classes for users, conversations and messages.

Named orm_models.py (not models.py) to avoid collision with domain/entities.py.
Sub-modules imported at the bottom register their tables with Base.metadata for Alembic:
  - orm_models_agent.py     → Skill (knowledge base)
  - orm_models_execution.py → AgentTask, AgentEvent, CicdEvent, Routine, etc.
  - orm_models_platform.py  → GitProvider, Repository, AiProvider, AiModel, etc.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.orm_base import Base, JSONBType, UUIDType

__all__ = ["Base", "JSONBType", "UUIDType"]


class Sandbox(Base):
    """Instância do container sandbox que hospeda o openclaude gRPC.

    Cada linha representa um container Docker independente (ADR-004).
    ``status`` é o estado lógico (active|draining|offline); ``container_status``
    é o estado físico do container no orquestrador.
    """

    __tablename__ = "sandboxes"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    host: Mapped[str] = mapped_column(String(256), nullable=False)
    grpc_port: Mapped[int] = mapped_column(Integer, nullable=False, default=50051)
    session_port: Mapped[int] = mapped_column(Integer, nullable=False, default=8080)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    runtime: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="compose", default="compose"
    )
    image: Mapped[str] = mapped_column(String(512), nullable=False, server_default="", default="")
    env_vars: Mapped[dict] = mapped_column(JSONBType, nullable=False, server_default="{}")
    container_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default="not_created",
        default="not_created",
        index=True,
    )
    register_token: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation", back_populates="sandbox"
    )
    sync_queue: Mapped[list["SandboxSyncQueue"]] = relationship(
        "SandboxSyncQueue", back_populates="sandbox", cascade="all, delete-orphan"
    )
    repositories: Mapped[list["Repository"]] = relationship("Repository", back_populates="sandbox")


class RepoEnvironment(Base):
    """Ambiente global (repositório git) partilhado por todos os utilizadores."""

    __tablename__ = "repo_environments"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    repo_url: Mapped[str] = mapped_column(Text, nullable=False)
    branch: Mapped[str] = mapped_column(String(256), nullable=False, default="main")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    routines: Mapped[list["Routine"]] = relationship("Routine", back_populates="environment")


class User(Base):
    """Utilizador registado.

    O campo ``role`` é guardado em texto (``"admin" | "user"``) e mapeado para
    o enum :class:`app.domain.entities.UserRole` na camada de domínio (ADR-005).
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="user", default="user", index=True
    )
    is_super_admin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False, index=True
    )
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversations: Mapped[list[Conversation]] = relationship(
        "Conversation", back_populates="user", cascade="all, delete-orphan"
    )
    routines: Mapped[list["Routine"]] = relationship(
        "Routine", back_populates="created_by_user", cascade="all, delete-orphan"
    )


class Conversation(Base):
    """Conversa (thread) por utilizador."""

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sandbox_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType,
        ForeignKey("sandboxes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    ai_model_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType,
        ForeignKey("ai_models.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(512), default="Nova conversa")
    # Multi-repo: lista de {slug, alias, base_branch, branch_name, worktree_path}
    repos: Mapped[list] = mapped_column(JSONBType, nullable=False, server_default="[]")
    # Diretório raiz da sessão no volume: /repos/sessions/<short_id>/
    session_root: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Worktree state
    worktree_exists: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    lines_added: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lines_removed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    files_changed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # PR tracking
    pr_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    pr_status: Mapped[str] = mapped_column(String(32), nullable=False, default="none")
    pr_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # CI tracking
    ci_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    ci_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    github_pr_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    github_repo_slug: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship("User", back_populates="conversations")
    sandbox: Mapped["Sandbox | None"] = relationship("Sandbox", back_populates="conversations")
    ai_model: Mapped["AiModel | None"] = relationship("AiModel", back_populates="conversations")
    messages: Mapped[list[Message]] = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )
    agent_tasks: Mapped[list["AgentTask"]] = relationship(
        "AgentTask", back_populates="conversation", cascade="all, delete-orphan"
    )
    diff_comments: Mapped[list["DiffComment"]] = relationship(
        "DiffComment", back_populates="conversation", cascade="all, delete-orphan"
    )
    pr_subscriptions: Mapped[list["PrSubscription"]] = relationship(
        "PrSubscription", back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base):
    """Mensagem numa conversa.

    Em mensagens de ``role='assistant'``, os campos ``model_used``,
    ``prompt_tokens``, ``completion_tokens`` e ``cost_usd`` são preenchidos
    no fim do turno do agente. Para ``role='user'`` ficam ``NULL``/``0``.
    """

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    model_used: Mapped[str | None] = mapped_column(String(256), nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped[Conversation] = relationship("Conversation", back_populates="messages")


class MessageAttachment(Base):
    """Anexo carregado pelo utilizador (inicialmente imagens).

    O ficheiro físico vive num volume Docker (``storage_path``); aqui
    armazenamos apenas o metadado e a descrição textual gerada pelo modelo
    de visão (``vision_description``) que é injetada no prompt do agente.
    """

    __tablename__ = "message_attachments"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType,
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="image")
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processing_status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="uploaded", default="uploaded", index=True
    )
    chunks_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    vision_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    vision_model_used: Mapped[str | None] = mapped_column(String(256), nullable=True)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(UUIDType, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ConversationArtifactChunk(Base):
    """Chunk pesquisável de um arquivo anexado a uma conversa."""

    __tablename__ = "conversation_artifact_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    attachment_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("message_attachments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    line_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    line_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    meta: Mapped[dict] = mapped_column(JSONBType, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# Import sub-modules last — registers tables with Base.metadata for Alembic.
from app.infrastructure.orm_models_access import (  # noqa: F401, E402
    UserAiModelAccess,
    UserRepositoryAccess,
    UserSandboxAccess,
)
from app.infrastructure.orm_models_agent import (  # noqa: F401, E402
    Skill,
)
from app.infrastructure.orm_models_agentic_delivery import (  # noqa: F401, E402
    AgenticDeliveryCycle,
    AgenticDeliveryPermission,
    AgentOutput,
    AgentOutputEvidenceLink,
    CycleMetric,
    EvidenceSource,
    ExternalActionAuthorization,
    KnowledgeReuseRelationship,
    LifecycleTransition,
    ReusableKnowledgeItem,
    ReviewDecision,
    ReviewGate,
    SensitiveSurface,
    StructuredWorkPackage,
)
from app.infrastructure.orm_models_execution import (  # noqa: F401, E402
    AgentEvent,
    AgentTask,
    CicdEvent,
    DiffComment,
    PrSubscription,
    Routine,
    RoutineRun,
)
from app.infrastructure.orm_models_graph import (  # noqa: F401, E402
    GraphEdge,
    GraphNode,
    GraphReconciliationRun,
)
from app.infrastructure.orm_models_mcp import (  # noqa: F401, E402
    McpServer,
    McpToolInvocation,
    UserMcpServer,
)
from app.infrastructure.orm_models_platform import (  # noqa: F401, E402
    AiModel,
    AiProvider,
    Document,
    GitProvider,
    Repository,
    SandboxSyncQueue,
)
from app.infrastructure.orm_models_sandbox_globals import (  # noqa: F401, E402
    GlobalSkill as GlobalSkillORM,
)
