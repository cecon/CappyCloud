"""Unit tests for dynamic LLM provider runtime config."""

from __future__ import annotations

from typing import Any

from app.adapters.primary.http.admin_ai_catalog_helpers import _normalise_provider_endpoint
from app.infrastructure.azure_foundry_models import (
    _deployment_catalog_urls,
    fetch_azure_foundry_deployments,
)

from .agent_runtime_test_loader import pipeline_helpers as _pipeline_helpers


def test_admin_provider_endpoint_infers_azure_responses_url() -> None:
    base_url, api_format = _normalise_provider_endpoint(
        "https://example.services.ai.azure.com/api/projects/demo/openai/v1/responses",
        "chat_completions",
    )

    assert base_url == "https://example.services.ai.azure.com/api/projects/demo/openai/v1"
    assert api_format == "responses"


def test_admin_provider_endpoint_expands_azure_host_to_openai_v1() -> None:
    base_url, api_format = _normalise_provider_endpoint(
        "https://example.services.ai.azure.com",
        "responses",
    )

    assert base_url == "https://example.services.ai.azure.com/openai/v1"
    assert api_format == "responses"


def test_admin_provider_endpoint_keeps_openrouter_chat_base_url() -> None:
    base_url, api_format = _normalise_provider_endpoint(
        "https://openrouter.ai/api/v1",
        "chat_completions",
    )

    assert base_url == "https://openrouter.ai/api/v1"
    assert api_format == "chat_completions"


async def test_resolve_model_provider_runtime_config_decrypts_and_normalises(
    monkeypatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeConn:
        async def fetchrow(self, query: str, model_id: str) -> dict[str, str]:
            captured["query"] = query
            captured["model_id"] = model_id
            return {
                "base_url": "https://example.services.ai.azure.com/api/projects/demo/openai/v1/responses",
                "api_key_encrypted": "ciphertext",
                "api_format": "chat_completions",
                "name": "Azure",
            }

        async def close(self) -> None:
            captured["closed"] = True

    async def fake_connect(database_url: str) -> FakeConn:
        captured["database_url"] = database_url
        return FakeConn()

    monkeypatch.setattr(_pipeline_helpers.asyncpg, "connect", fake_connect)
    monkeypatch.setattr(_pipeline_helpers, "_decrypt_secret", lambda value: "plain-key")

    config = await _pipeline_helpers.resolve_model_provider_runtime_config(
        "postgresql://db",
        "gpt-5.4-mini",
    )

    assert config is not None
    assert config.base_url == "https://example.services.ai.azure.com/openai/v1"
    assert config.api_key == "plain-key"
    assert config.api_format == "responses"
    assert captured["model_id"] == "gpt-5.4-mini"
    assert "JOIN ai_providers" in captured["query"]
    assert captured["closed"] is True


def test_azure_deployment_catalog_url_uses_project_from_path_first() -> None:
    urls = _deployment_catalog_urls(
        "https://example.services.ai.azure.com/api/projects/custom/openai/v1"
    )

    assert urls[0].endswith("/api/projects/custom/deployments?api-version=v1")
    assert urls[1].endswith("/api/projects/example_project/deployments?api-version=v1")


async def test_fetch_azure_foundry_deployments_normalises_payload(monkeypatch) -> None:
    class FakeResponse:
        status_code = 200

        def json(self) -> dict[str, Any]:
            return {
                "value": [
                    {
                        "name": "gpt-5.4-mini",
                        "modelName": "gpt-5.4-mini",
                        "capabilities": {"chat_completion": "true"},
                    },
                    {
                        "name": "embed",
                        "capabilities": {"embeddings": "true"},
                    },
                ]
            }

    class FakeClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self) -> FakeClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def get(self, url: str, headers: dict[str, str]) -> FakeResponse:
            assert url.endswith("/api/projects/example_project/deployments?api-version=v1")
            assert headers["Authorization"].startswith("Bearer ")
            return FakeResponse()

    monkeypatch.setattr(
        "app.infrastructure.azure_foundry_models.httpx.AsyncClient",
        FakeClient,
    )

    deployments = await fetch_azure_foundry_deployments(
        base_url="https://example.services.ai.azure.com/openai/v1",
        api_key="plain-key",
    )

    assert deployments == [
        {
            "model_id": "gpt-5.4-mini",
            "display_name": "gpt-5.4-mini",
            "context_window": 200000,
            "input_cost_per_1m_usd": None,
            "output_cost_per_1m_usd": None,
            "capabilities": ["text"],
        },
        {
            "model_id": "embed",
            "display_name": "embed",
            "context_window": 200000,
            "input_cost_per_1m_usd": None,
            "output_cost_per_1m_usd": None,
            "capabilities": ["embedding"],
        },
    ]
