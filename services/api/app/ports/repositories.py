"""Repository ports — ABCs for persistence adapters.

Each ABC defines the contract that both real (SQLAlchemy) and fake (in-memory)
implementations must satisfy, enabling LSP-verified substitution.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from app.domain.entities import Conversation, Message, RepoEnvironment, User


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
