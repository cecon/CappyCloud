"""Dependências base partilhadas entre ``deps.py`` e ``deps_attachments.py``.

Existe apenas para quebrar o ciclo de import: ambos os módulos precisam de
``get_db_session`` e ``get_conv_repo`` mas têm que importar um do outro.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.secondary.persistence.sqlalchemy_conversation_repo import (
    SQLAlchemyConversationRepository,
)
from app.infrastructure.database import get_db
from app.ports.repositories import ConversationRepository


async def get_db_session(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AsyncSession:
    return session


def get_conv_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ConversationRepository:
    return SQLAlchemyConversationRepository(session)
