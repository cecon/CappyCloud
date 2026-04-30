"""Unit tests for the OpenRouter models adapter.

Cobre normalização de pricing (incluindo a sentinela ``-1`` que sinaliza
modelos BYOK), extração de capabilities e o fetch HTTP com mock.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from app.infrastructure import openrouter_models as adapter


class TestToPer1M:
    """Conversão preço-por-token (string) → preço-por-1M-tokens (float)."""

    def test_none_returns_none(self) -> None:
        assert adapter._to_per_1m(None) is None

    def test_empty_string_returns_none(self) -> None:
        assert adapter._to_per_1m("") is None

    def test_garbage_returns_none(self) -> None:
        assert adapter._to_per_1m("abc") is None

    def test_negative_returns_none(self) -> None:
        # OpenRouter usa -1 como "BYOK only" — não persistir como preço real.
        assert adapter._to_per_1m("-1") is None

    def test_zero_stays_zero(self) -> None:
        # Modelos free devem persistir como 0 para distinguir de "preço desconhecido".
        assert adapter._to_per_1m("0") == 0.0

    def test_normal_value_scales_to_per_1m(self) -> None:
        # 0.0000025 USD/token → 2.50 USD/1M tokens (gpt-4o)
        assert adapter._to_per_1m("0.0000025") == 2.5

    def test_rounds_to_six_decimals(self) -> None:
        result = adapter._to_per_1m("0.00000012345678")
        assert result is not None
        assert result == round(result, 6)


class TestExtractCapabilities:
    def test_default_text_only(self) -> None:
        assert adapter._extract_capabilities(None) == ["text"]
        assert adapter._extract_capabilities({}) == ["text"]

    def test_image_adds_vision(self) -> None:
        caps = adapter._extract_capabilities({"input_modalities": ["text", "image"]})
        assert "vision" in caps
        assert "text" in caps

    def test_audio_and_video(self) -> None:
        caps = adapter._extract_capabilities({"input_modalities": ["text", "audio", "video"]})
        assert set(caps) == {"text", "audio", "video"}


class TestNormalize:
    def test_minimal_payload(self) -> None:
        result = adapter._normalize(
            {
                "id": "openai/gpt-4o-mini",
                "name": "OpenAI: GPT-4o Mini",
                "context_length": 128000,
                "pricing": {"prompt": "0.00000015", "completion": "0.00000060"},
                "architecture": {"input_modalities": ["text"]},
            }
        )
        assert result is not None
        assert result["model_id"] == "openai/gpt-4o-mini"
        assert result["context_window"] == 128000
        assert result["input_cost_per_1m_usd"] == 0.15
        assert result["output_cost_per_1m_usd"] == 0.6
        assert result["capabilities"] == ["text"]

    def test_missing_id_returns_none(self) -> None:
        assert adapter._normalize({"name": "noop"}) is None
        assert adapter._normalize({"id": "", "name": "noop"}) is None

    def test_byok_negative_pricing_drops_to_none(self) -> None:
        result = adapter._normalize(
            {
                "id": "openrouter/pareto-code",
                "name": "Pareto Code",
                "pricing": {"prompt": "-1", "completion": "-1"},
                "context_length": 200000,
            }
        )
        assert result is not None
        assert result["input_cost_per_1m_usd"] is None
        assert result["output_cost_per_1m_usd"] is None

    def test_default_context_when_missing(self) -> None:
        result = adapter._normalize({"id": "x/y", "name": "X", "pricing": {}})
        assert result is not None
        assert result["context_window"] == 200_000


class TestFetchOpenRouterModels:
    @pytest.mark.asyncio
    async def test_fetch_normalizes_and_filters(self, monkeypatch: pytest.MonkeyPatch) -> None:
        payload: dict[str, Any] = {
            "data": [
                {
                    "id": "openai/gpt-4o-mini",
                    "name": "OpenAI GPT-4o Mini",
                    "context_length": 128000,
                    "pricing": {"prompt": "0.00000015", "completion": "0.00000060"},
                    "architecture": {"input_modalities": ["text", "image"]},
                },
                {
                    "id": "openrouter/pareto-code",
                    "name": "Pareto Code (BYOK)",
                    "pricing": {"prompt": "-1", "completion": "-1"},
                    "context_length": 200000,
                    "architecture": {"input_modalities": ["text"]},
                },
                # Sem id — deve ser descartado
                {"name": "no-id"},
                # Não-dict — deve ser descartado
                "noop",
            ]
        }

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=json.dumps(payload))

        transport = httpx.MockTransport(handler)
        original_client = httpx.AsyncClient

        def patched_client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
            kwargs["transport"] = transport
            return original_client(*args, **kwargs)

        monkeypatch.setattr(httpx, "AsyncClient", patched_client)

        models = await adapter.fetch_openrouter_models()
        assert len(models) == 2
        ids = [m["model_id"] for m in models]
        assert ids == ["openai/gpt-4o-mini", "openrouter/pareto-code"]
        assert models[0]["input_cost_per_1m_usd"] == 0.15
        assert "vision" in models[0]["capabilities"]
        assert models[1]["input_cost_per_1m_usd"] is None
