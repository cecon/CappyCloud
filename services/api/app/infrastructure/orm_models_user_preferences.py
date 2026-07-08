"""SQLAlchemy models for per-user persisted preferences."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.value_objects import DEFAULT_PERMISSION_MODE
from app.infrastructure.orm_base import Base, UUIDType


class UserPreferences(Base):
    __tablename__ = "user_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    default_permission_mode: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=DEFAULT_PERMISSION_MODE,
        default=DEFAULT_PERMISSION_MODE,
    )
