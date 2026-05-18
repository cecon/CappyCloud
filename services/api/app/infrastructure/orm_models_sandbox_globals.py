"""ORM models — skills globais, associações por sandbox e agents (ADR-004 §6).

Distintos de ``Skill`` (em ``orm_models_agent.py``, por repositório, RAG).
Estes vivem em ``~/.claude/skills/`` e ``~/.claude/agents/`` dentro do
container da sandbox, escritos pelo bootstrap ao boot.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.orm_base import Base, JSONBType, UUIDType


class GlobalSkill(Base):
    """Catálogo global de skills.

    As associações em ``global_skill_sandboxes`` definem quais sandboxes recebem
    cada skill no boot.
    """

    __tablename__ = "global_skills"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="", default="")
    content: Mapped[str] = mapped_column(Text, nullable=False, server_default="", default="")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class GlobalSkillSandbox(Base):
    """Associação entre skill global e sandbox que deve recebê-la."""

    __tablename__ = "global_skill_sandboxes"
    __table_args__ = (
        UniqueConstraint("skill_id", "sandbox_id", name="uq_global_skill_sandbox"),
    )

    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("global_skills.id", ondelete="CASCADE"),
        primary_key=True,
    )
    sandbox_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("sandboxes.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SandboxSkill(Base):
    """Tabela legada de skills por sandbox.

    Mantida para compatibilidade/migração. O catálogo novo vive em
    ``global_skills`` e as associações em ``global_skill_sandboxes``.
    """

    __tablename__ = "sandbox_skills"
    __table_args__ = (UniqueConstraint("sandbox_id", "name", name="uq_sandbox_skills_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    sandbox_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("sandboxes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="", default="")
    content: Mapped[str] = mapped_column(Text, nullable=False, server_default="", default="")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SandboxAgent(Base):
    """Subagent global da sandbox — vira arquivo ``~/.claude/agents/<name>.md``.

    Frontmatter YAML composto por ``name``, ``description``, ``tools``,
    ``model``; corpo é o ``system_prompt``.
    """

    __tablename__ = "sandbox_agents"
    __table_args__ = (UniqueConstraint("sandbox_id", "name", name="uq_sandbox_agents_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    sandbox_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("sandboxes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="", default="")
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False, server_default="", default="")
    model: Mapped[str] = mapped_column(String(256), nullable=False, server_default="", default="")
    tools: Mapped[list] = mapped_column(JSONBType, nullable=False, server_default="[]")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
