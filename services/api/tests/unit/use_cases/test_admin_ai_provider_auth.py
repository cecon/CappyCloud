from __future__ import annotations

from types import SimpleNamespace

from app.application.use_cases.admin_ai_provider_auth import DeriveProviderAuthState


def test_provider_with_key_is_configured() -> None:
    provider = SimpleNamespace(name="Azure", active=True, api_key_encrypted="ciphertext")

    state = DeriveProviderAuthState().execute(provider)

    assert state.state == "configured"
    assert state.label == "Chave configurada"
    assert "Sincronize" in state.next_action


def test_inactive_provider_takes_precedence_over_key_state() -> None:
    provider = SimpleNamespace(name="Azure", active=False, api_key_encrypted="ciphertext")

    state = DeriveProviderAuthState().execute(provider)

    assert state.state == "inactive"
    assert state.label == "Provider inativo"


def test_openrouter_without_key_is_catalog_only() -> None:
    provider = SimpleNamespace(name="OpenRouter", active=True, api_key_encrypted="")

    state = DeriveProviderAuthState().execute(provider)

    assert state.state == "catalog-only"
    assert state.label == "Catálogo público"


def test_manual_provider_without_key_requires_auth() -> None:
    provider = SimpleNamespace(name="Azure", active=True, api_key_encrypted="")

    state = DeriveProviderAuthState().execute(provider)

    assert state.state == "missing-key"
    assert state.label == "Chave pendente"
    assert "Cadastre a chave" in state.next_action
