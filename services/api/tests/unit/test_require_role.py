"""Unit tests for require_role FastAPI dependency factory (ADR-005)."""

from __future__ import annotations

import uuid

import pytest
from app.adapters.primary.http.deps import require_role
from app.domain.entities import User, UserRole
from fastapi import HTTPException


def _user(role: UserRole) -> User:
    return User(
        id=uuid.uuid4(),
        email=f"{role.value}@test.com",
        hashed_password="x",
        role=role,
    )


class TestRequireRole:
    async def test_admin_passes_when_admin_required(self) -> None:
        dep = require_role(UserRole.ADMIN)
        admin = _user(UserRole.ADMIN)
        assert await dep(admin) is admin

    async def test_user_blocked_when_admin_required(self) -> None:
        dep = require_role(UserRole.ADMIN)
        with pytest.raises(HTTPException) as exc:
            await dep(_user(UserRole.USER))
        assert exc.value.status_code == 403

    async def test_user_passes_when_user_required(self) -> None:
        dep = require_role(UserRole.USER)
        user = _user(UserRole.USER)
        assert await dep(user) is user

    async def test_admin_bypasses_user_requirement(self) -> None:
        # ADR-005 §3: ADMIN sempre passa, ignora regra de USER.
        dep = require_role(UserRole.USER)
        admin = _user(UserRole.ADMIN)
        assert await dep(admin) is admin

    async def test_403_message_does_not_leak_role_name(self) -> None:
        dep = require_role(UserRole.ADMIN)
        with pytest.raises(HTTPException) as exc:
            await dep(_user(UserRole.USER))
        # Mensagem genérica — não revela qual papel é necessário (defesa
        # em profundidade, ADR-005 §5).
        assert "admin" not in exc.value.detail.lower()
        assert "permissão" in exc.value.detail.lower()
