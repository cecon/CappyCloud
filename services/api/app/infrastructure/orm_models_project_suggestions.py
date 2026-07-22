"""ORM models for project chat suggestions and calibration runs."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.orm_base import Base, JSONBType, UUIDType


class ProjectSuggestion(Base):
    __tablename__ = "project_suggestions"
    __table_args__ = (
        Index("ix_project_suggestions_repo_status_priority", "repository_id", "status", "priority"),
        Index("ix_project_suggestions_repo_source", "repository_id", "source"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(96), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    safety_state: Mapped[str] = mapped_column(String(32), nullable=False, default="safe")
    freshness_state: Mapped[str] = mapped_column(String(32), nullable=False, default="fresh")
    analysis_window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    analysis_window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_calibrated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    suppressed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    suppressed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    suppression_reason: Mapped[str | None] = mapped_column(Text)
    suggestion_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONBType, nullable=False, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProjectSuggestionCalibrationRun(Base):
    __tablename__ = "project_suggestion_calibration_runs"
    __table_args__ = (
        Index("ix_project_suggestion_runs_repo_created", "repository_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trigger: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    analysis_window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    analysis_window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    eligible_message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    eligible_user_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    suggestions_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    suggestions_activated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    suggestions_suppressed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
