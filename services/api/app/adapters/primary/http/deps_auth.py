"""Authentication and authorization dependencies for HTTP adapters."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.secondary.persistence.sqlalchemy_user_repo import SQLAlchemyUserRepository
from app.adapters.secondary.persistence.sqlalchemy_workspace_admin_repo import (
    SQLAlchemyWorkspaceAdminRepository,
)
from app.application.use_cases.admin_scope import (
    AdminScope,
    AdminScopeDeniedError,
    ResolveAdminScope,
)
from app.application.use_cases.auth import ChangePassword, GetCurrentUser, LoginUser, RegisterUser
from app.domain.entities import User, UserRole
from app.ports.repositories import UserRepository
from app.ports.services import PasswordService, TokenService
from app.ports.workspace_admin import WorkspaceAdminRepository

from .deps_base import get_db_session

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_user_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserRepository:
    return SQLAlchemyUserRepository(session)


def get_password_service() -> PasswordService:
    from app.infrastructure.security import BcryptPasswordService

    return BcryptPasswordService()


def get_token_service() -> TokenService:
    from app.infrastructure.security import JWTTokenService

    return JWTTokenService()


def get_register_uc(
    users: Annotated[UserRepository, Depends(get_user_repo)],
    passwords: Annotated[PasswordService, Depends(get_password_service)],
) -> RegisterUser:
    return RegisterUser(users, passwords)


def get_login_uc(
    users: Annotated[UserRepository, Depends(get_user_repo)],
    passwords: Annotated[PasswordService, Depends(get_password_service)],
    tokens: Annotated[TokenService, Depends(get_token_service)],
) -> LoginUser:
    return LoginUser(users, passwords, tokens)


def get_current_user_uc(
    users: Annotated[UserRepository, Depends(get_user_repo)],
    tokens: Annotated[TokenService, Depends(get_token_service)],
) -> GetCurrentUser:
    return GetCurrentUser(users, tokens)


def get_change_password_uc(
    users: Annotated[UserRepository, Depends(get_user_repo)],
    passwords: Annotated[PasswordService, Depends(get_password_service)],
) -> ChangePassword:
    return ChangePassword(users, passwords)


async def get_authenticated_user(
    request: Request,
    token: Annotated[str, Depends(oauth2_scheme)],
    uc: Annotated[GetCurrentUser, Depends(get_current_user_uc)],
) -> User:
    try:
        user = await uc.execute(token)
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    if user.must_change_password and request.url.path not in {
        "/api/auth/me",
        "/api/auth/change-password",
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Troque a senha inicial antes de continuar.",
        )
    return user


def require_role(required: UserRole):
    async def _dep(
        current: Annotated[User, Depends(get_authenticated_user)],
    ) -> User:
        if current.role is UserRole.ADMIN or current.role is required:
            return current
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permissão insuficiente.",
        )

    return _dep


def get_workspace_admin_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> WorkspaceAdminRepository:
    return SQLAlchemyWorkspaceAdminRepository(session)


async def get_admin_scope(
    current: Annotated[User, Depends(get_authenticated_user)],
    repo: Annotated[WorkspaceAdminRepository, Depends(get_workspace_admin_repo)],
) -> AdminScope:
    """ADMIN global ou admin de workspace; qualquer outro recebe 403."""
    try:
        return await ResolveAdminScope(repo).execute(current)
    except AdminScopeDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


def _ensure_allows(scope: AdminScope, workspace_id: uuid.UUID) -> AdminScope:
    if not scope.allows(workspace_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Você não administra este workspace."
        )
    return scope


async def require_workspace_in_scope(
    workspace_id: uuid.UUID,
    scope: Annotated[AdminScope, Depends(get_admin_scope)],
) -> AdminScope:
    """Para rotas com ``{workspace_id}`` no caminho: ADMIN global ou admin dele."""
    return _ensure_allows(scope, workspace_id)


async def get_workspace_manager_scope(
    scope: Annotated[AdminScope, Depends(get_admin_scope)],
) -> AdminScope:
    """Super admin ou admin de workspace: ADMIN global comum nunca geriu workspaces."""
    if scope.is_global and not scope.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permissão de super admin necessária."
        )
    return scope


async def require_workspace_manager(
    workspace_id: uuid.UUID,
    scope: Annotated[AdminScope, Depends(get_workspace_manager_scope)],
) -> AdminScope:
    """Configuração do workspace (CLAUDE.md, conhecimento): super admin ou admin dele."""
    return _ensure_allows(scope, workspace_id)


async def require_super_admin(
    current: Annotated[User, Depends(get_authenticated_user)],
) -> User:
    if current.role is UserRole.ADMIN and current.is_super_admin:
        return current
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Permissão de super admin necessária.",
    )
