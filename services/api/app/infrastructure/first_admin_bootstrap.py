"""Bootstrap do primeiro ADMIN no arranque da aplicação.

Lê ``FIRST_ADMIN_EMAIL`` e ``FIRST_ADMIN_PASSWORD`` das settings e chama
:class:`app.application.use_cases.seed_admin.SeedFirstAdmin`. Idempotente:
re-arranques com o mesmo email não falham e não recriam o utilizador.

Falhas reais (email inválido, password fraca, conflito com USER existente)
levantam exceção para serem visíveis no log de startup — o operador resolve
em vez de a aplicação fingir que o seed funcionou.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.adapters.secondary.persistence.sqlalchemy_user_repo import (
    SQLAlchemyUserRepository,
)
from app.application.use_cases.seed_admin import (
    FirstAdminAlreadyExistsError,
    SeedFirstAdmin,
)
from app.infrastructure.config import Settings
from app.ports.services import PasswordService

log = logging.getLogger(__name__)


async def ensure_first_admin(
    settings: Settings,
    session_factory: async_sessionmaker,
    password_service: PasswordService | None = None,
) -> None:
    """Garante o primeiro ADMIN se as settings estão preenchidas.

    No-op silencioso quando ``FIRST_ADMIN_EMAIL`` ou ``FIRST_ADMIN_PASSWORD``
    estão vazios — convenção esperada em ambientes onde o seed já correu
    como passo de deploy.

    ``password_service`` é injetável para testes; quando omitido, usa-se a
    implementação real :class:`BcryptPasswordService`.
    """
    email = settings.first_admin_email.strip()
    password = settings.first_admin_password
    if not email or not password:
        return

    if password_service is None:
        from app.infrastructure.security import BcryptPasswordService

        password_service = BcryptPasswordService()

    async with session_factory() as session:
        users = SQLAlchemyUserRepository(session)
        uc = SeedFirstAdmin(users, password_service)
        try:
            admin = await uc.execute(email, password)
        except FirstAdminAlreadyExistsError:
            log.info("First admin %s já existe; seed no-op.", email)
            return
        log.info("First admin criado: %s (id=%s).", admin.email, admin.id)
