"""Fake em memória da port do relatório de uso por workspace."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime
from typing import Any

from app.ports.workspace_report import (
    ReportConversation,
    ReportMessage,
    ReportWorkspace,
    WorkspaceReportRepository,
)


class InMemoryWorkspaceReportRepository(WorkspaceReportRepository):
    def __init__(self) -> None:
        self.workspaces: dict[uuid.UUID, ReportWorkspace] = {}
        self.access: dict[uuid.UUID, set[uuid.UUID]] = {}
        self.conversations: dict[uuid.UUID, ReportConversation] = {}
        self.messages: list[ReportMessage] = []

    def add_workspace(self, ws: ReportWorkspace) -> ReportWorkspace:
        self.workspaces[ws.id] = ws
        return ws

    def grant(self, user_id: uuid.UUID, workspace_id: uuid.UUID) -> None:
        self.access.setdefault(user_id, set()).add(workspace_id)

    def add_conversation(self, conv: ReportConversation, *messages: ReportMessage) -> None:
        self.conversations[conv.id] = conv
        self.messages.extend(messages)

    async def list_workspaces(self) -> list[ReportWorkspace]:
        return sorted(self.workspaces.values(), key=lambda ws: ws.name)

    async def accessible_workspace_ids(self, user_id: uuid.UUID) -> set[uuid.UUID]:
        return set(self.access.get(user_id, set()))

    async def list_period_messages(
        self, workspace_ids: Sequence[uuid.UUID], start: datetime, end: datetime
    ) -> list[ReportMessage]:
        wanted = set(workspace_ids)
        return [
            msg
            for msg in self.messages
            if msg.conversation_id in self.conversations
            and self.conversations[msg.conversation_id].workspace_id in wanted
            and start <= msg.created_at < end
        ]

    async def get_conversations(
        self, conversation_ids: Sequence[uuid.UUID]
    ) -> list[ReportConversation]:
        return [self.conversations[cid] for cid in conversation_ids if cid in self.conversations]

    async def list_branches(self, workspace_ids: Sequence[uuid.UUID]) -> list[str]:
        wanted = set(workspace_ids)
        found: set[str] = set()
        for conv in self.conversations.values():
            if conv.workspace_id in wanted:
                found |= conv.branches
        return sorted(found)

    async def save_theme_config(
        self,
        workspace_id: uuid.UUID,
        preset: str | None,
        rules: list[dict[str, Any]] | None,
    ) -> ReportWorkspace | None:
        ws = self.workspaces.get(workspace_id)
        if ws is None:
            return None
        self.workspaces[workspace_id] = replace(ws, theme_preset=preset, theme_rules=rules)
        return self.workspaces[workspace_id]
