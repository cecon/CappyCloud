"""Pessoas de um workspace vistas e geridas pelo escopo de admin.

- ``ListScopedUsers``: ADMIN global vê todos; admin de workspace só quem tem
  acesso a um workspace que ele administra.
- ``AddWorkspaceMember``: cria USER (troca de senha obrigatória) já com acesso
  ao workspace; e-mail existente só ganha o acesso. Quem é criado por admin de
  workspace herda os modelos LLM do criador, senão não conseguiria conversar.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.application.use_cases.admin_scope import AdminScope, AdminScopeDeniedError
from app.application.use_cases.auth import RegisterUser
from app.domain.entities import User, UserRole
from app.domain.value_objects import validate_email
from app.ports.repositories import UserRepository
from app.ports.workspace_admin import WorkspaceAdminRepository


class ListScopedUsers:
    def __init__(self, users: UserRepository, access: WorkspaceAdminRepository) -> None:
        self._users = users
        self._access = access

    async def execute(self, scope: AdminScope) -> list[User]:
        everyone = await self._users.list_all()
        if scope.workspace_ids is None:
            return everyone
        members = await self._access.member_user_ids(scope.workspace_ids)
        return [user for user in everyone if user.id in members]


@dataclass(frozen=True)
class MemberResult:
    user: User
    created: bool


class AddWorkspaceMember:
    def __init__(
        self,
        users: UserRepository,
        access: WorkspaceAdminRepository,
        register: RegisterUser,
    ) -> None:
        self._users = users
        self._access = access
        self._register = register

    async def execute(
        self, scope: AdminScope, *, email: str, password: str, workspace_id: uuid.UUID
    ) -> MemberResult:
        scope.ensure_workspace(workspace_id)
        existing = await self._users.get_by_email(validate_email(email))
        if existing is not None:
            if not scope.is_global and existing.role is UserRole.ADMIN:
                raise AdminScopeDeniedError("Só o super admin gerencia administradores.")
            await self._access.grant_access(existing.id, workspace_id)
            return MemberResult(user=existing, created=False)

        user = await self._register.execute(
            email, password, UserRole.USER, must_change_password=True
        )
        await self._access.grant_access(user.id, workspace_id)
        if not scope.is_global:
            await self._access.copy_model_access(scope.user.id, user.id)
        return MemberResult(user=user, created=True)
