"""HTTP adapter for authentication endpoints — thin glue only."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.adapters.primary.http.deps import (
    get_authenticated_user,
    get_change_password_uc,
    get_login_uc,
    get_register_uc,
    require_role,
)
from app.application.use_cases.auth import ChangePassword, LoginUser, RegisterUser
from app.domain.entities import User, UserRole
from app.schemas import PasswordChangeBody, Token, UserCreate, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _to_user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        role=user.role,
        is_super_admin=user.is_super_admin,
        must_change_password=user.must_change_password,
    )


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    body: UserCreate,
    uc: Annotated[RegisterUser, Depends(get_register_uc)],
    _admin: Annotated[User, Depends(require_role(UserRole.ADMIN))],
) -> UserOut:
    """Regista um novo utilizador. Apenas ADMINs (ADR-005).

    O primeiro ADMIN é criado por seed (``scripts/seed_first_admin.py`` ou
    variáveis ``FIRST_ADMIN_EMAIL``/``FIRST_ADMIN_PASSWORD`` no boot).
    """
    try:
        user = await uc.execute(
            body.email,
            body.password,
            body.role,
            must_change_password=body.must_change_password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _to_user_out(user)


@router.post("/login", response_model=Token)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    uc: Annotated[LoginUser, Depends(get_login_uc)],
) -> Token:
    """Autentica utilizador e devolve JWT."""
    try:
        token = await uc.execute(form.username, form.password)
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return Token(access_token=token)


@router.get("/me", response_model=UserOut)
async def me(
    current: Annotated[User, Depends(get_authenticated_user)],
) -> UserOut:
    """Devolve dados do utilizador autenticado, incluindo o papel."""
    return _to_user_out(current)


@router.post("/change-password", response_model=UserOut)
async def change_password(
    body: PasswordChangeBody,
    current: Annotated[User, Depends(get_authenticated_user)],
    uc: Annotated[ChangePassword, Depends(get_change_password_uc)],
) -> UserOut:
    """Troca a senha do utilizador autenticado e libera o primeiro acesso."""
    try:
        updated = await uc.execute(current.id, body.current_password, body.new_password)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _to_user_out(updated)
