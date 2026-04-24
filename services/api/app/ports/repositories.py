"""Repository ports — ABCs for persistence adapters.

Each ABC defines the contract that both real (SQLAlchemy) and fake (in-memory)
implementations must satisfy, enabling LSP-verified substitution.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from app.domain.entities import Conversation, Message, RepoEnvironment, Repository, User


class UserRepository(ABC):
    """Port for user persistence operations."""

    @abstractmethod
    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """Return user by primary key, or None if not found."""

    @abstractmethod
    async def get_by_email(self, email: str) -> User | None:
        """Return user by email (case-insensitive), or None if not found."""

    @abstractmethod
    async def save(self, user: User) -> User:
        """Persist a new user and return it with any DB-generated fields."""


class UserAgentProfileRepository(ABC):
    """Port para resolver o agente padrão associado ao utilizador."""

    @abstractmethod
    async def get_default_agent_id(self, user_id: uuid.UUID) -> uuid.UUID | None:
        """Retorna o agente padrão do utilizador, ou None se não houver vínculo."""


class RepoEnvironmentRepository(ABC):
    """Port for global repo environment persistence."""

    @abstractmethod
    async def list_all(self) -> list[RepoEnvironment]:
        """Return all repo environments ordered by name."""

    @abstractmethod
    async def get(self, env_id: uuid.UUID) -> RepoEnvironment | None:
        """Return repo environment by primary key, or None if not found."""

    @abstractmethod
    async def get_by_slug(self, slug: str) -> RepoEnvironment | None:
        """Return repo environment by slug, or None if not found."""

    @abstractmethod
    async def save(self, env: RepoEnvironment) -> RepoEnvironment:
        """Persist a new repo environment and return it."""

    @abstractmethod
    async def delete(self, env_id: uuid.UUID) -> None:
        """Remove a repo environment record."""


class RepositoryRepository(ABC):
    """Port para o cat\u00e1logo de reposit\u00f3rios git geridos pelo sandbox.

    Distinto de :class:`RepoEnvironmentRepository` (este \u00faltimo \u00e9 legado).
    A tabela subjacente (``repositories``) \u00e9 a fonte da verdade para slugs
    usados no fluxo de sandbox/worktree e ser\u00e1 a ref de FK para skills
    vinculadas a um repo.
    """

    @abstractmethod
    async def get(self, repo_id: uuid.UUID) -> Repository | None:
        """Retorna o reposit\u00f3rio pelo id, ou None se n\u00e3o existir."""

    @abstractmethod
    async def get_by_slug(self, slug: str) -> Repository | None:
        """Retorna o reposit\u00f3rio pelo slug \u00fanico, ou None se n\u00e3o existir."""

    @abstractmethod
    async def get_authenticated_clone_url(self, repo_id: uuid.UUID) -> str | None:
        """Retorna clone_url com token PAT embutido, ou None se n\u00e3o houver credencial.

        Decripta o token do GitProvider associado e injeta na URL para que
        session_start.sh consiga autenticar o clone/fetch sem env vars globais.
        """


class ConversationRepository(ABC):
    """Port for conversation persistence operations."""

    @abstractmethod
    async def list_by_user(self, user_id: uuid.UUID) -> list[Conversation]:
        """Return all conversations for a user, newest first."""

    @abstractmethod
    async def get(self, conversation_id: uuid.UUID, user_id: uuid.UUID) -> Conversation | None:
        """Return conversation owned by user, or None if not found / not owned."""

    @abstractmethod
    async def save(self, conversation: Conversation) -> Conversation:
        """Persist a new conversation and return it."""

    @abstractmethod
    async def update(self, conversation: Conversation) -> Conversation:
        """Persist changes to an existing conversation and return it."""


class MessageRepository(ABC):
    """Port for message persistence operations."""

    @abstractmethod
    async def list_by_conversation(self, conversation_id: uuid.UUID) -> list[Message]:
        """Return all messages for a conversation, oldest first."""

    @abstractmethod
    async def save(self, message: Message) -> Message:
        """Persist a new message and return it."""
