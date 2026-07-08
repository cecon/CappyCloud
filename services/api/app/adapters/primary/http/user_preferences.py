"""HTTP adapter for authenticated user preferences."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.adapters.primary.http.deps import (
    get_authenticated_user,
    get_update_user_preferences_uc,
    get_user_preferences_uc,
)
from app.application.use_cases.user_preferences import (
    GetUserPreferences,
    UpdateUserPreferences,
)
from app.domain.entities import User
from app.schemas import UserPreferencesOut, UserPreferencesUpdate

router = APIRouter(prefix="/user/preferences", tags=["user-preferences"])


@router.get("", response_model=UserPreferencesOut)
async def get_preferences(
    current: Annotated[User, Depends(get_authenticated_user)],
    uc: Annotated[GetUserPreferences, Depends(get_user_preferences_uc)],
) -> UserPreferencesOut:
    prefs = await uc.execute(current.id)
    return UserPreferencesOut(default_permission_mode=prefs.default_permission_mode)


@router.patch("", response_model=UserPreferencesOut)
async def update_preferences(
    body: UserPreferencesUpdate,
    current: Annotated[User, Depends(get_authenticated_user)],
    uc: Annotated[UpdateUserPreferences, Depends(get_update_user_preferences_uc)],
) -> UserPreferencesOut:
    prefs = await uc.execute(
        current.id,
        default_permission_mode=body.default_permission_mode,
    )
    return UserPreferencesOut(default_permission_mode=prefs.default_permission_mode)
