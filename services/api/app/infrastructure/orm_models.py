"""ORM models — SQLAlchemy mapped classes for users, conversations and messages.

Named orm_models.py (not models.py) to avoid collision with domain/entities.py.
Sub-modules imported at the bottom register their tables with Base.metadata for Alembic:
  - orm_models_agent.py     → Agent, Skill (behavior profiles)
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
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator, Uuid


class Base(DeclarativeBase):
    """Base declarativa para modelos ORM."""


class UUIDType(TypeDecorator[uuid.UUID]):
    """UUID column compatible with both PostgreSQL and SQLite (for tests)."""

    impl = Uuid
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "sqlite":
            from sqlalchemy import String as SaString

            return dialect.type_descriptor(SaString(36))
        return dialect.type_descriptor(Uuid(as_uuid=True))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "sqlite":
            return str(value)
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


class JSONBType(TypeDecorator):
    """JSONB on PostgreSQL, JSON on SQLite (for tests)."""

    impl = JSONB
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "sqlite":
            from sqlalchemy import JSON

            return dialect.type_descriptor(JSON())
        return dialect.type_descriptor(JSONB())


class Sandbox(Base):
    """Instância do container sandbox que hospeda o openclaude gRPC.

    Cada linha representa um container Docker independente.
    status: active | draining | offline
    """

    __tablename__ = "sandboxes"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    host: Mapped[str] = mapped_column(String(256), nullable=False)
    grpc_port: Mapped[int] = mapped_column(Integer, nullable=False, default=50051)
    session_port: Mapped[int] = mapped_column(Integer, nullable=False, default=8080)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
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
    """Utilizador registado."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
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
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType,
        ForeignKey("agents.id", ondelete="SET NULL"),
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
    """Mensagem numa conversa."""

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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped[Conversation] = relationship("Conversation", back_populates="messages")


# Import sub-modules last — registers tables with Base.metadata for Alembic.
from app.infrastructure.orm_models_agent import (  # noqa: F401, E402
    Agent,
    Skill,
    UserAgentProfile,
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
from app.infrastructure.orm_models_platform import (  # noqa: F401, E402
    AiModel,
    AiProvider,
    GitProvider,
    Repository,
    SandboxSyncQueue,
)
