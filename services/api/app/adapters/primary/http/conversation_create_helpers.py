"""Apoio à criação de conversas: modelo de IA e conversas por workspace."""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.adapters.primary.http.conversation_sandbox_guard import ensure_sandbox_ready_for_chat
from app.adapters.secondary.persistence.sqlalchemy_ai_model_access_policy import (
    SQLAlchemyAiModelAccessPolicy,
)
from app.application.use_cases.conversations import CreateConversation
from app.domain.entities import Conversation, User, UserRole
from app.infrastructure.orm_models_platform import AiModel
from app.infrastructure.orm_models_workspaces import (
    UserWorkspaceAccess,
    Workspace,
    WorkspaceRepository,
)
from app.schemas import ConversationCreate, ConversationOut


async def resolve_ai_model_id(
    session: AsyncSession, current: User, model_id: str | None
) -> uuid.UUID | None:
    """Valida o modelo pedido contra o acesso do utilizador e devolve o id ativo."""
    if not model_id:
        return None
    try:
        resolved = await SQLAlchemyAiModelAccessPolicy(session).resolve_model_for_user(
            current.id, current.role, model_id
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    ai_model_id = (
        await session.execute(
            select(AiModel.id)
            .where(AiModel.model_id == resolved, AiModel.active.is_(True))
            .limit(1)
        )
    ).scalar_one_or_none()
    if ai_model_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Modelo LLM indisponível ou desativado globalmente.",
        )
    return ai_model_id


async def create_workspace_conversation(
    session: AsyncSession,
    current: User,
    uc: CreateConversation,
    body: ConversationCreate,
) -> Conversation:
    """Conversa num workspace: abre todos os repositórios dele, na sandbox dele."""
    ws = (
        await session.execute(
            select(Workspace)
            .where(Workspace.id == body.workspace_id)
            .options(
                selectinload(Workspace.repositories).selectinload(WorkspaceRepository.repository)
            )
        )
    ).scalar_one_or_none()
    if ws is None or not ws.active:
        raise HTTPException(status_code=404, detail="Workspace não encontrado.")
    if current.role is not UserRole.ADMIN:
        granted = await session.execute(
            select(UserWorkspaceAccess.id).where(
                UserWorkspaceAccess.user_id == current.id,
                UserWorkspaceAccess.workspace_id == ws.id,
            )
        )
        if granted.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Sem acesso a este workspace."
            )
    if not ws.repositories:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Workspace sem repositórios."
        )
    if ws.sync_status != "synced":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Workspace ainda não foi sincronizado no sandbox. Tente em instantes.",
        )

    await ensure_sandbox_ready_for_chat(session, ws.sandbox_id)
    ai_model_id = await resolve_ai_model_id(session, current, body.model_id)
    repos = [
        {
            "slug": link.repository.slug,
            "alias": link.alias,
            "base_branch": link.base_branch or link.repository.default_branch,
            "read_only": link.read_only,
        }
        for link in ws.repositories
    ]
    return await uc.execute(
        current.id,
        title=body.title,
        sandbox_id=ws.sandbox_id,
        ai_model_id=ai_model_id,
        repos=repos,
        workspace_id=ws.id,
        workspace_slug=ws.slug,
    )


def conversation_out(conv: Conversation) -> ConversationOut:
    return ConversationOut(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        sandbox_id=conv.sandbox_id,
        ai_model_id=conv.ai_model_id,
        repos=conv.repos,
        session_root=conv.session_root,
        workspace_id=conv.workspace_id,
        permission_mode=conv.permission_mode,
    )
