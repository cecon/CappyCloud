"""Regression tests for CappyCloud agent runtime edge cases."""

from __future__ import annotations

import types

from .agent_runtime_test_loader import (
    grpc_event_handlers as _grpc_event_handlers,
)


def test_done_full_text_becomes_text_event_when_chunks_are_missing() -> None:
    msg = types.SimpleNamespace(
        done=types.SimpleNamespace(
            full_text="Resposta final", prompt_tokens=10, completion_tokens=3
        )
    )

    assert _grpc_event_handlers.final_text_fallback_event(msg, streamed_text=False) == (
        "text",
        {"content": "Resposta final"},
    )
    assert _grpc_event_handlers.final_text_fallback_event(msg, streamed_text=True) is None


def test_provider_api_error_text_chunk_becomes_error_event() -> None:
    msg = types.SimpleNamespace(
        text_chunk=types.SimpleNamespace(
            text=(
                'API Error: 429 {"error":{"message":"Provider returned error",'
                '"code":429,"metadata":{"raw":"deepseek/deepseek-v4-flash:free '
                'is temporarily rate-limited upstream","provider_name":"Crucible",'
                '"is_byok":false}},"user_id":"user_should_not_leak"}'
            )
        )
    )

    event_type, data = _grpc_event_handlers.text_chunk_event(msg)

    assert event_type == "error"
    assert "429" in data["message"]
    assert "deepseek/deepseek-v4-flash:free" in data["message"]
    assert "Crucible" in data["message"]
    assert "user_should_not_leak" not in data["message"]


def test_payload_diagnostic_event_normalizes_and_strips_unsafe_fields() -> None:
    msg = types.SimpleNamespace(
        payload_diagnostic=types.SimpleNamespace(
            total_size_bytes=999,
            source="sk-live-secret",
            generated_at="/repos/private/file.py",
            categories=[
                types.SimpleNamespace(
                    key="/repos/private/file.py",
                    label="sk-live-secret",
                    size_bytes=25,
                    percentage=100,
                ),
                types.SimpleNamespace(
                    key="attachments",
                    label="/repos/private/image.png",
                    size_bytes=75,
                    percentage=100,
                ),
            ],
        )
    )

    event = _grpc_event_handlers.payload_diagnostic_event(msg)

    assert event is not None
    event_type, data = event
    assert event_type == "payload_diagnostic"
    diagnostics = data["diagnostics"]
    assert diagnostics["total_size_bytes"] == 100
    assert diagnostics["source"] == "openclaude"
    assert diagnostics["generated_at"] == ""
    assert diagnostics["categories"] == [
        {"key": "attachments", "label": "Anexos", "size_bytes": 75, "percentage": 75.0},
        {"key": "other", "label": "Outros", "size_bytes": 25, "percentage": 25.0},
    ]
    assert "sk-live-secret" not in str(data)
    assert "/repos/private" not in str(data)


def test_malformed_payload_diagnostic_event_is_ignored() -> None:
    msg = types.SimpleNamespace(
        payload_diagnostic=types.SimpleNamespace(
            total_size_bytes=-1,
            source="openclaude",
            generated_at="2026-06-17T15:20:00Z",
            categories=[],
        )
    )

    assert _grpc_event_handlers.payload_diagnostic_event(msg) is None


def test_context_progress_event_is_progress_only() -> None:
    msg = types.SimpleNamespace(
        context_progress=types.SimpleNamespace(
            label="Contexto usado",
            current_value=50,
            limit_value=200,
            percent="25.4",
            financial=True,
        )
    )

    assert _grpc_event_handlers.context_progress_event(msg) == (
        "context_progress",
        {
            "label": "Contexto usado",
            "current_value": 50,
            "limit_value": 200,
            "percent": 25.4,
            "financial": False,
        },
    )


def test_subagent_group_event_sanitizes_activity_state() -> None:
    msg = types.SimpleNamespace(
        subagent_group=types.SimpleNamespace(
            parent_turn_id="turn_1",
            label="Auxiliares\ninternos",
            collapsible=True,
            activities=[
                types.SimpleNamespace(id="agent_1", name="repo-a", state="done", detail="ok"),
                types.SimpleNamespace(id="agent_2", name="repo-b", state="weird", detail="rodando"),
            ],
        )
    )

    assert _grpc_event_handlers.subagent_group_event(msg) == (
        "subagent_group",
        {
            "parent_turn_id": "turn_1",
            "label": "Auxiliares internos",
            "collapsible": True,
            "activities": [
                {"id": "agent_1", "name": "repo-a", "state": "done", "detail": "ok"},
                {
                    "id": "agent_2",
                    "name": "repo-b",
                    "state": "tool-running",
                    "detail": "rodando",
                },
            ],
        },
    )


def test_subagent_group_event_preserves_runtime_edge_states() -> None:
    states = [
        "loading",
        "streaming",
        "tool-running",
        "permission-request",
        "permission-timeout",
        "stalled",
        "canceled",
        "failed",
        "done",
    ]
    msg = types.SimpleNamespace(
        subagent_group=types.SimpleNamespace(
            parent_turn_id="turn_2",
            label="Auxiliares",
            collapsible=True,
            activities=[
                types.SimpleNamespace(
                    id=f"agent_{index}",
                    name=f"worker-{index}",
                    state=state,
                    detail="ok",
                )
                for index, state in enumerate(states)
            ],
        )
    )

    event = _grpc_event_handlers.subagent_group_event(msg)

    assert event is not None
    _, data = event
    assert [activity["state"] for activity in data["activities"]] == states


def test_tool_result_event_preserves_stdout_and_error_flag() -> None:
    msg = types.SimpleNamespace(
        tool_result=types.SimpleNamespace(
            tool_name="Bash",
            output=b"stdout preservado",
            is_error=True,
            tool_use_id="toolu_1",
        )
    )

    event_type, data = _grpc_event_handlers.tool_result_event(msg)

    assert event_type == "tool_result"
    assert data == {
        "name": "Bash",
        "output": "stdout preservado",
        "is_error": True,
        "id": "toolu_1",
    }


def test_tool_error_remains_visible_after_text_event() -> None:
    text_msg = types.SimpleNamespace(text_chunk=types.SimpleNamespace(text="Investigando...\n"))
    tool_msg = types.SimpleNamespace(
        tool_result=types.SimpleNamespace(
            tool_name="Bash",
            output=b"comando falhou",
            is_error=True,
            tool_use_id="toolu_error",
        )
    )

    assert _grpc_event_handlers.text_chunk_event(text_msg) == (
        "text",
        {"content": "Investigando...\n"},
    )
    event_type, data = _grpc_event_handlers.tool_result_event(tool_msg)

    assert event_type == "tool_result"
    assert data["id"] == "toolu_error"
    assert data["is_error"] is True
    assert data["output"] == "comando falhou"


def test_done_event_reports_sanitized_runtime_fallback() -> None:
    msg = types.SimpleNamespace(
        done=types.SimpleNamespace(
            full_text="",
            prompt_tokens=10,
            completion_tokens=5,
            model_used="openrouter/fallback:free",
            fallback_reason="rate limit",
        )
    )

    event_type, data = _grpc_event_handlers.done_event(
        msg,
        session_id="session",
        model="openrouter/selected",
        wd="/workspace",
        streamed_text=True,
    )

    assert event_type == "done"
    assert data["model_used"] == "openrouter/fallback:free"
    assert data["fallback"] == {
        "selected_model": "openrouter/selected",
        "final_model": "openrouter/fallback:free",
        "reason": "rate_limit",
    }
