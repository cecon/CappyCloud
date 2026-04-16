"""ORM models — SQLAlchemy mapped classes for users, conversations and messages.

Named orm_models.py (not models.py) to avoid collision with domain/entities.py.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
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


class RepoEnvironment(Base):
    """Ambiente global (repositório git) partilhado por todos os utilizadores."""

    __tablename__ = "repo_environments"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    repo_url: Mapped[str] = mapped_column(Text, nullable=False)
    branch: Mapped[str] = mapped_column(String(256), nullable=False, default="main")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversations: Mapped[list[Conversation]] = relationship(
        "Conversation", back_populates="environment"
    )
    routines: Mapped[list[Routine]] = relationship("Routine", back_populates="environment")


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
    routines: Mapped[list[Routine]] = relationship(
        "Routine", back_populates="created_by_user", cascade="all, delete-orphan"
    )


class Conversation(Base):
    """Conversa (thread) por utilizador."""

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    environment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType,
        ForeignKey("repo_environments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(512), default="Nova conversa")
    base_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    github_pr_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    github_repo_slug: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship("User", back_populates="conversations")
    environment: Mapped[RepoEnvironment | None] = relationship(
        "RepoEnvironment", back_populates="conversations"
    )
    messages: Mapped[list[Message]] = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )
    agent_tasks: Mapped[list[AgentTask]] = relationship(
        "AgentTask", back_populates="conversation", cascade="all, delete-orphan"
    )
    diff_comments: Mapped[list[DiffComment]] = relationship(
        "DiffComment", back_populates="conversation", cascade="all, delete-orphan"
    )
    pr_subscriptions: Mapped[list[PrSubscription]] = relationship(
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


# ---------------------------------------------------------------------------
# Agent execution tables
# ---------------------------------------------------------------------------


class AgentTask(Base):
    """Unidade de execução autônoma do agente.

    Pode ser disparada por usuário, webhook de CI/CD, rotina agendada ou CLI.
    O ciclo de vida é: pending → running → (paused →) done | error.
    """

    __tablename__ = "agent_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType,
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    env_slug: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True
    )
    triggered_by: Mapped[str] = mapped_column(
        String(32), nullable=False, default="user"
    )
    trigger_payload: Mapped[dict] = mapped_column(JSONBType, nullable=False, default=dict)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_event_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    conversation: Mapped[Conversation | None] = relationship(
        "Conversation", back_populates="agent_tasks"
    )
    events: Mapped[list[AgentEvent]] = relationship(
        "AgentEvent", back_populates="task", cascade="all, delete-orphan"
    )


class AgentEvent(Base):
    """Evento do stream gRPC persistido em ordem sequencial.

    O `id` BIGSERIAL serve como cursor para reconexão da UI.
    """

    __tablename__ = "agent_events"
    __table_args__ = (Index("ix_agent_events_task_id_id", "task_id", "id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("agent_tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    data: Mapped[dict] = mapped_column(JSONBType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    task: Mapped[AgentTask] = relationship("AgentTask", back_populates="events")


class CicdEvent(Base):
    """Evento recebido via webhook de CI/CD (GitHub, GitLab)."""

    __tablename__ = "cicd_events"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    repo_slug: Mapped[str | None] = mapped_column(String(512), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONBType, nullable=False, default=dict)
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType,
        ForeignKey("agent_tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DiffComment(Base):
    """Comentário inline do utilizador numa linha do diff do worktree.

    Comentários não processados (bundled_at IS NULL) são injetados automaticamente
    no próximo prompt enviado para a conversa.
    """

    __tablename__ = "diff_comments"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    line: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    bundled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    conversation: Mapped[Conversation] = relationship(
        "Conversation", back_populates="diff_comments"
    )


# ---------------------------------------------------------------------------
# Routines — automações salvas com múltiplos triggers
# ---------------------------------------------------------------------------


class Routine(Base):
    """Automação salva com prompt + ambiente + triggers (schedule / API / GitHub).

    O campo `triggers` é um array JSON:
    [
      {"type": "schedule", "config": {"cron": "0 9 * * 1-5"}},
      {"type": "api"},
      {"type": "github", "config": {"repo_slug": "org/repo", "event": "pull_request.opened"}}
    ]
    """

    __tablename__ = "routines"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    env_slug: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("repo_environments.slug", ondelete="SET NULL"),
        nullable=False,
    )
    triggers: Mapped[list] = mapped_column(JSONBType, nullable=False, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    api_token_hash: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    environment: Mapped[RepoEnvironment] = relationship(
        "RepoEnvironment", back_populates="routines"
    )
    created_by_user: Mapped[User] = relationship("User", back_populates="routines")
    runs: Mapped[list[RoutineRun]] = relationship(
        "RoutineRun", back_populates="routine", cascade="all, delete-orphan"
    )


class RoutineRun(Base):
    """Registo de execução de uma routine."""

    __tablename__ = "routine_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    routine_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("routines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType,
        ForeignKey("agent_tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    triggered_by: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    routine: Mapped[Routine] = relationship("Routine", back_populates="runs")


# ---------------------------------------------------------------------------
# PR subscriptions — auto-fix de pull requests
# ---------------------------------------------------------------------------


class PrSubscription(Base):
    """Assinatura de eventos de um PR para auto-fix.

    Quando auto_fix_enabled=True, o webhook do GitHub dispara automaticamente
    uma nova AgentTask para a conversa associada ao receber:
    - check_run.completed com failure
    - pull_request_review com comentários
    """

    __tablename__ = "pr_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    repo_slug: Mapped[str] = mapped_column(String(512), nullable=False)
    pr_number: Mapped[int] = mapped_column(Integer, nullable=False)
    auto_fix_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    conversation: Mapped[Conversation] = relationship(
        "Conversation", back_populates="pr_subscriptions"
    )

