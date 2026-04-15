"""Service ports — ABCs for security-related services."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class PasswordService(ABC):
    """Port for password hashing and verification."""

    @abstractmethod
    def hash(self, plain: str) -> str:
        """Return a secure hash of the plain-text password."""

    @abstractmethod
    def verify(self, plain: str, hashed: str) -> bool:
        """Return True if plain matches the hashed password."""


class TokenService(ABC):
    """Port for JWT creation and decoding."""

    @abstractmethod
    def create(self, subject: str) -> str:
        """Create a signed JWT token for the given subject (user id)."""

    @abstractmethod
    def decode(self, token: str) -> dict[str, Any]:
        """Decode and validate a JWT token. Raises ValueError on invalid token."""
