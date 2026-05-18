"""SQLAlchemy adapters para os 3 ``UserAccessRepository`` (ADR-005 §2).

Os 3 são quase iguais — só mudam a tabela ORM e o nome da coluna de
recurso. Em vez de repetir, define uma classe genérica e 3 subclasses fixam
os atributos.
"""

from __future__ import annotations

import uuid
from typing import Any, ClassVar

from sqlalchemy import delete, insert, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.orm_models_access import (
    UserAiModelAccess as UserAiModelAccessORM,
)
from app.infrastructure.orm_models_access import (
    UserRepositoryAccess as UserRepositoryAccessORM,
)
from app.infrastructure.orm_models_access import (
    UserSandboxAccess as UserSandboxAccessORM,
)
from app.ports.user_access import (
    UserAiModelAccessRepository,
    UserRepositoryAccessRepository,
    UserSandboxAccessRepository,
)


class _BaseSqlAccess:
    """Lógica compartilhada. As subclasses fixam ``_orm`` e ``_resource_col``."""

    _orm: ClassVar[Any]
    _resource_col: ClassVar[str]

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _resource_attr(self) -> Any:
        return getattr(self._orm, self._resource_col)

    async def list_resources_for_user(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        col = self._resource_attr()
        result = await self._session.execute(select(col).where(self._orm.user_id == user_id))
        return list(result.scalars().all())

    async def has_access(self, user_id: uuid.UUID, resource_id: uuid.UUID) -> bool:
        col = self._resource_attr()
        result = await self._session.execute(
            select(self._orm.id).where(self._orm.user_id == user_id, col == resource_id)
        )
        return result.scalar_one_or_none() is not None

    async def grant(self, user_id: uuid.UUID, resource_id: uuid.UUID) -> None:
        # Idempotência: tenta inserir; se viola unique, ignora.
        stmt = insert(self._orm).values(
            id=uuid.uuid4(),
            user_id=user_id,
            **{self._resource_col: resource_id},
        )
        try:
            await self._session.execute(stmt)
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()

    async def revoke(self, user_id: uuid.UUID, resource_id: uuid.UUID) -> bool:
        col = self._resource_attr()
        result: CursorResult = await self._session.execute(  # type: ignore[assignment]
            delete(self._orm).where(self._orm.user_id == user_id, col == resource_id)
        )
        await self._session.commit()
        return result.rowcount > 0


class SQLAlchemyUserSandboxAccessRepository(_BaseSqlAccess, UserSandboxAccessRepository):
    _orm = UserSandboxAccessORM
    _resource_col = "sandbox_id"


class SQLAlchemyUserRepositoryAccessRepository(_BaseSqlAccess, UserRepositoryAccessRepository):
    _orm = UserRepositoryAccessORM
    _resource_col = "repository_id"


class SQLAlchemyUserAiModelAccessRepository(_BaseSqlAccess, UserAiModelAccessRepository):
    _orm = UserAiModelAccessORM
    _resource_col = "ai_model_id"
