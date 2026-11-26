"""Escolha da linha do catálogo quando o mesmo model_id está em dois providers."""

from __future__ import annotations

import uuid

import app.infrastructure.orm_models  # noqa: F401  (registra Conversation para o mapper)
import pytest
from app.adapters.secondary.persistence.sqlalchemy_ai_model_access_policy import (
    choose_model,
    order_candidates,
    parse_model_row_id,
)
from app.domain.entities import UserRole
from app.infrastructure.orm_models_platform import AiModel


def _model(name: str, *, default: bool = False) -> AiModel:
    return AiModel(
        id=uuid.uuid4(),
        provider_id=uuid.uuid4(),
        model_id="claude-opus-5-5",
        display_name=name,
        is_default={"text": default},
    )


def test_parse_model_row_id_accepts_only_uuids() -> None:
    row = uuid.uuid4()
    assert parse_model_row_id(str(row)) == row
    assert parse_model_row_id("claude-opus-5-5") is None
    assert parse_model_row_id("anthropic/claude-opus-4.7") is None
    assert parse_model_row_id(None) is None
    assert parse_model_row_id("") is None


def test_order_candidates_puts_text_default_first() -> None:
    azure, lynn = _model("Claude Opus 5.5"), _model("Claude Opus 5.5 (Lynn)", default=True)
    assert order_candidates([azure, lynn], "claude-opus-5-5") == [lynn, azure]
    assert order_candidates([azure, lynn], None) == [lynn]
    assert order_candidates([], None) == []


def test_admin_gets_first_candidate() -> None:
    azure, lynn = _model("Azure"), _model("Lynn")
    assert choose_model([lynn, azure], UserRole.ADMIN, set()) is lynn


def test_user_gets_the_row_they_can_use() -> None:
    # Pelo nome, o usuário com acesso só ao Lynn fica com o Lynn, não com o Azure.
    azure, lynn = _model("Azure"), _model("Lynn")
    assert choose_model([azure, lynn], UserRole.USER, {lynn.id}) is lynn


@pytest.mark.parametrize(
    ("candidates", "message"),
    [([], "indisponível"), ([_model("Azure")], "Sem acesso")],
)
def test_choose_model_refuses(candidates: list[AiModel], message: str) -> None:
    with pytest.raises(PermissionError, match=message):
        choose_model(candidates, UserRole.USER, set())
