"""Regression tests for assistant text cleanup and final message lookup."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from .agent_runtime_test_loader import (
    assistant_output as _assistant_output,
)
from .agent_runtime_test_loader import (
    task_final_message as _task_final_message,
)


def test_clean_assistant_text_removes_tool_chatter_before_final_answer() -> None:
    raw = (
        'Search repository for "1556".Open regra_nf.py.Read relevant lines.'
        "**Diagnóstico**\nO problema está na regra de CFOP."
    )

    assert _assistant_output.clean_assistant_text(raw).startswith("**Diagnóstico**")


def test_clean_assistant_text_rejects_tool_plan_without_answer() -> None:
    raw = (
        'Search repo for "ticketlog".Open venda.py.Read the relevant segment.'
        "#### Bash tool call\n```bash\nrg ticketlog\n```"
    )

    assert _assistant_output.clean_assistant_text(raw) == ""


def test_clean_assistant_text_rejects_internal_english_draft() -> None:
    raw = (
        "Likely need to adjust motivo_movto to have recolha_notas flag. "
        "Then use view to select older sales. Search send methods.Open view."
    )

    assert _assistant_output.clean_assistant_text(raw) == ""


async def test_final_message_lookup_uses_latest_user_turn_as_floor() -> None:
    conversation_id = uuid.uuid4()
    task_created = datetime(2026, 5, 20, 17, 35, 15, tzinfo=UTC)
    user_created = task_created - timedelta(seconds=1)
    message_id = uuid.uuid4()
    content = "Resposta final limpa"

    class FakeConn:
        def __init__(self) -> None:
            self.fetch_args: tuple[Any, ...] | None = None

        async def fetchrow(self, query: str, *args: Any) -> dict[str, Any]:
            return {"created_at": user_created}

        async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
            self.fetch_args = args
            return [{"id": message_id, "content": content}]

    conn = FakeConn()

    existing = await _task_final_message._find_existing_response_message(
        conn,
        conversation_id,
        content,
        {"created_at": task_created},
    )

    assert existing and existing["id"] == message_id
    assert conn.fetch_args == (conversation_id, user_created)


async def test_clean_existing_final_message_refreshes_usage_metadata() -> None:
    message_id = uuid.uuid4()
    task = {
        "model_used": "openai/gpt-oss-120b:free",
        "prompt_tokens": 100,
        "completion_tokens": 25,
        "cost_usd": Decimal("0"),
    }

    class FakeConn:
        def __init__(self) -> None:
            self.execute_args: tuple[Any, ...] | None = None

        async def execute(self, query: str, *args: Any) -> None:
            self.execute_args = args

    conn = FakeConn()

    await _task_final_message._clean_existing_message(
        conn,
        {"id": message_id, "content": "Resposta final limpa"},
        "Resposta final limpa",
        task,
    )

    assert conn.execute_args == (
        "openai/gpt-oss-120b:free",
        100,
        25,
        Decimal("0"),
        message_id,
    )
