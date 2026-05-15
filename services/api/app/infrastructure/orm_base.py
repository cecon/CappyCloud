"""Base declarativa e tipos customizados compartilhados entre módulos ORM.

Separado para evitar imports circulares entre orm_models.py e seus sub-módulos.
"""

from __future__ import annotations

import uuid

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase
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
