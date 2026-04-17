"""ORM models for agent execution: tasks, events, CI/CD, routines and PR subscriptions."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.orm_models import Base, JSONBType, UUIDType

if TYPE_CHECKING:
    from app.infrastructure.orm_models import Conversation, RepoEnvironment, User


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
    sandbox_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType,
        ForeignKey("sandboxes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    env_slug: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    triggered_by: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    trigger_payload: Mapped[dict] = mapped_column(JSONBType, nullable=False, default=dict)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_event_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped["Conversation | None"] = relationship(
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DiffComment(Base):
    """Comentário inline do utilizador numa linha do diff do worktree."""

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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="diff_comments"
    )


class Routine(Base):
    """Automação salva com prompt + ambiente + triggers (schedule / API / GitHub)."""

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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    environment: Mapped["RepoEnvironment"] = relationship(
        "RepoEnvironment", back_populates="routines"
    )
    created_by_user: Mapped["User"] = relationship("User", back_populates="routines")
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
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    routine: Mapped[Routine] = relationship("Routine", back_populates="runs")


class PrSubscription(Base):
    """Assinatura de eventos de um PR para auto-fix."""

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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="pr_subscriptions"
    )
