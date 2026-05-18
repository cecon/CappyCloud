"""Seed inicial do primeiro ADMIN — use case puro (sem FastAPI nem ORM).

Idempotente por email: se o email já existe e é ADMIN, no-op; se existe mas
é USER, erro (operador decide promover manualmente — não promovemos em
silêncio). Caso contrário, cria o utilizador com papel ADMIN.

ADR-005 define a regra: o primeiro ADMIN não passa pelo endpoint público de
registo (que agora exige autenticação admin). Esta camada é o ponto de
arranque do sistema.
"""

from __future__ import annotations

import uuid

from app.domain.entities import User, UserRole
from app.domain.value_objects import validate_email, validate_password
from app.ports.repositories import UserRepository
from app.ports.services import PasswordService


class FirstAdminAlreadyExistsError(Exception):
    """O email solicitado já existe e já tem papel ADMIN — nada a fazer."""


class FirstAdminEmailConflictError(Exception):
    """O email solicitado já existe mas com papel USER — não promovemos em silêncio."""


class SeedFirstAdmin:
    """Garante existência de um utilizador ADMIN identificado por email.

    Não impede que outros ADMINs existam: a regra é "o utilizador X deve
    existir e ser ADMIN". Promoção/rebaixamento de outros utilizadores fica
    fora do escopo do seed.
    """

    def __init__(self, users: UserRepository, passwords: PasswordService) -> None:
        self._users = users
        self._passwords = passwords

    async def execute(self, email: str, password: str) -> User:
        """Cria o utilizador como ADMIN se não existir.

        Returns:
            O ADMIN existente ou recém-criado.

        Raises:
            FirstAdminEmailConflictError: o email existe mas o utilizador é USER.
            ValueError: email ou password inválidos.
        """
        normalised = validate_email(email)
        validate_password(password)

        existing = await self._users.get_by_email(normalised)
        if existing is not None:
            if existing.role is UserRole.ADMIN:
                raise FirstAdminAlreadyExistsError(f"Utilizador ADMIN {normalised} já existe.")
            raise FirstAdminEmailConflictError(
                f"Email {normalised} já existe mas não é ADMIN. "
                "Promova manualmente em vez de re-executar o seed."
            )

        admin = User(
            id=uuid.uuid4(),
            email=normalised,
            hashed_password=self._passwords.hash(password),
            role=UserRole.ADMIN,
        )
        return await self._users.save(admin)
