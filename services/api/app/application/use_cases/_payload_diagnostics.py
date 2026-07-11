"""Sanitization helpers for chat-visible payload diagnostics."""

from __future__ import annotations

import re
from math import isfinite

_SAFE_DIAGNOSTIC_TEXT = re.compile(r"^[A-Za-z0-9_.:+-]{1,64}$")
_SAFE_PAYLOAD_CATEGORY_LABELS = {
    "user_message": "Mensagem do usuario",
    "conversation_history": "Historico da conversa",
    "repository_context": "Contexto do repositorio",
    "attachments": "Anexos",
    "tool_results": "Resultados de ferramentas",
    "tool_schemas": "Ferramentas",
    "mcp_tool_schemas": "Ferramentas MCP",
    "runtime_context": "Contexto de runtime",
    "other": "Outros",
}


def sanitize_payload_diagnostics(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None

    categories: dict[str, dict[str, object]] = {}
    raw_categories = value.get("categories")
    if isinstance(raw_categories, list):
        for raw_category in raw_categories:
            if not isinstance(raw_category, dict):
                continue
            key = _safe_payload_category_key(raw_category.get("key"))
            size_bytes = _safe_non_negative_int(raw_category.get("size_bytes"))
            if size_bytes <= 0:
                continue
            current = categories.setdefault(
                key,
                {
                    "key": key,
                    "label": _SAFE_PAYLOAD_CATEGORY_LABELS[key],
                    "size_bytes": 0,
                    "percentage": 0.0,
                },
            )
            current["size_bytes"] = _safe_non_negative_int(current.get("size_bytes")) + size_bytes

    total_size_bytes = _safe_non_negative_int(value.get("total_size_bytes"))
    if categories:
        total_size_bytes = sum(
            _safe_non_negative_int(item.get("size_bytes")) for item in categories.values()
        )
    elif total_size_bytes <= 0:
        return None

    ordered_categories = sorted(
        categories.values(),
        key=lambda item: _safe_non_negative_int(item.get("size_bytes")),
        reverse=True,
    )
    for category in ordered_categories:
        category_size = _safe_non_negative_int(category.get("size_bytes"))
        category["percentage"] = (
            round((category_size / total_size_bytes) * 1000) / 10 if total_size_bytes > 0 else 0.0
        )

    return {
        "total_size_bytes": total_size_bytes,
        "categories": ordered_categories,
        "source": _safe_diagnostic_source(value.get("source")),
        "generated_at": _safe_diagnostic_text(value.get("generated_at")),
    }


def _safe_payload_category_key(value: object) -> str:
    key = str(value or "").strip().lower()
    if key in _SAFE_PAYLOAD_CATEGORY_LABELS:
        return key
    return "other"


def _safe_non_negative_int(value: object) -> int:
    try:
        if isinstance(value, int):
            return max(0, value)
        if isinstance(value, float):
            return max(0, int(value)) if isfinite(value) else 0
        if isinstance(value, str):
            return max(0, int(value))
        return 0
    except TypeError:
        return 0
    except ValueError:
        return 0
    except OverflowError:
        return 0


def _safe_diagnostic_source(value: object) -> str:
    source = str(value or "openclaude").strip().lower()
    if source in {"openclaude", "cappycloud", "agent"}:
        return source
    return "openclaude"


def _safe_diagnostic_text(value: object) -> str:
    text = str(value or "").strip()
    if _SAFE_DIAGNOSTIC_TEXT.fullmatch(text):
        return text
    return ""
