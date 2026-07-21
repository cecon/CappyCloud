"""Tests for chat command sanitization."""

from app.application.use_cases.chat_command_sanitization import (
    sanitize_arguments,
    sanitize_command_text,
)


def test_sanitizes_secrets_tokens_oauth_and_user_paths() -> None:
    text = (
        "api_key=sk-live token: abc Bearer xyz "
        "https://user:pass@example.com/callback?code=secret&state=raw "
        "C:\\Users\\cecon\\repo"
    )

    sanitized = sanitize_command_text(text)

    assert "sk-live" not in sanitized
    assert "Bearer xyz" not in sanitized
    assert "code=secret" not in sanitized
    assert "state=raw" not in sanitized
    assert "cecon" not in sanitized


def test_sanitizes_sensitive_arguments_by_key() -> None:
    sanitized = sanitize_arguments(
        {"model": "openrouter/free", "token": "secret-token"},
        {"token"},
    )

    assert sanitized == {"model": "openrouter/free", "token": "***"}


def test_sanitizes_unauthorized_repository_content_and_nested_secret_text() -> None:
    text = (
        "Erro lendo /repos/users/tenant/private/.env secret = top-secret authorization: Basic raw"
    )

    sanitized = sanitize_command_text(text)

    assert "top-secret" not in sanitized
    assert "Basic raw" not in sanitized
    assert "/repos/users/tenant/private/.env" not in sanitized
    assert "/repos/users/***" in sanitized


def test_sanitizes_non_sensitive_argument_values_too() -> None:
    sanitized = sanitize_arguments(
        {"path": "C:\\Users\\cecon\\repo", "note": "refresh_token=abc"},
        set(),
    )

    assert sanitized["path"] == "C:\\Users\\***\\repo"
    assert sanitized["note"] == "refresh_token=***"
