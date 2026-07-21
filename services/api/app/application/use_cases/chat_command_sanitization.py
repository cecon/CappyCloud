"""Sanitization helpers for chat command diagnostics."""

from __future__ import annotations

import re

_API_KEY_RE = re.compile(r"(?i)(api[_-]?key|token|secret|authorization)(\s*[:=]\s*)([^\s`'\"&]+)")
_BEARER_RE = re.compile(r"(?i)bearer\s+[a-z0-9._\-]+")
_OAUTH_CODE_RE = re.compile(r"(?i)(code|state|access_token|refresh_token)=([^&\s]+)")
_WINDOWS_USER_RE = re.compile(r"[A-Z]:\\Users\\[^\\\s]+", re.IGNORECASE)
_SANDBOX_USER_RE = re.compile(r"/repos/users/[^`'\"\s]+")
_URL_CREDENTIAL_RE = re.compile(r"(https?://)([^/@\s]+)@")


def sanitize_command_text(value: object) -> str:
    text = str(value or "")
    text = _API_KEY_RE.sub(r"\1\2***", text)
    text = _BEARER_RE.sub("Bearer ***", text)
    text = _OAUTH_CODE_RE.sub(r"\1=***", text)
    text = _WINDOWS_USER_RE.sub(r"C:\\Users\\***", text)
    text = _SANDBOX_USER_RE.sub("/repos/users/***", text)
    text = _URL_CREDENTIAL_RE.sub(r"\1***@", text)
    return text


def sanitize_arguments(arguments: dict[str, object], sensitive_keys: set[str]) -> dict[str, object]:
    sanitized: dict[str, object] = {}
    for key, value in arguments.items():
        if key in sensitive_keys:
            sanitized[key] = "***"
        else:
            sanitized[key] = sanitize_command_text(value)
    return sanitized
