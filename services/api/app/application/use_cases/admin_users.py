"""Use cases administrativos para gestão de utilizadores (ADR-005).

Apenas ADMINs chamam estes use cases — o gating de papel é responsabilidade
da camada HTTP (``require_role(UserRole.ADMIN)``). Aqui validamos apenas as
invariantes de domínio:

- Não permitir que um ADMIN se rebaixe a si mesmo (evita lockout).
- Não permitir alterar o papel de um utilizador inexistente.
"""

from __future__ import annotations

import uuid

from app.domain.entities import User, UserRole
from app.ports.repositories import UserRepository


class UserNotFoundError(Exception):
    """O id solicitado não existe na tabela ``users``."""


class CannotDemoteSelfError(Exception):
    """ADMIN tentou rebaixar a si mesmo — bloqueado para evitar lockout."""


class ListUsers:
    """Lista todos os utilizadores. Ordem cronológica de criação."""

    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def execute(self) -> list[User]:
        return await self._users.list_all()


class UpdateUserRole:
    """Promove ou rebaixa o papel de um utilizador.

    O ``acting_user_id`` é quem está a executar a operação — necessário para
    impedir auto-rebaixamento (não há mecanismo de "reverter" se um ADMIN
    cair em USER e ninguém mais é ADMIN).
    """

    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def execute(
        self,
        target_user_id: uuid.UUID,
        new_role: UserRole,
        *,
        acting_user_id: uuid.UUID,
    ) -> User:
        if target_user_id == acting_user_id and new_role is not UserRole.ADMIN:
            raise CannotDemoteSelfError("Você não pode rebaixar a si mesmo. Peça a outro ADMIN.")

        updated = await self._users.update_role(target_user_id, new_role)
        if updated is None:
            raise UserNotFoundError(f"Utilizador {target_user_id} não encontrado.")
        return updated
