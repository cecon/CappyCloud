"""HTTP adapter for agentic delivery sensitive surfaces."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.adapters.primary.http.deps import get_authenticated_user
from app.adapters.primary.http.deps_agentic_delivery import get_manage_sensitive_surfaces_uc
from app.application.use_cases.agentic_delivery_review import ManageSensitiveSurfaces
from app.domain.entities import User
from app.schemas_agentic_delivery import (
    SensitiveSurfaceListResponse,
    SensitiveSurfaceOut,
    SensitiveSurfaceRequest,
)

router = APIRouter(prefix="/agentic-cycles", tags=["agentic-delivery"])


@router.put("/sensitive-surfaces/{surface_id}", response_model=SensitiveSurfaceOut)
async def save_sensitive_surface(
    surface_id: uuid.UUID,
    body: SensitiveSurfaceRequest,
    current: Annotated[User, Depends(get_authenticated_user)],
    uc: Annotated[ManageSensitiveSurfaces, Depends(get_manage_sensitive_surfaces_uc)],
) -> SensitiveSurfaceOut:
    try:
        row = await uc.save(surface_id, body.model_dump(), current)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return SensitiveSurfaceOut(**row)


@router.get("/sensitive-surfaces", response_model=SensitiveSurfaceListResponse)
async def list_sensitive_surfaces(
    uc: Annotated[ManageSensitiveSurfaces, Depends(get_manage_sensitive_surfaces_uc)],
    _current: Annotated[User, Depends(get_authenticated_user)],
    repository_id: Annotated[uuid.UUID | None, Query()] = None,
    domain_key: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query()] = None,
) -> SensitiveSurfaceListResponse:
    return SensitiveSurfaceListResponse(**await uc.list(repository_id, domain_key, limit, cursor))
