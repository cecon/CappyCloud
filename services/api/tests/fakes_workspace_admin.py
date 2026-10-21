"""Fake em memória da porta ``WorkspaceAdminRepository`` usado nos testes.

Mantém ``conftest.py`` abaixo de 300 linhas (regra ``max-file-length``).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable

from app.ports.workspace_admin import WorkspaceAdminRepository


class InMemoryWorkspaceAdminRepository(WorkspaceAdminRepository):
    def __init__(self) -> None:
        # (user_id, workspace_id) -> is_admin
        self.access: dict[tuple[uuid.UUID, uuid.UUID], bool] = {}
        self.models: dict[uuid.UUID, set[uuid.UUID]] = {}

    def add(self, user_id: uuid.UUID, workspace_id: uuid.UUID, *, admin: bool = False) -> None:
        self.access[(user_id, workspace_id)] = admin

    async def admin_workspace_ids(self, user_id: uuid.UUID) -> set[uuid.UUID]:
        return {ws for (uid, ws), admin in self.access.items() if uid == user_id and admin}

    async def member_workspace_ids(self, user_id: uuid.UUID) -> set[uuid.UUID]:
        return {ws for (uid, ws) in self.access if uid == user_id}

    async def member_user_ids(self, workspace_ids: Iterable[uuid.UUID]) -> set[uuid.UUID]:
        wanted = set(workspace_ids)
        return {uid for (uid, ws) in self.access if ws in wanted}

    async def grant_access(self, user_id: uuid.UUID, workspace_id: uuid.UUID) -> None:
        self.access.setdefault((user_id, workspace_id), False)

    async def copy_model_access(self, from_user_id: uuid.UUID, to_user_id: uuid.UUID) -> None:
        self.models.setdefault(to_user_id, set()).update(self.models.get(from_user_id, set()))
