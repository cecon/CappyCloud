"""Repository ports — ABCs for persistence adapters.

Each ABC defines the contract that both real (SQLAlchemy) and fake (in-memory)
implementations must satisfy, enabling LSP-verified substitution.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from app.domain.entities import (
    ContainerStatus,
    Conversation,
    Message,
    MessageAttachment,
    RepoEnvironment,
    Repository,
    Sandbox,
    User,
    UserRole,
)

__all__ = [
    "AiModelCapabilityLookup",
    "AttachmentRepository",
    "ContainerStatus",
    "ConversationRepository",
    "MessageRepository",
    "RepoEnvironmentRepository",
    "RepositoryRepository",
    "SandboxRepository",
    "UserRepository",
    "UserRole",
]


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

    @abstractmethod
    async def list_all(self) -> list[User]:
        """Lista todos os utilizadores ordenados por ``created_at`` ascendente.

        Sem paginação nesta 1ª iteração: o admin típico tem dezenas de users,
        não milhares (ADR-005). Quando crescer, adicionar ``limit``/``offset``
        explícitos sem quebrar o contrato.
        """

    @abstractmethod
    async def update_role(self, user_id: uuid.UUID, role: UserRole) -> User | None:
        """Atualiza apenas o papel. Devolve o utilizador atualizado, ou ``None``
        se o id não existir. Não mexe noutros campos."""


class SandboxRepository(ABC):
    """Port para o cadastro de sandboxes (ADR-004).

    Distinto do ``SandboxRuntimeGateway`` (que fala com Docker/Swarm). Este
    apenas persiste/lê a entidade.
    """

    @abstractmethod
    async def list_all(self) -> list[Sandbox]:
        """Lista todas as sandboxes, ordem cronológica de criação."""

    @abstractmethod
    async def get(self, sandbox_id: uuid.UUID) -> Sandbox | None:
        """Devolve sandbox por id, ou ``None`` se não existir."""

    @abstractmethod
    async def get_by_name(self, name: str) -> Sandbox | None:
        """Devolve sandbox por nome único, ou ``None`` se não existir."""

    @abstractmethod
    async def save(self, sandbox: Sandbox) -> Sandbox:
        """Insere uma nova sandbox e devolve-a com campos gerados."""

    @abstractmethod
    async def update(self, sandbox: Sandbox) -> Sandbox:
        """Persiste alterações de uma sandbox existente."""

    @abstractmethod
    async def update_container_status(
        self, sandbox_id: uuid.UUID, status: ContainerStatus
    ) -> Sandbox | None:
        """Atualiza apenas ``container_status``. Devolve a sandbox atualizada
        ou ``None`` se o id não existir."""

    @abstractmethod
    async def delete(self, sandbox_id: uuid.UUID) -> bool:
        """Remove a sandbox. Devolve ``True`` se algo foi apagado."""


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

    @abstractmethod
    async def get_confluence_settings(self, repo_id: uuid.UUID) -> tuple[str, str]:
        """Retorna ``(confluence_url, confluence_space)`` configurados para o repositório.

        Strings vazias quando o campo não está preenchido. ``space`` só faz
        sentido quando ``url`` está preenchida — o caller decide se ignora ou
        propaga o space órfão.
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

    @abstractmethod
    async def get_model_pricing(self, model_used: str) -> tuple[float, float] | None:
        """Devolve ``(input_cost_per_1m_usd, output_cost_per_1m_usd)`` ou ``None``.

        Lookup pelo ``model_id`` do catálogo de ``ai_models`` activos. Usado
        para calcular o ``cost_usd`` no fim de cada turno do agente.
        """


class AttachmentRepository(ABC):
    """Port para metadado de anexos de conversas."""

    @abstractmethod
    async def save(self, attachment: MessageAttachment) -> MessageAttachment:
        """Persiste um novo anexo e devolve-o."""

    @abstractmethod
    async def get(
        self, attachment_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> MessageAttachment | None:
        """Devolve anexo pertencente à conversa, ou ``None``."""

    @abstractmethod
    async def list_by_ids(
        self, attachment_ids: list[uuid.UUID], conversation_id: uuid.UUID
    ) -> list[MessageAttachment]:
        """Lista anexos pelos ids, garantindo que pertencem à conversa.

        Resultado ordenado pelo ``uploaded_at`` ascendente.
        """

    @abstractmethod
    async def delete(self, attachment_id: uuid.UUID, conversation_id: uuid.UUID) -> bool:
        """Remove o registo. Devolve ``True`` se algo foi apagado."""

    @abstractmethod
    async def update_description(
        self,
        attachment_id: uuid.UUID,
        description: str,
        model_used: str,
    ) -> None:
        """Persiste a descrição textual gerada pelo vision describer."""


class AiModelCapabilityLookup(ABC):
    """Port para consulta rápida de capacidades de modelo IA.

    Usado por ``StreamMessage`` para decidir se anexa imagens nativamente
    (Caminho A — modelos vision-capazes) ou cai para descrição textual
    pré-gerada pelo vision describer (Caminho C — modelos text-only).
    """

    @abstractmethod
    async def is_vision_capable(self, model_id: str) -> bool:
        """``True`` se ``model_id`` tem ``"vision"`` em ``capabilities``."""
