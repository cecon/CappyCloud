"""Value objects — pure validation functions. No external dependencies.

Pydantic validators in schemas.py delegate to these functions (DRY).
"""

from __future__ import annotations

import re
from enum import StrEnum

# Alinhado ao frontend (validation.ts) — evita rejeições estritas do EmailStr.
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")

_PASSWORD_MIN_LEN = 8


class PermissionMode(StrEnum):
    REQUEST_PERMISSIONS = "request_permissions"
    ACCEPT_EDITS = "accept_edits"
    PLAN = "plan"
    AUTO = "auto"
    BYPASS_PERMISSIONS = "bypass_permissions"


DEFAULT_PERMISSION_MODE = PermissionMode.BYPASS_PERMISSIONS.value


class UserWorkspaceStatus(StrEnum):
    PREPARING = "preparing"
    READY = "ready"
    REPAIRING = "repairing"
    DIRTY = "dirty"
    MISSING = "missing"
    UNAUTHORIZED = "unauthorized"
    ERROR = "error"


DEFAULT_USER_WORKSPACE_STATUS = UserWorkspaceStatus.PREPARING.value


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
        raise ValueError(f"A password deve ter pelo menos {_PASSWORD_MIN_LEN} caracteres.")
    return raw


def validate_permission_mode(raw: object | None) -> str:
    """Normaliza e valida o modo de permissão da sessão."""
    if raw is None:
        return DEFAULT_PERMISSION_MODE
    value = str(raw).strip()
    try:
        return PermissionMode(value).value
    except ValueError as exc:
        allowed = ", ".join(mode.value for mode in PermissionMode)
        raise ValueError(f"modo de permissão inválido. Use um de: {allowed}.") from exc


def validate_user_workspace_status(raw: object | None) -> str:
    """Normaliza e valida o estado de workspace persistente do utilizador."""
    if raw is None:
        return DEFAULT_USER_WORKSPACE_STATUS
    value = str(raw).strip()
    try:
        return UserWorkspaceStatus(value).value
    except ValueError as exc:
        allowed = ", ".join(status.value for status in UserWorkspaceStatus)
        raise ValueError(f"estado de workspace inválido. Use um de: {allowed}.") from exc
