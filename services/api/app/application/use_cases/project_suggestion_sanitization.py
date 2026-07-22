"""Safety helpers for project suggestion text and metadata."""

from __future__ import annotations

import re
from typing import Any

_SECRET_PATTERNS = (
    re.compile(r"\b(sk-[A-Za-z0-9_-]{16,})\b"),
    re.compile(r"\b(gh[pousr]_[A-Za-z0-9_]{20,})\b"),
    re.compile(r"\b(cappy_[A-Za-z0-9_-]{20,})\b", re.IGNORECASE),
    re.compile(r"\b([A-Fa-f0-9]{32,})\b"),
)


def sanitize_suggestion_text(value: str, *, limit: int = 220) -> str:
    text = " ".join((value or "").split())
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("[redigido]", text)
    text = re.sub(r"https?://\S+", "[link]", text)
    return text[:limit].rstrip()


def safe_metadata(value: dict[str, Any]) -> dict[str, str | int | bool]:
    clean: dict[str, str | int | bool] = {}
    for key, raw in value.items():
        if not isinstance(key, str) or key.lower() in {"prompt", "content", "secret", "token"}:
            continue
        if isinstance(raw, bool | int):
            clean[key[:40]] = raw
        elif isinstance(raw, str):
            clean[key[:40]] = sanitize_suggestion_text(raw, limit=120)
    return clean
