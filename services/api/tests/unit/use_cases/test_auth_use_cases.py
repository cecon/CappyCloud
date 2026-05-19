"""Unit tests for authentication use cases."""

import uuid

import pytest
from app.application.use_cases.auth import ChangePassword, GetCurrentUser, LoginUser, RegisterUser
from app.domain.entities import UserRole

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

    async def test_default_role_is_user(self, uc: RegisterUser) -> None:
        user = await uc.execute("default@test.com", "password123")
        assert user.role is UserRole.USER

    async def test_explicit_admin_role_is_persisted(self, uc: RegisterUser) -> None:
        user = await uc.execute("boss@test.com", "password123", UserRole.ADMIN)
        assert user.role is UserRole.ADMIN
        assert user.is_admin is True

    async def test_must_change_password_flag_can_be_set(self, uc: RegisterUser) -> None:
        user = await uc.execute(
            "first-login@test.com",
            "password123",
            must_change_password=True,
        )
        assert user.must_change_password is True


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

    async def test_wrong_password_raises(self, uc_with_user: tuple[LoginUser, str]) -> None:
        uc, _ = uc_with_user
        with pytest.raises(PermissionError, match="inválidas"):
            await uc.execute("login@test.com", "wrongpassword")

    async def test_unknown_email_raises(self, uc_with_user: tuple[LoginUser, str]) -> None:
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

    async def test_valid_token_returns_user(self, uc_with_user: tuple[GetCurrentUser, str]) -> None:
        uc, user_id = uc_with_user
        user = await uc.execute(f"token:{user_id}")
        assert str(user.id) == user_id

    async def test_invalid_token_raises(self, uc_with_user: tuple[GetCurrentUser, str]) -> None:
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


class TestChangePassword:
    async def test_changes_password_and_clears_first_login_flag(self) -> None:
        repo = InMemoryUserRepository()
        passwords = FakePasswordService()
        user = await RegisterUser(repo, passwords).execute(
            "change@test.com",
            "oldpassword",
            must_change_password=True,
        )
        uc = ChangePassword(repo, passwords)

        updated = await uc.execute(user.id, "oldpassword", "newpassword")

        assert updated.must_change_password is False
        assert updated.hashed_password == "hashed:newpassword"
        token_uc = LoginUser(repo, passwords, FakeTokenService())
        assert await token_uc.execute("change@test.com", "newpassword") == f"token:{user.id}"

    async def test_rejects_wrong_current_password(self) -> None:
        repo = InMemoryUserRepository()
        passwords = FakePasswordService()
        user = await RegisterUser(repo, passwords).execute("wrong@test.com", "oldpassword")
        uc = ChangePassword(repo, passwords)

        with pytest.raises(PermissionError, match="Senha atual inválida"):
            await uc.execute(user.id, "badpassword", "newpassword")

    async def test_rejects_unchanged_password(self) -> None:
        repo = InMemoryUserRepository()
        passwords = FakePasswordService()
        user = await RegisterUser(repo, passwords).execute("same@test.com", "oldpassword")
        uc = ChangePassword(repo, passwords)

        with pytest.raises(ValueError, match="diferente"):
            await uc.execute(user.id, "oldpassword", "oldpassword")
