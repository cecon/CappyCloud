"""Sessão async SQLAlchemy e utilitários de base de dados."""

from __future__ import annotations

import asyncio
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.infrastructure.config import get_settings

settings = get_settings()
engine = create_async_engine(settings.database_url, echo=settings.debug)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Alembic .ini is at services/api/alembic.ini (two levels up from this file)
_ALEMBIC_INI = Path(__file__).parent.parent.parent / "alembic.ini"


async def get_db():
    """Dependência FastAPI: sessão de base de dados."""
    async with async_session_factory() as session:
        yield session


async def init_db() -> None:
    """Aplica migrations Alembic (upgrade head) ao arrancar a aplicação."""
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config(str(_ALEMBIC_INI))
    # Override URL to pick up the runtime env var (not the placeholder in .ini)
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
    await asyncio.to_thread(command.upgrade, alembic_cfg, "head")

