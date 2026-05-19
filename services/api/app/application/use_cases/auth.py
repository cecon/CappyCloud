"""Authentication use cases — business logic for user registration and login.

No FastAPI, no SQLAlchemy. All dependencies injected via ports (ABCs).
"""

from __future__ import annotations

import uuid
from typing import Any

from app.domain.entities import User, UserRole
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

    async def execute(
        self,
        email: str,
        password: str,
        role: UserRole = UserRole.USER,
        must_change_password: bool = False,
    ) -> User:
        """Create and persist a new user.

        Args:
            email: endereço de email; será normalizado (lower-case, trim).
            password: senha em texto plano; validada e armazenada como hash.
            role: papel inicial do utilizador. Default :attr:`UserRole.USER`.
                Apenas chamadas confiáveis (HTTP autenticado como ADMIN, seed
                interno) devem passar :attr:`UserRole.ADMIN` (ADR-005).

        Raises:
            ValueError: se email/password forem inválidos ou o email já estiver
                registado.
        """
        email = validate_email(email)
        validate_password(password)

        if await self._users.get_by_email(email):
            raise ValueError("Email já registado.")

        user = User(
            id=uuid.uuid4(),
            email=email,
            hashed_password=self._passwords.hash(password),
            role=role,
            must_change_password=must_change_password,
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


class ChangePassword:
    """Change the authenticated user's password and clear first-login lock."""

    def __init__(self, users: UserRepository, passwords: PasswordService) -> None:
        self._users = users
        self._passwords = passwords

    async def execute(self, user_id: uuid.UUID, current_password: str, new_password: str) -> User:
        """Validate current password, store the new hash, and clear the lock.

        Raises:
            PermissionError: if the current password is wrong or user disappeared.
            ValueError: if the new password is invalid or unchanged.
        """
        validate_password(new_password)

        user = await self._users.get_by_id(user_id)
        if user is None:
            raise PermissionError("Utilizador não encontrado.")

        if not self._passwords.verify(current_password, user.hashed_password):
            raise PermissionError("Senha atual inválida.")

        if self._passwords.verify(new_password, user.hashed_password):
            raise ValueError("A nova senha deve ser diferente da senha atual.")

        updated = await self._users.update_password(
            user_id,
            self._passwords.hash(new_password),
            must_change_password=False,
        )
        if updated is None:
            raise PermissionError("Utilizador não encontrado.")
        return updated
