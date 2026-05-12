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


class AttachmentStorage(ABC):
    """Port para storage de bytes de anexos (volume Docker, S3, etc.)."""

    @abstractmethod
    async def save(self, *, conversation_id: str, filename: str, content: bytes) -> str:
        """Persiste o ficheiro e devolve o ``storage_path`` resultante.

        O caminho devolvido é opaco para o caller — só o próprio storage
        precisa saber decodificá-lo em :meth:`read` / :meth:`delete`.
        """

    @abstractmethod
    async def read(self, storage_path: str) -> bytes:
        """Lê o conteúdo binário do anexo."""

    @abstractmethod
    async def delete(self, storage_path: str) -> bool:
        """Remove o ficheiro físico. Devolve ``True`` se algo foi apagado."""


class VisionDescriber(ABC):
    """Port para gerar descrição textual rica de uma imagem.

    Permite injetar o conteúdo visual num prompt text-only, viabilizando
    comparativos honestos entre modelos (incluindo os sem capacidade
    multimodal nativa, como DeepSeek-Chat).
    """

    @abstractmethod
    async def describe(
        self, *, mime_type: str, content: bytes, hint: str | None = None
    ) -> tuple[str, str]:
        """Devolve ``(descrição_textual, modelo_usado)``.

        ``hint`` (opcional) dá contexto adicional ao modelo de visão (ex.:
        "esta imagem foi anexada a uma pergunta sobre arquitetura").
        """
