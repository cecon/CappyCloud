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


def test_admin_provider_endpoint_keeps_azure_project_url_for_anthropic() -> None:
    # A URL do projeto continua servindo para listar os deployments na sincronização.
    base_url, api_format = _normalise_provider_endpoint(
        "https://example.services.ai.azure.com/api/projects/demo/openai/v1",
        "anthropic",
    )

    assert base_url == "https://example.services.ai.azure.com/api/projects/demo/openai/v1"
    assert api_format == "anthropic"


def test_admin_provider_endpoint_infers_anthropic_messages_url() -> None:
    base_url, api_format = _normalise_provider_endpoint(
        "https://example.services.ai.azure.com/anthropic/v1/messages",
        "chat_completions",
    )

    assert base_url == "https://example.services.ai.azure.com/anthropic/v1"
    assert api_format == "anthropic"


def test_anthropic_runtime_base_url_points_to_azure_anthropic_route() -> None:
    to_base = _pipeline_helpers._anthropic_runtime_base_url

    assert (
        to_base("https://example.services.ai.azure.com/api/projects/demo/openai/v1")
        == "https://example.services.ai.azure.com/anthropic"
    )
    assert to_base("https://api.anthropic.com/v1/messages") == "https://api.anthropic.com"
    assert to_base("https://proxy.example.com/claude/v1") == "https://proxy.example.com/claude"


async def test_resolve_runtime_config_keeps_anthropic_format(monkeypatch) -> None:
    class FakeConn:
        async def fetchrow(self, query: str, model_id: str) -> dict[str, str]:
            return {
                "base_url": "https://example.services.ai.azure.com/api/projects/demo/openai/v1",
                "api_key_encrypted": "ciphertext",
                "api_format": "anthropic",
                "name": "Azure Claude",
            }

        async def close(self) -> None:
            return None

    async def fake_connect(database_url: str) -> FakeConn:
        return FakeConn()

    monkeypatch.setattr(_pipeline_helpers.asyncpg, "connect", fake_connect)
    monkeypatch.setattr(_pipeline_helpers, "_decrypt_secret", lambda value: "plain-key")

    config = await _pipeline_helpers.resolve_model_provider_runtime_config(
        "postgresql://db", "claude-opus-5-5"
    )

    assert config is not None
    assert config.base_url == "https://example.services.ai.azure.com/anthropic"
    assert config.api_format == "anthropic"


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
                        "name": "text-embedding-3-large",
                        "capabilities": {"embeddings": "true"},
                    },
                    {
                        "name": "DeepSeek-V4-Pro",
                        "capabilities": {"chat_completion": "true"},
                    },
                    {
                        "name": "Kimi-K2.6-1",
                        "capabilities": {"chat_completion": "true"},
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
            "input_cost_per_1m_usd": 0.75,
            "output_cost_per_1m_usd": 4.5,
            "capabilities": ["text"],
        },
        {
            "model_id": "text-embedding-3-large",
            "display_name": "text-embedding-3-large",
            "context_window": 200000,
            "input_cost_per_1m_usd": 0.143,
            "output_cost_per_1m_usd": 0.0,
            "capabilities": ["embedding"],
        },
        {
            "model_id": "DeepSeek-V4-Pro",
            "display_name": "DeepSeek-V4-Pro",
            "context_window": 200000,
            "input_cost_per_1m_usd": 1.74,
            "output_cost_per_1m_usd": 3.48,
            "capabilities": ["text"],
        },
        {
            "model_id": "Kimi-K2.6-1",
            "display_name": "Kimi-K2.6-1",
            "context_window": 200000,
            "input_cost_per_1m_usd": 0.95,
            "output_cost_per_1m_usd": 4.0,
            "capabilities": ["text"],
        },
    ]
