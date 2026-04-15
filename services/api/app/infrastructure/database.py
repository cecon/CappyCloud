"""Sessão async SQLAlchemy e utilitários de base de dados."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.infrastructure.config import get_settings

settings = get_settings()
engine = create_async_engine(settings.database_url, echo=settings.debug)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependência FastAPI: sessão de base de dados."""
    async with async_session_factory() as session:
        yield session


async def init_db() -> None:
    """Cria tabelas e aplica migrations incrementais."""
    from app.infrastructure import orm_models

    async with engine.begin() as conn:
        # Cria tabelas novas (incluindo repo_environments antes de conversations para a FK)
        await conn.run_sync(orm_models.Base.metadata.create_all)
        # Migration incremental: adiciona environment_id a conversas já existentes
        await conn.execute(
            text(
                "ALTER TABLE conversations "
                "ADD COLUMN IF NOT EXISTS environment_id UUID "
                "REFERENCES repo_environments(id) ON DELETE SET NULL"
            )
        )
        # Migration incremental: branch de origem selecionada pelo utilizador para a sessão
        await conn.execute(
            text(
                "ALTER TABLE conversations "
                "ADD COLUMN IF NOT EXISTS base_branch VARCHAR(255)"
            )
        )
