#!/usr/bin/env python3
"""Cria (ou confirma) o primeiro ADMIN do CappyCloud (ADR-005).

Uso típico (deploy):

    FIRST_ADMIN_EMAIL=admin@cappycloud.io \\
    FIRST_ADMIN_PASSWORD='troca-isto-no-1o-login' \\
    python -m scripts.seed_first_admin

Idempotente: re-execução com o mesmo email não falha nem recria o utilizador.
Se o email existir como USER, o script erra propositadamente — promova
manualmente em SQL para não promover em silêncio.

Variáveis lidas (settings):
    DATABASE_URL           postgresql+asyncpg://...
    FIRST_ADMIN_EMAIL      ou passe ``--email``
    FIRST_ADMIN_PASSWORD   ou passe ``--password`` (não recomendado em CLI)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from app.adapters.secondary.persistence.sqlalchemy_user_repo import (
    SQLAlchemyUserRepository,
)
from app.application.use_cases.seed_admin import (
    FirstAdminAlreadyExistsError,
    FirstAdminEmailConflictError,
    SeedFirstAdmin,
)
from app.infrastructure.config import get_settings
from app.infrastructure.database import async_session_factory
from app.infrastructure.security import BcryptPasswordService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("seed_first_admin")


async def _run(email: str, password: str) -> int:
    async with async_session_factory() as session:
        users = SQLAlchemyUserRepository(session)
        passwords = BcryptPasswordService()
        uc = SeedFirstAdmin(users, passwords)
        try:
            admin = await uc.execute(email, password)
        except FirstAdminAlreadyExistsError as exc:
            log.info("%s", exc)
            return 0
        except FirstAdminEmailConflictError as exc:
            log.error("%s", exc)
            return 2
        except ValueError as exc:
            log.error("Dados inválidos: %s", exc)
            return 2
        log.info("ADMIN criado: %s (id=%s).", admin.email, admin.id)
        return 0


def main() -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Seed do primeiro ADMIN.")
    parser.add_argument(
        "--email",
        default=settings.first_admin_email,
        help="Email do ADMIN. Default: FIRST_ADMIN_EMAIL.",
    )
    parser.add_argument(
        "--password",
        default=settings.first_admin_password,
        help="Password do ADMIN. Default: FIRST_ADMIN_PASSWORD.",
    )
    args = parser.parse_args()
    if not args.email or not args.password:
        parser.error(
            "Email e password obrigatórios. Defina FIRST_ADMIN_EMAIL/"
            "FIRST_ADMIN_PASSWORD ou passe --email/--password."
        )
    return asyncio.run(_run(args.email, args.password))


if __name__ == "__main__":
    sys.exit(main())
