"""AI model catalog use cases."""

from __future__ import annotations

import uuid

from app.domain.entities import AiModel
from app.ports.services import ModelCatalogService


class ListAiModels:
    """List local models enriched with the external OpenRouter catalog."""

    def __init__(self, catalog: ModelCatalogService) -> None:
        self._catalog = catalog

    async def execute(
        self,
        local_models: list[AiModel],
        provider_id: uuid.UUID,
    ) -> list[AiModel]:
        """Merge locally configured models with models currently advertised by OpenRouter."""
        merged = {model.model_id: model for model in local_models}

        try:
            external_models = await self._catalog.list_models(provider_id)
        except Exception:
            external_models = []

        for model in external_models:
            merged.setdefault(model.model_id, model)

        return sorted(merged.values(), key=lambda model: model.display_name.lower())
