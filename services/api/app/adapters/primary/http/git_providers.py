"""Git Providers HTTP router — CRUD de provedores git com tokens criptografados."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.deps import get_authenticated_user, get_db_session
from app.domain.entities import User
from app.infrastructure.encryption import get_encryptor
from app.infrastructure.orm_models import GitProvider
from app.schemas import GitProviderCreate, GitProviderOut

router = APIRouter(prefix="/git-providers", tags=["git-providers"])


@router.get("", response_model=list[GitProviderOut])
async def list_git_providers(
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[GitProviderOut]:
    rows = await session.execute(select(GitProvider).order_by(GitProvider.created_at))
    return [GitProviderOut.model_validate(r) for r in rows.scalars()]


@router.post("", response_model=GitProviderOut, status_code=201)
async def create_git_provider(
    body: GitProviderCreate,
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> GitProviderOut:
    enc = get_encryptor()
    provider = GitProvider(
        id=uuid.uuid4(),
        name=body.name,
        provider_type=body.provider_type,
        base_url=body.base_url,
        org_or_project=body.org_or_project,
        token_encrypted=enc.encrypt(body.token) if body.token else "",
    )
    session.add(provider)
    await session.commit()
    await session.refresh(provider)
    return GitProviderOut.model_validate(provider)


@router.patch("/{provider_id}/token", response_model=GitProviderOut)
async def update_token(
    provider_id: uuid.UUID,
    token: str,
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> GitProviderOut:
    provider = await session.get(GitProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider não encontrado")
    provider.token_encrypted = get_encryptor().encrypt(token)
    await session.commit()
    await session.refresh(provider)
    return GitProviderOut.model_validate(provider)


@router.delete("/{provider_id}", status_code=204)
async def delete_git_provider(
    provider_id: uuid.UUID,
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    provider = await session.get(GitProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider não encontrado")
    await session.delete(provider)
    await session.commit()
