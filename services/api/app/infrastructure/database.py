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
    """Aplica migrations Alembic (upgrade head) ao arrancar a aplicação.

    Executa via subprocess para evitar conflito entre uvloop (event loop do uvicorn)
    e asyncio.run() dentro de asyncio.to_thread() que travava o startup.
    """
    import sys

    result = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "alembic",
        "-c",
        str(_ALEMBIC_INI),
        "upgrade",
        "head",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _stdout, stderr = await result.communicate()
    if result.returncode != 0:
        raise RuntimeError(
            f"Alembic upgrade failed (exit {result.returncode}):\n{stderr.decode(errors='replace')}"
        )
