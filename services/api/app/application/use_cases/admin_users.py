"""Use cases administrativos para gestão de utilizadores (ADR-005).

Apenas ADMINs chamam estes use cases — o gating de papel é responsabilidade
da camada HTTP (``require_role(UserRole.ADMIN)``). Aqui validamos apenas as
invariantes de domínio:

- Não permitir que um ADMIN se rebaixe a si mesmo (evita lockout).
- Não permitir alterar o papel de um utilizador inexistente.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from app.domain.entities import User, UserRole
from app.ports.repositories import UserRepository
from app.ports.services import PasswordService


class UserNotFoundError(Exception):
    """O id solicitado não existe na tabela ``users``."""


class CannotDemoteSelfError(Exception):
    """ADMIN tentou rebaixar a si mesmo — bloqueado para evitar lockout."""


class CannotChangeSuperAdminRoleError(Exception):
    """Tentativa de alterar papel de SUPER ADMIN por outro utilizador."""


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

        current = await self._users.get_by_id(target_user_id)
        if current is None:
            raise UserNotFoundError(f"Utilizador {target_user_id} não encontrado.")
        if current.is_super_admin and target_user_id != acting_user_id:
            raise CannotChangeSuperAdminRoleError(
                "Papel de SUPER ADMIN não pode ser alterado por outro administrador."
            )

        updated = await self._users.update_role(target_user_id, new_role)
        if updated is None:
            raise UserNotFoundError(f"Utilizador {target_user_id} não encontrado.")
        return updated


RESET_PASSWORD_TTL = timedelta(hours=24)


class CannotResetOwnPasswordError(Exception):
    """Super admin tentando redefinir a própria senha pelo admin."""


class ResetUserPassword:
    """Volta a senha do usuário para a senha temporária padrão e obriga a troca.

    A senha temporária vale 24 h; depois o login é recusado até nova redefinição.

    No próximo login o usuário cai na tela de definir senha nova (o bloqueio de
    ``must_change_password`` vale em toda a API até a troca).
    """

    def __init__(
        self, users: UserRepository, passwords: PasswordService, temporary_password: str
    ) -> None:
        self._users = users
        self._passwords = passwords
        self._temporary_password = temporary_password

    async def execute(self, user_id: uuid.UUID, acting_user_id: uuid.UUID) -> User:
        if user_id == acting_user_id:
            raise CannotResetOwnPasswordError("Use 'Trocar senha' para mudar a sua própria senha.")
        updated = await self._users.update_password(
            user_id,
            self._passwords.hash(self._temporary_password),
            must_change_password=True,
            reset_expires_at=datetime.now(UTC) + RESET_PASSWORD_TTL,
        )
        if updated is None:
            raise UserNotFoundError(f"Utilizador {user_id} não encontrado.")
        return updated
