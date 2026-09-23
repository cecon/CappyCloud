"""Testes da compactação e associação de turnos do histórico de atividade."""

from datetime import UTC, datetime, timedelta

from app.adapters.primary.http.conversation_activity import (
    MAX_FIELD_CHARS,
    assign_turns_to_messages,
    compact_events,
)

T0 = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)


def _at(seconds: int) -> datetime:
    return T0 + timedelta(seconds=seconds)


def test_assign_turns_uses_latest_message_before_task() -> None:
    messages = [_at(0), _at(60)]
    tasks = [_at(1), _at(61), _at(62)]

    assert assign_turns_to_messages(tasks, messages) == [0, 1, 1]


def test_assign_turns_without_prior_message_returns_none() -> None:
    assert assign_turns_to_messages([_at(0)], [_at(5)]) == [None]


def test_compact_merges_contiguous_text_and_keeps_order() -> None:
    events = [
        {"type": "text", "data": {"content": "Olá "}, "at": _at(0)},
        {"type": "text", "data": {"content": "mundo"}, "at": _at(1)},
        {"type": "tool_start", "data": {"id": "t1", "name": "Read", "input": "{}"}, "at": _at(2)},
        {"type": "text", "data": {"content": "fim"}, "at": _at(3)},
    ]

    result = compact_events(events)

    assert [e["type"] for e in result] == ["text", "tool_start", "text"]
    assert result[0]["data"]["content"] == "Olá mundo"
    assert result[0]["at"] == _at(0).isoformat()


def test_compact_skips_status_without_stage_and_truncates_tool_output() -> None:
    events = [
        {"type": "status", "data": {"message": "heartbeat"}, "at": _at(0)},
        {"type": "status", "data": {"stage": "agent", "state": "active"}, "at": _at(1)},
        {
            "type": "tool_result",
            "data": {"id": "t1", "output": "x" * (MAX_FIELD_CHARS + 10)},
            "at": _at(2),
        },
    ]

    result = compact_events(events)

    assert [e["type"] for e in result] == ["status", "tool_result"]
    assert result[1]["data"]["output"].endswith("(truncado)")
    assert len(result[1]["data"]["output"]) < MAX_FIELD_CHARS + 20
