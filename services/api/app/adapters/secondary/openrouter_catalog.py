"""OpenRouter model catalog adapter."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import httpx

from app.domain.entities import AiModel
from app.ports.services import ModelCatalogService

_MODELS_URL = "https://openrouter.ai/api/v1/models"
_MODEL_NAMESPACE = uuid.UUID("90d6c836-f786-4fc4-9079-8a891f5f59d5")


class OpenRouterModelCatalog(ModelCatalogService):
    """Fetch the public model catalog from OpenRouter."""

    async def list_models(self, provider_id: uuid.UUID) -> list[AiModel]:
        """Return all models currently listed by OpenRouter."""
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            response = await client.get(_MODELS_URL, headers={"User-Agent": "CappyCloud"})
            response.raise_for_status()

        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            return []

        return [
            self._to_model(item, provider_id)
            for item in data
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        ]

    def _to_model(self, item: dict[str, Any], provider_id: uuid.UUID) -> AiModel:
        model_id = item["id"]
        display_name = str(item.get("name") or model_id)
        context_window = self._context_window(item)

        return AiModel(
            id=uuid.uuid5(_MODEL_NAMESPACE, model_id),
            provider_id=provider_id,
            model_id=model_id,
            display_name=display_name,
            capabilities=self._capabilities(item),
            is_default={},
            context_window=context_window,
            active=True,
            created_at=datetime.now(UTC),
        )

    def _context_window(self, item: dict[str, Any]) -> int:
        value = item.get("context_length") or item.get("context_window")
        if isinstance(value, int) and value > 0:
            return value
        return 200000

    def _capabilities(self, item: dict[str, Any]) -> list[str]:
        architecture = item.get("architecture")
        modalities: set[str] = set()
        if isinstance(architecture, dict):
            for key in ("modality", "input_modalities", "output_modalities"):
                self._collect_modalities(architecture.get(key), modalities)

        capabilities = {"text"}
        if {"image", "vision"} & modalities:
            capabilities.add("vision")
        if "embedding" in modalities or "embedding" in str(item.get("id", "")).lower():
            capabilities.add("embedding")
        if "video" in modalities:
            capabilities.add("video")

        return sorted(capabilities)

    def _collect_modalities(self, value: Any, modalities: set[str]) -> None:
        if isinstance(value, str):
            modalities.update(part.strip().lower() for part in value.replace("+", ",").split(","))
        elif isinstance(value, list):
            modalities.update(str(part).strip().lower() for part in value)
