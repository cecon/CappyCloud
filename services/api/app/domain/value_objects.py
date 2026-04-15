"""Value objects — pure validation functions. No external dependencies.

Pydantic validators in schemas.py delegate to these functions (DRY).
"""

from __future__ import annotations

import re

# Alinhado ao frontend (validation.ts) — evita rejeições estritas do EmailStr.
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")

_PASSWORD_MIN_LEN = 8


def validate_email(raw: str) -> str:
    """Normaliza e valida o formato do email.

    Returns:
        Email em minúsculas sem espaços.

    Raises:
        ValueError: se o formato for inválido.
    """
    value = str(raw).strip().lower()
    if not value:
        raise ValueError("Email é obrigatório.")
    if not _EMAIL_RE.fullmatch(value):
        raise ValueError("Email inválido. Use o formato nome@dominio.com.")
    return value


def validate_password(raw: str) -> str:
    """Valida comprimento mínimo da password.

    Returns:
        Password sem modificações.

    Raises:
        ValueError: se tiver menos de 8 caracteres.
    """
    if len(raw) < _PASSWORD_MIN_LEN:
        raise ValueError(
            f"A password deve ter pelo menos {_PASSWORD_MIN_LEN} caracteres."
        )
    return raw
