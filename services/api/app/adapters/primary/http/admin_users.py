"""HTTP adapter para gestão administrativa de utilizadores (ADR-005).

Listar, redefinir senha e incluir membro aceitam ADMIN global ou admin de
workspace (este só vê e mexe em USER dos workspaces que administra). Mudar
papel continua só para ADMIN; redefinir senha, para super admin ou admin de
workspace. Glue fino: parse → use case → serialize.
"""

from __future__ import annotations

import os
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.adapters.primary.http.deps import get_register_uc, get_user_repo, require_role
from app.adapters.primary.http.deps_auth import (
    get_admin_scope,
    get_password_service,
    get_workspace_admin_repo,
)
from app.application.use_cases.admin_scope import (
    AdminScope,
    AdminScopeDeniedError,
    ensure_manageable_user,
)
from app.application.use_cases.admin_users import (
    CannotChangeSuperAdminRoleError,
    CannotDemoteSelfError,
    CannotResetOwnPasswordError,
    ResetUserPassword,
    UpdateUserRole,
    UserNotFoundError,
)
from app.application.use_cases.auth import RegisterUser
from app.application.use_cases.workspace_members import AddWorkspaceMember, ListScopedUsers
from app.domain.entities import User, UserRole
from app.ports.repositories import UserRepository
from app.ports.services import PasswordService
from app.ports.workspace_admin import WorkspaceAdminRepository
from app.schemas import UserOut, UserRoleUpdate

router = APIRouter(prefix="/admin/users", tags=["admin"])


def _to_user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        role=user.role,
        is_super_admin=user.is_super_admin,
        must_change_password=user.must_change_password,
    )


Users = Annotated[UserRepository, Depends(get_user_repo)]
Access = Annotated[WorkspaceAdminRepository, Depends(get_workspace_admin_repo)]
Scope = Annotated[AdminScope, Depends(get_admin_scope)]


class WorkspaceMemberCreate(BaseModel):
    """Inclui alguém num workspace: cria a conta USER ou só libera o acesso."""

    email: str = Field(max_length=320)
    password: str = Field(max_length=128)
    workspace_id: uuid.UUID


def _forbidden(exc: AdminScopeDeniedError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


def _get_update_role_uc(users: Users) -> UpdateUserRole:
    return UpdateUserRole(users)


@router.get("", response_model=list[UserOut])
async def list_users(scope: Scope, users: Users, access: Access) -> list[UserOut]:
    """ADMIN vê todos; admin de workspace, só quem tem acesso aos workspaces dele."""
    rows = await ListScopedUsers(users, access).execute(scope)
    return [_to_user_out(u) for u in rows]


@router.post("/workspace-member", response_model=UserOut)
async def add_workspace_member(
    body: WorkspaceMemberCreate,
    scope: Scope,
    users: Users,
    access: Access,
    register: Annotated[RegisterUser, Depends(get_register_uc)],
) -> UserOut:
    """Cria USER já com acesso ao workspace (ou só libera o acesso se o e-mail existir)."""
    try:
        result = await AddWorkspaceMember(users, access, register).execute(
            scope, email=body.email, password=body.password, workspace_id=body.workspace_id
        )
    except AdminScopeDeniedError as exc:
        raise _forbidden(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _to_user_out(result.user)


@router.patch(
    "/{user_id}/role",
    response_model=UserOut,
)
async def update_user_role(
    user_id: uuid.UUID,
    body: UserRoleUpdate,
    uc: Annotated[UpdateUserRole, Depends(_get_update_role_uc)],
    acting: Annotated[User, Depends(require_role(UserRole.ADMIN))],
) -> UserOut:
    """Altera o papel de um utilizador (ADMIN only).

    Impede auto-rebaixamento — um ADMIN não pode tornar-se USER sozinho.
    """
    try:
        updated = await uc.execute(user_id, body.role, acting_user_id=acting.id)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except CannotDemoteSelfError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except CannotChangeSuperAdminRoleError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return _to_user_out(updated)


def _get_reset_password_uc(
    users: Annotated[UserRepository, Depends(get_user_repo)],
    passwords: Annotated[PasswordService, Depends(get_password_service)],
) -> ResetUserPassword:
    # Senha temporária da redefinição; o usuário é obrigado a trocar no próximo login.
    return ResetUserPassword(users, passwords, os.getenv("ADMIN_RESET_PASSWORD", "12345678"))


@router.post("/{user_id}/reset-password", response_model=UserOut)
async def reset_user_password(
    user_id: uuid.UUID,
    uc: Annotated[ResetUserPassword, Depends(_get_reset_password_uc)],
    scope: Scope,
    users: Users,
    access: Access,
) -> UserOut:
    """Volta a senha para a temporária e marca a troca no próximo acesso.

    Super admin redefine de qualquer um; admin de workspace, só de USER dos
    workspaces que administra. ADMIN global comum continua sem essa ação.
    """
    if scope.is_global and not scope.is_super_admin:
        raise HTTPException(status_code=403, detail="Permissão de super admin necessária.")
    target = await users.get_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=404, detail=f"Utilizador {user_id} não encontrado.")
    try:
        await ensure_manageable_user(scope, target, access)
    except AdminScopeDeniedError as exc:
        raise _forbidden(exc) from exc
    try:
        updated = await uc.execute(user_id, acting_user_id=scope.user.id)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except CannotResetOwnPasswordError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _to_user_out(updated)
