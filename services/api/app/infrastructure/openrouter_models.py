"""Cliente para o catálogo de modelos do OpenRouter.

Faz ``GET https://openrouter.ai/api/v1/models`` e normaliza o resultado para o
formato interno (mesmas colunas que ``ai_models``). Os preços do OpenRouter
vêm em **USD por token** (string); convertemos para **USD por 1 milhão de
tokens** que é o formato standard usado em interfaces e cobrança.
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict

import httpx

log = logging.getLogger(__name__)

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
_TIMEOUT_SECONDS = 30.0


class NormalizedModel(TypedDict):
    """Representação interna de um modelo OpenRouter já normalizada."""

    model_id: str
    display_name: str
    context_window: int
    input_cost_per_1m_usd: float | None
    output_cost_per_1m_usd: float | None
    capabilities: list[str]


def is_free_text_model(model_id: str, capabilities: list[str]) -> bool:
    """True para modelos OpenRouter grátis que servem como LLM de texto."""
    return "text" in capabilities and (model_id.endswith(":free") or model_id == "openrouter/free")


def is_free_text_entry(entry: NormalizedModel) -> bool:
    """Versão do predicado para entradas já normalizadas do catálogo."""
    return is_free_text_model(entry["model_id"], entry["capabilities"])


def filter_text_entries(entries: list[NormalizedModel]) -> list[NormalizedModel]:
    """Mantém o catálogo admin completo de modelos de texto, grátis e pagos."""
    return [entry for entry in entries if "text" in entry["capabilities"]]


def _to_per_1m(price_str: Any) -> float | None:
    """Converte preço do OpenRouter (USD/token, string) para USD por 1M tokens.

    Devolve ``None`` quando o preço está ausente, não é parseável ou é
    negativo (o OpenRouter usa ``-1`` como sentinela de modelo "BYOK only",
    que não tem preço público). Mantém o ``0.0`` (modelos free) como zero —
    útil para distinguir "free" de "preço desconhecido".
    """
    if price_str is None or price_str == "":
        return None
    try:
        per_token = float(price_str)
    except TypeError, ValueError:
        return None
    if per_token < 0:
        return None
    return round(per_token * 1_000_000, 6)


def _extract_capabilities(architecture: dict[str, Any] | None) -> list[str]:
    """Mapeia ``architecture.input_modalities`` para o nosso formato.

    Sempre incluímos ``"text"``. Adicionamos ``"vision"``/``"audio"``/``"video"``
    quando o modelo suporta inputs desses tipos.
    """
    caps: list[str] = ["text"]
    if not isinstance(architecture, dict):
        return caps
    inputs = architecture.get("input_modalities") or []
    if not isinstance(inputs, list):
        return caps
    if "image" in inputs:
        caps.append("vision")
    if "audio" in inputs:
        caps.append("audio")
    if "video" in inputs:
        caps.append("video")
    return caps


def _normalize(raw: dict[str, Any]) -> NormalizedModel | None:
    """Converte um item do JSON do OpenRouter num ``NormalizedModel``.

    Devolve ``None`` quando faltam campos obrigatórios (id/name).
    """
    model_id = raw.get("id")
    name = raw.get("name") or model_id
    if not isinstance(model_id, str) or not model_id:
        return None
    pricing = raw.get("pricing") or {}
    architecture = raw.get("architecture") or {}
    context_window_raw = raw.get("context_length") or raw.get("top_provider", {}).get(
        "context_length"
    )
    try:
        context_window = int(context_window_raw or 0) or 200_000
    except TypeError, ValueError:
        context_window = 200_000
    return NormalizedModel(
        model_id=model_id,
        display_name=str(name),
        context_window=context_window,
        input_cost_per_1m_usd=_to_per_1m(pricing.get("prompt")),
        output_cost_per_1m_usd=_to_per_1m(pricing.get("completion")),
        capabilities=_extract_capabilities(architecture),
    )


async def fetch_openrouter_models(
    api_key: str | None = None,
    url: str = OPENROUTER_MODELS_URL,
    timeout: float = _TIMEOUT_SECONDS,
) -> list[NormalizedModel]:
    """Busca o catálogo do OpenRouter e devolve uma lista normalizada.

    A API é pública (não exige auth), mas se ``api_key`` for fornecido vai
    como ``Authorization: Bearer`` para garantir rate limit individual em vez
    do partilhado. Modelos sem ``id`` são descartados silenciosamente.
    """
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(url, headers=headers)
    resp.raise_for_status()
    payload = resp.json() or {}
    raw_list = payload.get("data") or []
    out: list[NormalizedModel] = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        normalized = _normalize(item)
        if normalized is not None:
            out.append(normalized)
    log.info("OpenRouter: %d modelos normalizados", len(out))
    return out
