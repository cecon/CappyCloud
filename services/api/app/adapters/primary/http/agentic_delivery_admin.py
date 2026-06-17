"""Admin HTTP adapter for agentic delivery controls."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.adapters.primary.http.deps import get_authenticated_user, require_role
from app.adapters.primary.http.deps_agentic_delivery import get_manage_agentic_permissions_uc
from app.application.use_cases.agentic_delivery_review import ManageAgenticDeliveryPermissions
from app.domain.entities import User, UserRole
from app.schemas_agentic_delivery import (
    AgenticDeliveryPermissionRequest,
    AgenticDeliveryPermissionResponse,
)

router = APIRouter(prefix="/admin/agentic-delivery", tags=["admin-agentic-delivery"])


@router.put(
    "/permissions/{permission_id}",
    response_model=AgenticDeliveryPermissionResponse,
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
async def upsert_permission(
    permission_id: uuid.UUID,
    body: AgenticDeliveryPermissionRequest,
    current: Annotated[User, Depends(get_authenticated_user)],
    uc: Annotated[ManageAgenticDeliveryPermissions, Depends(get_manage_agentic_permissions_uc)],
) -> AgenticDeliveryPermissionResponse:
    try:
        row = await uc.upsert(permission_id, current.id, body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return AgenticDeliveryPermissionResponse(**row)
