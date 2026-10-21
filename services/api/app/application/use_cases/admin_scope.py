"""Escopo de quem chama uma rota administrativa.

ADMIN global vê e gerencia tudo. Admin de workspace (USER com ``is_admin`` no
acesso ao workspace) só enxerga e gerencia os workspaces que administra e as
pessoas que têm acesso a eles. As rotas pedem o escopo e filtram por ele; a
negação acontece aqui, não só na UI.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass

from app.domain.entities import User, UserRole
from app.ports.workspace_admin import WorkspaceAdminRepository


class AdminScopeDeniedError(Exception):
    """Sem permissão de admin, ou fora do escopo do admin de workspace."""


@dataclass(frozen=True)
class AdminScope:
    user: User
    # None = ADMIN global (sem limite de workspace).
    workspace_ids: frozenset[uuid.UUID] | None

    @property
    def is_global(self) -> bool:
        return self.workspace_ids is None

    @property
    def is_super_admin(self) -> bool:
        return self.is_global and self.user.is_super_admin

    def allows(self, workspace_id: uuid.UUID | None) -> bool:
        if self.workspace_ids is None:
            return True
        return workspace_id is not None and workspace_id in self.workspace_ids

    def ensure_workspace(self, workspace_id: uuid.UUID | None) -> None:
        if not self.allows(workspace_id):
            raise AdminScopeDeniedError("Você não administra este workspace.")

    def visible(self, workspace_ids: Iterable[uuid.UUID]) -> list[uuid.UUID]:
        """Os ids que o escopo enxerga, na ordem recebida."""
        return [ws_id for ws_id in workspace_ids if self.allows(ws_id)]


class ResolveAdminScope:
    def __init__(self, repo: WorkspaceAdminRepository) -> None:
        self._repo = repo

    async def execute(self, user: User) -> AdminScope:
        if user.role is UserRole.ADMIN:
            return AdminScope(user=user, workspace_ids=None)
        ids = await self._repo.admin_workspace_ids(user.id)
        if not ids:
            raise AdminScopeDeniedError("Permissão insuficiente.")
        return AdminScope(user=user, workspace_ids=frozenset(ids))


def ensure_can_grant(scope: AdminScope, target: User, workspace_id: uuid.UUID) -> None:
    """Conceder acesso: o workspace é do escopo e o alvo é USER comum (não ele mesmo)."""
    scope.ensure_workspace(workspace_id)
    if scope.is_global:
        return
    if target.id == scope.user.id:
        raise AdminScopeDeniedError("Peça ao super admin para mudar o seu próprio acesso.")
    if target.role is UserRole.ADMIN:
        raise AdminScopeDeniedError("Só o super admin gerencia administradores.")


def ensure_can_revoke(
    scope: AdminScope, target: User, workspace_id: uuid.UUID, *, target_is_admin: bool
) -> None:
    """Revogar: como conceder, e admin de workspace não tira outro admin do workspace."""
    ensure_can_grant(scope, target, workspace_id)
    if not scope.is_global and target_is_admin:
        raise AdminScopeDeniedError("Só o super admin remove um admin do workspace.")


async def ensure_manageable_user(
    scope: AdminScope, target: User, repo: WorkspaceAdminRepository
) -> None:
    """Admin de workspace só mexe em USER comum que tenha acesso a um workspace dele.

    Nunca em si mesmo, em ADMIN global (inclui super admin) ou em outro admin de
    workspace. ADMIN global passa direto (as regras dele ficam nos use cases de
    cada rota).
    """
    if scope.is_global:
        return
    if target.id == scope.user.id:
        raise AdminScopeDeniedError("Use 'Trocar senha' ou peça ao super admin.")
    if target.role is UserRole.ADMIN:
        raise AdminScopeDeniedError("Só o super admin gerencia administradores.")
    if await repo.admin_workspace_ids(target.id):
        raise AdminScopeDeniedError("Só o super admin gerencia outro admin de workspace.")
    shared = scope.visible(await repo.member_workspace_ids(target.id))
    if not shared:
        raise AdminScopeDeniedError(
            "Este usuário não tem acesso a um workspace que você administra."
        )
