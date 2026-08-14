from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.adapters.primary.http.admin_ai_catalog_helpers import admin_provider_out


def test_admin_provider_out_includes_sanitized_auth_state_without_secret_fields() -> None:
    provider = SimpleNamespace(
        id=uuid4(),
        name="Azure",
        base_url="https://example.openai.azure.com/openai/v1",
        api_format="responses",
        active=True,
        api_key_encrypted="",
        last_synced_at=datetime(2026, 8, 8, tzinfo=UTC),
    )

    dto = admin_provider_out(provider, models_count=3)
    data = dto.model_dump()

    assert data["auth_state"] == "missing-key"
    assert data["auth_label"] == "Chave pendente"
    assert data["models_count"] == 3
    assert "api_key" not in data
    assert "api_key_encrypted" not in data
