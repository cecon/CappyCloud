"""Utilities for turning raw model stream text into user-facing output."""

from __future__ import annotations

import re

from ._grpc_helpers import provider_api_error_message

_FINAL_MARKERS = (
    "**Diagnóstico",
    "Diagnóstico",
    "**Resposta",
    "Resposta",
    "**Causa",
    "Causa",
    "**Evidências",
    "Evidências",
)

_TOOL_PREFIX_RE = re.compile(
    r"^(?:(?:Search|Open|Read|Grep|Find|List|Run|Use|Maybe|Need to|We need|"
    r"Path typo|The file already loaded|Line \d+|Let's|I will)"
    r"[^.!?\n]{0,280}[.!?]\s*)+",
    re.IGNORECASE,
)

_TOOL_TEXT_RE = re.compile(
    r"\b(Search|Open|Read|Grep|Find|Bash|Glob|Tool called|tool call)\b",
    re.IGNORECASE,
)
_INTERNAL_DRAFT_RE = re.compile(
    r"^\s*(?:likely need|likely|probably|maybe|need to|we need|i need|let's|"
    r"search|open|read|grep|find|actually)\b",
    re.IGNORECASE,
)


def clean_assistant_text(raw_text: str) -> str:
    """Remove tool chatter and unsafe provider blobs from assistant text."""
    text = (raw_text or "").strip()
    if not text:
        return ""

    provider_error = provider_api_error_message(text)
    if provider_error:
        return f"**Erro:** {provider_error}"

    if "</think>" in text and not _has_final_marker(text):
        return ""

    if not _has_final_marker(text) and _INTERNAL_DRAFT_RE.search(text):
        return ""

    marker_index = _first_final_marker_index(text)
    if marker_index > 0 and _TOOL_TEXT_RE.search(text[:marker_index]):
        text = text[marker_index:].lstrip()

    previous = None
    while previous != text:
        previous = text
        text = _TOOL_PREFIX_RE.sub("", text).lstrip()

    if _looks_like_tool_plan(text):
        return ""
    return text.strip()


def _has_final_marker(text: str) -> bool:
    return any(marker in text for marker in _FINAL_MARKERS)


def _first_final_marker_index(text: str) -> int:
    indexes = [text.find(marker) for marker in _FINAL_MARKERS if marker in text]
    return min(indexes) if indexes else -1


def _looks_like_tool_plan(text: str) -> bool:
    if not text:
        return True
    if "#### Bash tool call" in text or "### Step 1" in text:
        return True
    tool_hits = len(_TOOL_TEXT_RE.findall(text))
    return tool_hits >= 3 and not _has_final_marker(text)
