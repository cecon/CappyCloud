"""Repositories admin HTTP router — CRUD de repos e disparo de sync no sandbox."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.deps import get_authenticated_user, get_db_session
from app.domain.entities import User
from app.infrastructure.encryption import get_encryptor
from app.infrastructure.orm_models import GitProvider, Repository, Sandbox, SandboxSyncQueue
from app.schemas import RepositoryCreate, RepositoryOut

router = APIRouter(prefix="/repositories", tags=["repositories"])


async def _decrypt_provider_token(
    session: AsyncSession, provider_id: uuid.UUID | None
) -> tuple[str, str]:
    """Devolve (token_em_claro, provider_type) ou ("", "") se sem provider/token."""
    if not provider_id:
        return "", ""
    provider = await session.get(GitProvider, provider_id)
    if not provider or not provider.token_encrypted:
        return "", provider.provider_type if provider else ""
    try:
        return get_encryptor().decrypt(provider.token_encrypted), provider.provider_type
    except Exception:
        return "", provider.provider_type


def _guess_provider_type(clone_url: str) -> str:
    """Heurística para deduzir provider_type a partir da URL."""
    u = (clone_url or "").lower()
    if "dev.azure.com" in u or "visualstudio.com" in u:
        return "azure_devops"
    if "github.com" in u:
        return "github"
    if "gitlab.com" in u:
        return "gitlab"
    if "bitbucket.org" in u:
        return "bitbucket"
    return "github"


async def _resolve_inline_pat(
    session: AsyncSession,
    repo_slug: str,
    clone_url: str,
    pat_token: str | None,
    provider_type_hint: str | None,
    existing_provider_id: uuid.UUID | None,
) -> uuid.UUID | None:
    """Cria/atualiza um GitProvider implícito quando o utilizador colou o PAT no form do repo.

    Estratégia:
    - Se já existe um provider associado, atualiza o token nele.
    - Senão, cria um provider com o nome ``auto-<slug>``.
    Retorna o ``provider_id`` a guardar no Repository.
    """
    if not pat_token or not pat_token.strip():
        return existing_provider_id

    enc = get_encryptor()
    ptype = (provider_type_hint or "").strip() or _guess_provider_type(clone_url)

    if existing_provider_id:
        provider = await session.get(GitProvider, existing_provider_id)
        if provider:
            provider.token_encrypted = enc.encrypt(pat_token.strip())
            if provider_type_hint:
                provider.provider_type = ptype
            return provider.id

    name = f"auto-{repo_slug}"
    provider = GitProvider(
        id=uuid.uuid4(),
        name=name,
        provider_type=ptype,
        base_url="",
        org_or_project="",
        token_encrypted=enc.encrypt(pat_token.strip()),
    )
    session.add(provider)
    await session.flush()
    return provider.id


async def _enqueue_clone(
    session: AsyncSession,
    repo: Repository,
    *,
    priority: int = 5,
) -> None:
    """Enfileira clone_repo no sandbox_sync_queue com token (se houver provider)."""
    if not repo.sandbox_id:
        return
    token, provider_type = await _decrypt_provider_token(session, repo.provider_id)
    payload: dict = {
        "slug": repo.slug,
        "clone_url": repo.clone_url,
        "default_branch": repo.default_branch,
    }
    if token:
        payload["token"] = token
        payload["provider_type"] = provider_type
    session.add(
        SandboxSyncQueue(
            id=uuid.uuid4(),
            sandbox_id=repo.sandbox_id,
            operation="clone_repo",
            payload=payload,
            priority=priority,
        )
    )


@router.get("", response_model=list[RepositoryOut])
async def list_repositories(
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[RepositoryOut]:
    rows = await session.execute(select(Repository).order_by(Repository.name))
    return [RepositoryOut.model_validate(r) for r in rows.scalars()]


@router.post("", response_model=RepositoryOut, status_code=201)
async def create_repository(
    body: RepositoryCreate,
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RepositoryOut:
    sandbox_id = body.sandbox_id
    if sandbox_id is None:
        row = await session.execute(
            select(Sandbox).where(Sandbox.status == "active").order_by(Sandbox.created_at).limit(1)
        )
        default_sandbox = row.scalar_one_or_none()
        if default_sandbox:
            sandbox_id = default_sandbox.id

    provider_id = await _resolve_inline_pat(
        session,
        repo_slug=body.slug,
        clone_url=body.clone_url,
        pat_token=body.pat_token,
        provider_type_hint=body.provider_type,
        existing_provider_id=body.provider_id,
    )

    repo = Repository(
        id=uuid.uuid4(),
        slug=body.slug,
        name=body.name,
        clone_url=body.clone_url,
        default_branch=body.default_branch,
        provider_id=provider_id,
        sandbox_id=sandbox_id,
    )
    session.add(repo)
    await session.flush()
    await _enqueue_clone(session, repo, priority=5)
    await session.commit()
    await session.refresh(repo)
    return RepositoryOut.model_validate(repo)


@router.patch("/{repo_id}", response_model=RepositoryOut)
async def update_repository(
    repo_id: uuid.UUID,
    body: RepositoryCreate,
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RepositoryOut:
    """Atualiza o repositório (em particular, permite associar provider_id ou PAT inline)."""
    repo = await session.get(Repository, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repositório não encontrado")

    new_provider_id = await _resolve_inline_pat(
        session,
        repo_slug=body.slug,
        clone_url=body.clone_url,
        pat_token=body.pat_token,
        provider_type_hint=body.provider_type,
        existing_provider_id=body.provider_id or repo.provider_id,
    )

    repo.slug = body.slug
    repo.name = body.name
    repo.clone_url = body.clone_url
    repo.default_branch = body.default_branch
    repo.provider_id = new_provider_id
    if body.sandbox_id:
        repo.sandbox_id = body.sandbox_id
    await session.flush()
    await _enqueue_clone(session, repo, priority=5)
    await session.commit()
    await session.refresh(repo)
    return RepositoryOut.model_validate(repo)


@router.post("/{repo_id}/sync", status_code=202)
async def enqueue_sync(
    repo_id: uuid.UUID,
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """Enfileira clone/update do repo no sandbox via sandbox_sync_queue."""
    repo = await session.get(Repository, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repositório não encontrado")
    if not repo.sandbox_id:
        raise HTTPException(status_code=400, detail="Repositório não possui sandbox associado")
    await _enqueue_clone(session, repo, priority=5)
    await session.commit()
    return {"queued": True}


@router.delete("/{repo_id}", status_code=204)
async def delete_repository(
    repo_id: uuid.UUID,
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    repo = await session.get(Repository, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repositório não encontrado")

    if repo.sandbox_id and repo.sandbox_status == "cloned":
        item = SandboxSyncQueue(
            id=uuid.uuid4(),
            sandbox_id=repo.sandbox_id,
            operation="remove_repo",
            payload={"slug": repo.slug, "sandbox_path": repo.sandbox_path},
            priority=3,
        )
        session.add(item)

    await session.delete(repo)
    await session.commit()
