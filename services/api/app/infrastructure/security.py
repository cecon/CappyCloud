"""Hash de passwords e tokens JWT + implementações dos ports de segurança."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.infrastructure.config import get_settings
from app.ports.services import PasswordService, TokenService

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ---------------------------------------------------------------------------
# Low-level helpers (used by concrete service implementations below)
# ---------------------------------------------------------------------------


def hash_password(plain: str) -> str:
    """Gera hash bcrypt da password."""
    return str(pwd_context.hash(plain))


def verify_password(plain: str, hashed: str) -> bool:
    """Verifica password contra hash."""
    return bool(pwd_context.verify(plain, hashed))


def create_access_token(subject: str, extra: dict[str, Any] | None = None) -> str:
    """Emite JWT de acesso."""
    s = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=s.access_token_expire_minutes)
    payload: dict[str, Any] = {"sub": subject, "exp": expire}
    if extra:
        payload.update(extra)
    return str(jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm))


def decode_token(token: str) -> dict[str, Any]:
    """Decodifica e valida JWT. Raises ValueError se inválido."""
    s = get_settings()
    try:
        result: dict[str, Any] = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
        return result
    except JWTError as exc:
        raise ValueError("Token inválido ou expirado.") from exc


# ---------------------------------------------------------------------------
# Port implementations (concrete adapters for PasswordService / TokenService)
# ---------------------------------------------------------------------------


class BcryptPasswordService(PasswordService):
    """Implements PasswordService using bcrypt via passlib."""

    def hash(self, plain: str) -> str:
        return hash_password(plain)

    def verify(self, plain: str, hashed: str) -> bool:
        return verify_password(plain, hashed)


class JWTTokenService(TokenService):
    """Implements TokenService using python-jose JWT."""

    def create(self, subject: str) -> str:
        return create_access_token(subject)

    def decode(self, token: str) -> dict[str, Any]:
        return decode_token(token)
