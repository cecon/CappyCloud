"""Sessão async SQLAlchemy e utilitários de base de dados."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    """Base declarativa para modelos ORM."""


settings = get_settings()
engine = create_async_engine(settings.database_url, echo=settings.debug)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependência FastAPI: sessão de base de dados."""
    async with async_session_factory() as session:
        yield session


async def init_db() -> None:
    """Cria tabelas em desenvolvimento (sem Alembic)."""
    from app import models  # noqa: F401 — regista modelos no metadata

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
