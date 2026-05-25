"""Helpers compartilhados da coleta automática de evidências."""

from __future__ import annotations

from collections.abc import Sequence

from ._evidence_models import _ConfluenceSource

_TEXT_LIMIT = 220


def _trim(text: str, limit: int = _TEXT_LIMIT) -> str:
    one_line = " ".join(str(text).split())
    return one_line[:limit]


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        value = item.strip()
        key = value.lower()
        if value and key not in seen:
            seen.add(key)
            out.append(value)
    return out


def _clean_labels(raw_labels: object) -> list[str]:
    if isinstance(raw_labels, str):
        values: Sequence[object] = raw_labels.split(",")
    elif isinstance(raw_labels, (list, tuple)):
        values = list(raw_labels)
    else:
        return []
    labels: list[str] = []
    seen: set[str] = set()
    for raw in values:
        label = str(raw).strip()
        key = label.lower()
        if label and key not in seen:
            seen.add(key)
            labels.append(label)
    return labels


def _format_doc_filters(source: _ConfluenceSource) -> str:
    filters: list[str] = []
    if source.space:
        filters.append(f"space `{source.space}`")
    if source.labels:
        filters.append("labels " + ", ".join(f"`{label}`" for label in source.labels))
    return f" ({'; '.join(filters)})" if filters else ""


def _worktree_path(repo: dict, session_root: str) -> str:
    wt = str(repo.get("worktree_path") or "").strip()
    if wt:
        return wt
    alias = str(repo.get("alias") or repo.get("slug") or "").strip()
    return f"{session_root.rstrip('/')}/{alias}" if session_root and alias else ""
