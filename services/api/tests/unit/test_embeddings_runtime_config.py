"""Unit tests for dynamic embedding runtime config."""

from __future__ import annotations

from typing import Any

from app.infrastructure import embeddings


async def test_resolve_embedding_runtime_config_uses_default_embedding_model(
    monkeypatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeConn:
        async def fetchrow(self, query: str) -> dict[str, str]:
            captured["query"] = query
            return {
                "model_id": "text-embedding-3-small",
                "base_url": "https://example.services.ai.azure.com",
                "api_key_encrypted": "ciphertext",
            }

        async def close(self) -> None:
            captured["closed"] = True

    async def fake_connect(database_url: str) -> FakeConn:
        captured["database_url"] = database_url
        return FakeConn()

    monkeypatch.setattr(embeddings, "_database_url", lambda: "postgresql://db")
    monkeypatch.setattr(embeddings.asyncpg, "connect", fake_connect)
    monkeypatch.setattr(embeddings, "_decrypt_secret", lambda value: "plain-key")

    config = await embeddings.resolve_embedding_runtime_config()

    assert config is not None
    assert config.base_url == "https://example.services.ai.azure.com/openai/v1"
    assert config.api_key == "plain-key"
    assert config.model == "text-embedding-3-small"
    assert "m.capabilities ? 'embedding'" in captured["query"]
    assert "is_default->>'embedding'" in captured["query"]
    assert captured["closed"] is True


async def test_embed_texts_sends_dynamic_embedding_model(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class FakeResponse:
        status_code = 200

        def json(self) -> dict[str, Any]:
            return {"data": [{"embedding": [0.1] * embeddings.EMBEDDING_DIM}]}

    class FakeClient:
        def __init__(self, timeout: Any) -> None:
            self.timeout = timeout

        async def __aenter__(self) -> FakeClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(
            self,
            url: str,
            *,
            headers: dict[str, str],
            json: dict[str, Any],
        ) -> FakeResponse:
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return FakeResponse()

    async def fake_resolve_embedding_runtime_config() -> embeddings.EmbeddingRuntimeConfig:
        return embeddings.EmbeddingRuntimeConfig(
            base_url="https://example.services.ai.azure.com/openai/v1",
            api_key="plain-key",
            model="text-embedding-3-small",
        )

    monkeypatch.setattr(
        embeddings,
        "resolve_embedding_runtime_config",
        fake_resolve_embedding_runtime_config,
    )
    monkeypatch.setattr(embeddings.httpx, "AsyncClient", FakeClient)

    result = await embeddings.embed_texts(["consulta sobre produtos"])

    assert len(result) == 1
    assert captured["url"] == "https://example.services.ai.azure.com/openai/v1/embeddings"
    assert captured["headers"]["Authorization"] == "Bearer plain-key"
    assert captured["json"] == {
        "model": "text-embedding-3-small",
        "input": ["consulta sobre produtos"],
        "dimensions": embeddings.EMBEDDING_DIM,
    }


def test_env_fallback_requires_explicit_embedding_settings(monkeypatch) -> None:
    monkeypatch.delenv("EMBEDDING_BASE_URL", raising=False)
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-key")

    assert embeddings._resolve_env_embedding_runtime_config() is None
