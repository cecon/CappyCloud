"""Port de leitura do relatório de uso por workspace."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ReportWorkspace:
    id: uuid.UUID
    slug: str
    name: str
    theme_preset: str | None = None
    theme_rules: list[dict[str, Any]] | None = None


@dataclass(frozen=True)
class ReportMessage:
    conversation_id: uuid.UUID
    created_at: datetime
    cost_usd: float


@dataclass(frozen=True)
class ReportConversation:
    id: uuid.UUID
    workspace_id: uuid.UUID
    user_email: str
    title: str
    ticket_number: str | None = None
    branches: frozenset[str] = field(default_factory=frozenset)
    first_user_message: str = ""


def branches_from_repos(repos: Any) -> frozenset[str]:
    """``base_branch`` e ``branch_name`` de cada repo de ``conversations.repos``."""
    found: set[str] = set()
    for repo in repos if isinstance(repos, list) else []:
        if not isinstance(repo, dict):
            continue
        for key in ("base_branch", "branch_name"):
            value = repo.get(key)
            if isinstance(value, str) and value.strip():
                found.add(value.strip())
    return frozenset(found)


class WorkspaceReportRepository(ABC):
    """Dados crus do relatório; o cálculo fica no use case."""

    @abstractmethod
    async def list_workspaces(self) -> list[ReportWorkspace]:
        """Todos os workspaces, ordenados pelo nome."""

    @abstractmethod
    async def accessible_workspace_ids(self, user_id: uuid.UUID) -> set[uuid.UUID]:
        """Workspaces concedidos ao usuário em ``user_workspace_access``."""

    @abstractmethod
    async def list_period_messages(
        self, workspace_ids: Sequence[uuid.UUID], start: datetime, end: datetime
    ) -> list[ReportMessage]:
        """Mensagens com ``start <= created_at < end`` das conversas desses workspaces."""

    @abstractmethod
    async def get_conversations(
        self, conversation_ids: Sequence[uuid.UUID]
    ) -> list[ReportConversation]:
        """Dados das conversas, com a primeira mensagem do usuário."""

    @abstractmethod
    async def list_branches(self, workspace_ids: Sequence[uuid.UUID]) -> list[str]:
        """Branches distintas das conversas desses workspaces, ordenadas."""

    @abstractmethod
    async def save_theme_config(
        self,
        workspace_id: uuid.UUID,
        preset: str | None,
        rules: list[dict[str, Any]] | None,
    ) -> ReportWorkspace | None:
        """Grava o modelo e as regras próprias; ``None`` se o workspace não existe."""
