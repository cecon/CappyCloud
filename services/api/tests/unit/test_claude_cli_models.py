"""Modelos do Claude CLI: só em sandbox com runtime Claude CLI, fora do catálogo."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from app.adapters.primary.http.conversation_sandbox_guard import uses_claude_cli_model
from app.domain.value_objects import is_claude_cli_model
from fastapi import HTTPException


class _Session:
    def __init__(self, sandbox):
        self._sandbox = sandbox

    async def get(self, _model, _id):
        return self._sandbox


def test_reconhece_so_os_tres_modelos() -> None:
    assert all(is_claude_cli_model(f"claude-cli/{m}") for m in ("opus", "sonnet", "haiku"))
    assert not is_claude_cli_model("anthropic/claude-sonnet-5")
    assert not is_claude_cli_model(None)


async def test_modelo_do_catalogo_segue_o_fluxo_normal() -> None:
    assert await uses_claude_cli_model(_Session(None), uuid.uuid4(), "gpt-5.4") is False


async def test_aceita_em_sandbox_claude_cli() -> None:
    session = _Session(SimpleNamespace(agent_runtime="claude_cli"))
    assert await uses_claude_cli_model(session, uuid.uuid4(), "claude-cli/opus") is True


@pytest.mark.parametrize("sandbox", [SimpleNamespace(agent_runtime="openclaude"), None])
async def test_recusa_fora_do_claude_cli(sandbox) -> None:
    with pytest.raises(HTTPException) as exc:
        await uses_claude_cli_model(_Session(sandbox), uuid.uuid4(), "claude-cli/opus")
    assert exc.value.status_code == 403


async def test_pipeline_nao_troca_modelo_do_claude_cli_pelo_padrao_do_catalogo() -> None:
    from tests.unit.agent_runtime_test_loader import pipeline_helpers

    # Sem banco: um modelo do catálogo cairia no padrão; o do Claude CLI passa direto.
    assert await pipeline_helpers.resolve_text_model_id("", "claude-cli/opus") == "claude-cli/opus"
