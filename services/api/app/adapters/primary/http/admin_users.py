"""HTTP adapter para gestão administrativa de utilizadores (ADR-005).

Todas as rotas exigem papel ADMIN. Glue fino: parse → use case → serialize.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.adapters.primary.http.deps import get_user_repo, require_role
from app.application.use_cases.admin_users import (
    CannotChangeSuperAdminRoleError,
    CannotDemoteSelfError,
    ListUsers,
    UpdateUserRole,
    UserNotFoundError,
)
from app.domain.entities import User, UserRole
from app.ports.repositories import UserRepository
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


def _get_list_users_uc(
    users: Annotated[UserRepository, Depends(get_user_repo)],
) -> ListUsers:
    return ListUsers(users)


def _get_update_role_uc(
    users: Annotated[UserRepository, Depends(get_user_repo)],
) -> UpdateUserRole:
    return UpdateUserRole(users)


@router.get(
    "",
    response_model=list[UserOut],
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
async def list_users(
    uc: Annotated[ListUsers, Depends(_get_list_users_uc)],
) -> list[UserOut]:
    """Lista todos os utilizadores (ADMIN only)."""
    rows = await uc.execute()
    return [_to_user_out(u) for u in rows]


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
