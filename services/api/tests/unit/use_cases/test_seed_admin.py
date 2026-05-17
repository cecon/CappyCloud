"""Unit tests for SeedFirstAdmin use case (ADR-005)."""

from __future__ import annotations

import uuid

import pytest
from app.application.use_cases.auth import RegisterUser
from app.application.use_cases.seed_admin import (
    FirstAdminAlreadyExistsError,
    FirstAdminEmailConflictError,
    SeedFirstAdmin,
)
from app.domain.entities import User, UserRole

from tests.conftest import FakePasswordService, InMemoryUserRepository


class TestSeedFirstAdmin:
    @pytest.fixture
    def repo(self) -> InMemoryUserRepository:
        return InMemoryUserRepository()

    @pytest.fixture
    def uc(self, repo: InMemoryUserRepository) -> SeedFirstAdmin:
        return SeedFirstAdmin(repo, FakePasswordService())

    async def test_creates_admin_when_email_missing(
        self, uc: SeedFirstAdmin, repo: InMemoryUserRepository
    ) -> None:
        admin = await uc.execute("admin@cappy.io", "longenough123")

        assert admin.role is UserRole.ADMIN
        assert admin.email == "admin@cappy.io"
        # Persistido com hash (não a senha em claro):
        assert admin.hashed_password == "hashed:longenough123"
        # Está mesmo no repo (não foi só devolvido):
        stored = await repo.get_by_email("admin@cappy.io")
        assert stored is not None and stored.is_admin

    async def test_idempotent_when_admin_already_exists(
        self, uc: SeedFirstAdmin, repo: InMemoryUserRepository
    ) -> None:
        existing = User(
            id=uuid.uuid4(),
            email="admin@cappy.io",
            hashed_password="hashed:original",
            role=UserRole.ADMIN,
        )
        await repo.save(existing)

        with pytest.raises(FirstAdminAlreadyExistsError):
            await uc.execute("admin@cappy.io", "outrasenha123")

        # Senha original preservada — seed não recriou:
        stored = await repo.get_by_email("admin@cappy.io")
        assert stored is not None
        assert stored.hashed_password == "hashed:original"

    async def test_rejects_when_email_exists_as_user(
        self, uc: SeedFirstAdmin, repo: InMemoryUserRepository
    ) -> None:
        # Email já cadastrado como USER comum — seed não deve promover sozinho.
        await RegisterUser(repo, FakePasswordService()).execute("joe@cappy.io", "password123")

        with pytest.raises(FirstAdminEmailConflictError, match="não é ADMIN"):
            await uc.execute("joe@cappy.io", "password123")

        # Confirmar que continua USER, sem promoção silenciosa:
        stored = await repo.get_by_email("joe@cappy.io")
        assert stored is not None
        assert stored.role is UserRole.USER

    async def test_normalises_email_before_lookup(
        self, uc: SeedFirstAdmin, repo: InMemoryUserRepository
    ) -> None:
        await uc.execute("CAPS@Cappy.IO", "password123")

        assert await repo.get_by_email("caps@cappy.io") is not None

    async def test_invalid_email_raises(self, uc: SeedFirstAdmin) -> None:
        with pytest.raises(ValueError, match="inválido"):
            await uc.execute("not-an-email", "password123")

    async def test_short_password_raises(self, uc: SeedFirstAdmin) -> None:
        with pytest.raises(ValueError, match="8 caracteres"):
            await uc.execute("admin@cappy.io", "short")
