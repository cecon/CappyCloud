"""HTTP adapter administrativo para permissões binárias (ADR-005 §2).

Rotas (todas ADMIN):

- GET    /admin/users/{user_id}/access/sandboxes
- POST   /admin/users/{user_id}/access/sandboxes/{sandbox_id}
- DELETE /admin/users/{user_id}/access/sandboxes/{sandbox_id}

(análogos para ``repositories`` e ``ai-models``)

- POST   /admin/users/{user_id}/access/ai-models/bulk-tier
        body: { "tier": "free" | "paid" | "unknown" }
        Libera todos os modelos ativos daquele tier (ADR-006 §3).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.deps import require_role
from app.adapters.primary.http.deps_base import get_db_session
from app.adapters.secondary.persistence.sqlalchemy_models_by_tier import (
    SQLAlchemyModelsByTierLookup,
)
from app.adapters.secondary.persistence.sqlalchemy_user_access_repo import (
    SQLAlchemyUserAiModelAccessRepository,
    SQLAlchemyUserRepositoryAccessRepository,
    SQLAlchemyUserSandboxAccessRepository,
)
from app.application.use_cases.admin_user_access import (
    BulkGrantAiModelsByTier,
    GrantAiModelAccess,
    GrantRepositoryAccess,
    GrantSandboxAccess,
    ListUserAiModelAccess,
    ListUserRepositoryAccess,
    ListUserSandboxAccess,
    ModelsByTierLookup,
    RevokeAiModelAccess,
    RevokeRepositoryAccess,
    RevokeSandboxAccess,
)
from app.domain.entities import ModelTier, UserRole
from app.ports.user_access import (
    UserAiModelAccessRepository,
    UserRepositoryAccessRepository,
    UserSandboxAccessRepository,
)

router = APIRouter(
    prefix="/admin/users/{user_id}/access",
    tags=["admin"],
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)


# ── Repository factories (overridable em testes via dependency_overrides) ────


def get_sandbox_access_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserSandboxAccessRepository:
    return SQLAlchemyUserSandboxAccessRepository(session)


def get_repository_access_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserRepositoryAccessRepository:
    return SQLAlchemyUserRepositoryAccessRepository(session)


def get_ai_model_access_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserAiModelAccessRepository:
    return SQLAlchemyUserAiModelAccessRepository(session)


def get_models_by_tier_lookup(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ModelsByTierLookup:
    return SQLAlchemyModelsByTierLookup(session)


# ── Sandboxes ───────────────────────────────────────────────────────────────


@router.get("/sandboxes", response_model=list[uuid.UUID])
async def list_sandbox_access(
    user_id: uuid.UUID,
    repo: Annotated[UserSandboxAccessRepository, Depends(get_sandbox_access_repo)],
) -> list[uuid.UUID]:
    return await ListUserSandboxAccess(repo).execute(user_id)


@router.post("/sandboxes/{sandbox_id}", status_code=status.HTTP_204_NO_CONTENT)
async def grant_sandbox_access(
    user_id: uuid.UUID,
    sandbox_id: uuid.UUID,
    repo: Annotated[UserSandboxAccessRepository, Depends(get_sandbox_access_repo)],
) -> None:
    await GrantSandboxAccess(repo).execute(user_id, sandbox_id)


@router.delete("/sandboxes/{sandbox_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_sandbox_access(
    user_id: uuid.UUID,
    sandbox_id: uuid.UUID,
    repo: Annotated[UserSandboxAccessRepository, Depends(get_sandbox_access_repo)],
) -> None:
    deleted = await RevokeSandboxAccess(repo).execute(user_id, sandbox_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Acesso não existia.")


# ── Repositories ────────────────────────────────────────────────────────────


@router.get("/repositories", response_model=list[uuid.UUID])
async def list_repository_access(
    user_id: uuid.UUID,
    repo: Annotated[UserRepositoryAccessRepository, Depends(get_repository_access_repo)],
) -> list[uuid.UUID]:
    return await ListUserRepositoryAccess(repo).execute(user_id)


@router.post("/repositories/{repository_id}", status_code=status.HTTP_204_NO_CONTENT)
async def grant_repository_access(
    user_id: uuid.UUID,
    repository_id: uuid.UUID,
    repo: Annotated[UserRepositoryAccessRepository, Depends(get_repository_access_repo)],
) -> None:
    await GrantRepositoryAccess(repo).execute(user_id, repository_id)


@router.delete("/repositories/{repository_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_repository_access(
    user_id: uuid.UUID,
    repository_id: uuid.UUID,
    repo: Annotated[UserRepositoryAccessRepository, Depends(get_repository_access_repo)],
) -> None:
    deleted = await RevokeRepositoryAccess(repo).execute(user_id, repository_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Acesso não existia.")


# ── AI Models ───────────────────────────────────────────────────────────────


class BulkTierBody(BaseModel):
    tier: ModelTier


class BulkTierResult(BaseModel):
    granted: int


@router.get("/ai-models", response_model=list[uuid.UUID])
async def list_ai_model_access(
    user_id: uuid.UUID,
    repo: Annotated[UserAiModelAccessRepository, Depends(get_ai_model_access_repo)],
) -> list[uuid.UUID]:
    return await ListUserAiModelAccess(repo).execute(user_id)


# ATENÇÃO: ``bulk-tier`` precisa ser declarado ANTES da rota com ``{ai_model_id}``
# senão o FastAPI tenta interpretar "bulk-tier" como UUID e devolve 422.
@router.post("/ai-models/bulk-tier", response_model=BulkTierResult)
async def bulk_grant_ai_models_by_tier(
    user_id: uuid.UUID,
    body: BulkTierBody,
    repo: Annotated[UserAiModelAccessRepository, Depends(get_ai_model_access_repo)],
    lookup: Annotated[ModelsByTierLookup, Depends(get_models_by_tier_lookup)],
) -> BulkTierResult:
    granted = await BulkGrantAiModelsByTier(repo, lookup).execute(user_id, body.tier)
    return BulkTierResult(granted=granted)


@router.post("/ai-models/{ai_model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def grant_ai_model_access(
    user_id: uuid.UUID,
    ai_model_id: uuid.UUID,
    repo: Annotated[UserAiModelAccessRepository, Depends(get_ai_model_access_repo)],
) -> None:
    await GrantAiModelAccess(repo).execute(user_id, ai_model_id)


@router.delete("/ai-models/{ai_model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_ai_model_access(
    user_id: uuid.UUID,
    ai_model_id: uuid.UUID,
    repo: Annotated[UserAiModelAccessRepository, Depends(get_ai_model_access_repo)],
) -> None:
    deleted = await RevokeAiModelAccess(repo).execute(user_id, ai_model_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Acesso não existia.")
