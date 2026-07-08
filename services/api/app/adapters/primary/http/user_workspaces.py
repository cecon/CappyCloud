"""HTTP adapter for current-user repository workspace baselines."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.adapters.primary.http.deps import (
    get_authenticated_user,
    get_delete_user_workspace_uc,
    get_ensure_user_workspace_uc,
    get_list_user_workspaces_uc,
)
from app.application.use_cases.user_workspaces import (
    DeleteUserRepositoryWorkspace,
    EnsureUserRepositoryWorkspace,
    ListUserRepositoryWorkspaces,
    UserWorkspaceAccessDeniedError,
    UserWorkspaceNotFoundError,
)
from app.domain.entities import User
from app.schemas_user_workspaces import UserWorkspaceEnsureBody, UserWorkspaceOut

router = APIRouter(prefix="/user-workspaces", tags=["user-workspaces"])


@router.get("", response_model=list[UserWorkspaceOut])
async def list_user_workspaces(
    current: Annotated[User, Depends(get_authenticated_user)],
    uc: Annotated[ListUserRepositoryWorkspaces, Depends(get_list_user_workspaces_uc)],
) -> list[UserWorkspaceOut]:
    items = await uc.execute(current_user=current)
    return [UserWorkspaceOut.model_validate(item) for item in items]


@router.post("/ensure", response_model=UserWorkspaceOut)
async def ensure_user_workspace(
    body: UserWorkspaceEnsureBody,
    current: Annotated[User, Depends(get_authenticated_user)],
    uc: Annotated[EnsureUserRepositoryWorkspace, Depends(get_ensure_user_workspace_uc)],
) -> UserWorkspaceOut:
    try:
        workspace = await uc.execute(
            current_user=current,
            repository_id=body.repository_id,
            base_branch=body.base_branch,
        )
    except UserWorkspaceAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except UserWorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return UserWorkspaceOut.model_validate(workspace)


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_workspace(
    workspace_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    uc: Annotated[DeleteUserRepositoryWorkspace, Depends(get_delete_user_workspace_uc)],
) -> None:
    try:
        await uc.execute(current_user=current, workspace_id=workspace_id)
    except UserWorkspaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
