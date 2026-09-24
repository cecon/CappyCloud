"""Criação de conversa num workspace: regras de acesso e repos repassados."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from app.adapters.primary.http import conversation_create_helpers as helpers
from app.domain.entities import UserRole
from fastapi import HTTPException


class _Scalar:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _Session:
    def __init__(self, *values):
        self._values = list(values)

    async def execute(self, *_args, **_kwargs):
        return _Scalar(self._values.pop(0))


class _UseCase:
    def __init__(self):
        self.kwargs: dict = {}

    async def execute(self, user_id, **kwargs):
        self.kwargs = kwargs
        return "conv"


def _link(alias: str, read_only: bool = False, base: str = ""):
    repo = SimpleNamespace(slug=f"{alias}-slug", default_branch="main")
    return SimpleNamespace(alias=alias, base_branch=base, read_only=read_only, repository=repo)


def _workspace(**overrides):
    values = {
        "id": uuid.uuid4(),
        "slug": "loja",
        "active": True,
        "sync_status": "synced",
        "sandbox_id": uuid.uuid4(),
        "repositories": [_link("backend", base="develop"), _link("docs", read_only=True)],
    }
    return SimpleNamespace(**{**values, **overrides})


def _user(role=UserRole.USER):
    return SimpleNamespace(id=uuid.uuid4(), role=role)


@pytest.fixture(autouse=True)
def _no_sandbox(monkeypatch: pytest.MonkeyPatch) -> None:
    async def ready(*_args):
        return None

    async def model(*_args):
        return None

    monkeypatch.setattr(helpers, "ensure_sandbox_ready_for_chat", ready)
    monkeypatch.setattr(helpers, "resolve_ai_model_id", model)


def _body():
    return SimpleNamespace(workspace_id=uuid.uuid4(), title=None, model_id=None)


async def test_repassa_todos_os_repos_com_read_only() -> None:
    uc = _UseCase()
    ws = _workspace()
    await helpers.create_workspace_conversation(_Session(ws, uuid.uuid4()), _user(), uc, _body())
    assert uc.kwargs["workspace_slug"] == "loja"
    assert uc.kwargs["repos"] == [
        {"slug": "backend-slug", "alias": "backend", "base_branch": "develop", "read_only": False},
        {"slug": "docs-slug", "alias": "docs", "base_branch": "main", "read_only": True},
    ]


@pytest.mark.parametrize(
    ("values", "role", "status"),
    [
        ((None,), UserRole.ADMIN, 404),
        ((_workspace(active=False),), UserRole.ADMIN, 404),
        ((_workspace(), None), UserRole.USER, 403),
        ((_workspace(repositories=[]),), UserRole.ADMIN, 400),
        ((_workspace(sync_status="pending"),), UserRole.ADMIN, 409),
    ],
)
async def test_recusa_workspace_inacessivel(values, role, status) -> None:
    with pytest.raises(HTTPException) as exc:
        await helpers.create_workspace_conversation(
            _Session(*values), _user(role), _UseCase(), _body()
        )
    assert exc.value.status_code == status
