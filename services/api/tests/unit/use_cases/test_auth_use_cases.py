"""Unit tests for authentication use cases."""

import uuid

import pytest
from app.application.use_cases.auth import GetCurrentUser, LoginUser, RegisterUser

from tests.conftest import (
    FakePasswordService,
    FakeTokenService,
    InMemoryUserRepository,
)


class TestRegisterUser:
    @pytest.fixture
    def uc(self) -> RegisterUser:
        return RegisterUser(InMemoryUserRepository(), FakePasswordService())

    async def test_creates_user_with_normalised_email(self, uc: RegisterUser) -> None:
        user = await uc.execute("USER@Example.COM", "password123")
        assert user.email == "user@example.com"

    async def test_hashes_password(self, uc: RegisterUser) -> None:
        user = await uc.execute("a@b.com", "mypassword")
        assert user.hashed_password == "hashed:mypassword"
        assert user.hashed_password != "mypassword"

    async def test_assigns_uuid(self, uc: RegisterUser) -> None:
        user = await uc.execute("a@b.com", "password1")
        assert isinstance(user.id, uuid.UUID)

    async def test_duplicate_email_raises(self, uc: RegisterUser) -> None:
        await uc.execute("dup@test.com", "password1")
        with pytest.raises(ValueError, match="já registado"):
            await uc.execute("dup@test.com", "password2")

    async def test_invalid_email_raises(self, uc: RegisterUser) -> None:
        with pytest.raises(ValueError, match="inválido"):
            await uc.execute("not-an-email", "password1")

    async def test_short_password_raises(self, uc: RegisterUser) -> None:
        with pytest.raises(ValueError, match="8 caracteres"):
            await uc.execute("a@b.com", "short")


class TestLoginUser:
    @pytest.fixture
    async def uc_with_user(self) -> tuple[LoginUser, str]:
        repo = InMemoryUserRepository()
        passwords = FakePasswordService()
        tokens = FakeTokenService()
        # Pre-register a user
        reg = RegisterUser(repo, passwords)
        user = await reg.execute("login@test.com", "goodpassword")
        uc = LoginUser(repo, passwords, tokens)
        return uc, str(user.id)

    async def test_valid_credentials_return_token(
        self, uc_with_user: tuple[LoginUser, str]
    ) -> None:
        uc, user_id = uc_with_user
        token = await uc.execute("login@test.com", "goodpassword")
        assert token == f"token:{user_id}"

    async def test_wrong_password_raises(
        self, uc_with_user: tuple[LoginUser, str]
    ) -> None:
        uc, _ = uc_with_user
        with pytest.raises(PermissionError, match="inválidas"):
            await uc.execute("login@test.com", "wrongpassword")

    async def test_unknown_email_raises(
        self, uc_with_user: tuple[LoginUser, str]
    ) -> None:
        uc, _ = uc_with_user
        with pytest.raises(PermissionError, match="inválidas"):
            await uc.execute("nobody@test.com", "goodpassword")

    async def test_email_normalised_before_lookup(
        self, uc_with_user: tuple[LoginUser, str]
    ) -> None:
        uc, user_id = uc_with_user
        token = await uc.execute("LOGIN@TEST.COM", "goodpassword")
        assert token == f"token:{user_id}"


class TestGetCurrentUser:
    @pytest.fixture
    async def uc_with_user(self) -> tuple[GetCurrentUser, str]:
        repo = InMemoryUserRepository()
        tokens = FakeTokenService()
        # Register directly
        reg = RegisterUser(repo, FakePasswordService())
        user = await reg.execute("current@test.com", "password1")
        uc = GetCurrentUser(repo, tokens)
        return uc, str(user.id)

    async def test_valid_token_returns_user(
        self, uc_with_user: tuple[GetCurrentUser, str]
    ) -> None:
        uc, user_id = uc_with_user
        user = await uc.execute(f"token:{user_id}")
        assert str(user.id) == user_id

    async def test_invalid_token_raises(
        self, uc_with_user: tuple[GetCurrentUser, str]
    ) -> None:
        uc, _ = uc_with_user
        with pytest.raises(PermissionError, match="inválido"):
            await uc.execute("bad-token")

    async def test_unknown_user_id_raises(self) -> None:
        repo = InMemoryUserRepository()
        tokens = FakeTokenService()
        uc = GetCurrentUser(repo, tokens)
        phantom_id = str(uuid.uuid4())
        with pytest.raises(PermissionError, match="não encontrado"):
            await uc.execute(f"token:{phantom_id}")
