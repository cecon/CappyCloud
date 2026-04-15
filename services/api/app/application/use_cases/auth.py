"""Authentication use cases — business logic for user registration and login.

No FastAPI, no SQLAlchemy. All dependencies injected via ports (ABCs).
"""

from __future__ import annotations

import uuid
from typing import Any

from app.domain.entities import User
from app.domain.value_objects import validate_email, validate_password
from app.ports.repositories import UserRepository
from app.ports.services import PasswordService, TokenService


class RegisterUser:
    """Register a new user account.

    Validates email/password, checks for duplicate emails,
    hashes the password, and persists the user.
    """

    def __init__(self, users: UserRepository, passwords: PasswordService) -> None:
        self._users = users
        self._passwords = passwords

    async def execute(self, email: str, password: str) -> User:
        """Create and persist a new user.

        Raises:
            ValueError: if email/password invalid or email already registered.
        """
        email = validate_email(email)
        validate_password(password)

        if await self._users.get_by_email(email):
            raise ValueError("Email já registado.")

        user = User(
            id=uuid.uuid4(),
            email=email,
            hashed_password=self._passwords.hash(password),
        )
        return await self._users.save(user)


class LoginUser:
    """Authenticate a user and issue a JWT access token."""

    def __init__(
        self,
        users: UserRepository,
        passwords: PasswordService,
        tokens: TokenService,
    ) -> None:
        self._users = users
        self._passwords = passwords
        self._tokens = tokens

    async def execute(self, email: str, password: str) -> str:
        """Verify credentials and return a JWT access token.

        Raises:
            PermissionError: if credentials are invalid.
        """
        normalised = email.strip().lower()
        user = await self._users.get_by_email(normalised)

        if not user or not self._passwords.verify(password, user.hashed_password):
            raise PermissionError("Credenciais inválidas.")

        return self._tokens.create(str(user.id))


class GetCurrentUser:
    """Resolve the authenticated user from a JWT token."""

    def __init__(self, users: UserRepository, tokens: TokenService) -> None:
        self._users = users
        self._tokens = tokens

    async def execute(self, token: str) -> User:
        """Return the user identified by token.

        Raises:
            PermissionError: if token is invalid or user no longer exists.
        """
        try:
            payload: dict[str, Any] = self._tokens.decode(token)
        except (ValueError, Exception) as exc:
            raise PermissionError("Token inválido ou expirado.") from exc

        user = await self._users.get_by_id(uuid.UUID(payload["sub"]))
        if not user:
            raise PermissionError("Utilizador não encontrado.")
        return user
