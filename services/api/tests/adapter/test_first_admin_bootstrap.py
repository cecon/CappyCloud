"""Adapter test: ensure_first_admin contra SQLite real (ADR-005)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from app.adapters.secondary.persistence.sqlalchemy_user_repo import (
    SQLAlchemyUserRepository,
)
from app.domain.entities import UserRole
from app.infrastructure.config import Settings
from app.infrastructure.first_admin_bootstrap import ensure_first_admin
from app.infrastructure.orm_models import Base
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from tests.conftest import FakePasswordService


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def sqlite_engine() -> AsyncGenerator[Any]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def session_factory(sqlite_engine: Any) -> async_sessionmaker:
    from sqlalchemy.ext.asyncio import AsyncSession

    return async_sessionmaker(sqlite_engine, class_=AsyncSession, expire_on_commit=False)


def _settings(email: str, password: str) -> Settings:
    return Settings(first_admin_email=email, first_admin_password=password)


class TestEnsureFirstAdmin:
    async def test_noop_when_email_empty(self, session_factory: async_sessionmaker) -> None:
        await ensure_first_admin(
            _settings("", "password123"), session_factory, FakePasswordService()
        )

        async with session_factory() as s:
            assert await SQLAlchemyUserRepository(s).get_by_email("any@x.com") is None

    async def test_noop_when_password_empty(self, session_factory: async_sessionmaker) -> None:
        await ensure_first_admin(
            _settings("first@x.com", ""), session_factory, FakePasswordService()
        )

        async with session_factory() as s:
            assert await SQLAlchemyUserRepository(s).get_by_email("first@x.com") is None

    async def test_creates_admin_when_settings_filled(
        self, session_factory: async_sessionmaker
    ) -> None:
        await ensure_first_admin(
            _settings("boot@cappy.io", "password123"),
            session_factory,
            FakePasswordService(),
        )

        async with session_factory() as s:
            found = await SQLAlchemyUserRepository(s).get_by_email("boot@cappy.io")
        assert found is not None
        assert found.role is UserRole.ADMIN

    async def test_idempotent_on_rerun(self, session_factory: async_sessionmaker) -> None:
        settings = _settings("idem@cappy.io", "password123")
        await ensure_first_admin(settings, session_factory, FakePasswordService())
        # Segunda execução não deve falhar nem duplicar.
        await ensure_first_admin(settings, session_factory, FakePasswordService())

        async with session_factory() as s:
            found = await SQLAlchemyUserRepository(s).get_by_email("idem@cappy.io")
        assert found is not None
        assert found.is_admin
