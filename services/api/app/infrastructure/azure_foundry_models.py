"""Azure AI Foundry deployment catalog client."""

from __future__ import annotations

import logging
from typing import Any, TypedDict
from urllib.parse import urlsplit, urlunsplit

import httpx

log = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 30.0
_AZURE_FOUNDRY_HOST_SUFFIX = ".services.ai.azure.com"
_KNOWN_PRICING_PER_1M_USD: dict[str, tuple[float, float]] = {
    "deepseek-v4-flash": (0.19, 0.51),
    "deepseek-v4-pro": (1.74, 3.48),
    "gpt-5-chat": (1.25, 10.0),
    "gpt-5.4": (2.5, 15.0),
    "gpt-5.4-mini": (0.75, 4.5),
    "kimi-k2.6": (0.95, 4.0),
    "kimi-k2.6-1": (0.95, 4.0),
    "text-embedding-3-large": (0.143, 0.0),
}


class AzureFoundryDeployment(TypedDict):
    """Normalized Azure deployment entry for ai_models."""

    model_id: str
    display_name: str
    context_window: int
    input_cost_per_1m_usd: float | None
    output_cost_per_1m_usd: float | None
    capabilities: list[str]


def is_azure_foundry_endpoint(raw_url: str) -> bool:
    parsed = urlsplit((raw_url or "").strip())
    host = parsed.netloc.split("@")[-1].split(":")[0].lower()
    return host.endswith(_AZURE_FOUNDRY_HOST_SUFFIX)


def normalize_azure_openai_v1_base_url(raw_url: str) -> str:
    """Return the OpenAI-compatible v1 base URL for Azure AI Foundry."""
    raw = (raw_url or "").strip()
    if not raw:
        return raw
    parsed = urlsplit(raw)
    path = parsed.path.rstrip("/")
    lower_path = path.lower()
    if lower_path.endswith("/responses"):
        path = path[: -len("/responses")]
        lower_path = path.lower()
    elif lower_path.endswith("/chat/completions"):
        path = path[: -len("/chat/completions")]
        lower_path = path.lower()

    if not is_azure_foundry_endpoint(raw):
        return urlunsplit((parsed.scheme, parsed.netloc, path.rstrip("/"), "", ""))

    if not path or _path_has_project_openai_v1(lower_path):
        path = "/openai/v1"
    return urlunsplit((parsed.scheme, parsed.netloc, path.rstrip("/"), "", ""))


async def fetch_azure_foundry_deployments(
    *,
    base_url: str,
    api_key: str,
    timeout: float = _TIMEOUT_SECONDS,
) -> list[AzureFoundryDeployment]:
    """Fetch Azure AI Foundry project deployments.

    The OpenAI-compatible ``/openai/v1/models`` endpoint lists base models
    available in the region. For the admin catalog we need project deployments,
    because those names are the values the runtime must send as ``model``.
    """
    if not api_key:
        raise ValueError("Azure Foundry API key is required for sync.")

    last_error: str | None = None
    urls = _deployment_catalog_urls(base_url)
    async with httpx.AsyncClient(timeout=timeout) as client:
        for url in urls:
            response = await client.get(url, headers={"Authorization": f"Bearer {api_key}"})
            if response.status_code == 200:
                deployments = _normalize_deployments(response.json())
                log.info("Azure Foundry: %d deployments normalized", len(deployments))
                return deployments
            last_error = f"{response.status_code}: {response.text[:300]}"
            if response.status_code not in {404, 405}:
                response.raise_for_status()

    raise RuntimeError(
        "Could not list Azure Foundry deployments. "
        "Use the project endpoint URL when the default project name cannot be inferred. "
        f"Last response: {last_error or 'no response'}"
    )


def _deployment_catalog_urls(raw_url: str) -> list[str]:
    parsed = urlsplit((raw_url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return []
    projects: list[str] = []
    path_project = _project_name_from_path(parsed.path)
    if path_project:
        projects.append(path_project)
    host_project = _project_name_from_host(parsed.netloc)
    if host_project:
        projects.append(host_project)

    urls: list[str] = []
    seen: set[str] = set()
    for project in projects:
        if project in seen:
            continue
        seen.add(project)
        urls.append(
            urlunsplit(
                (
                    parsed.scheme,
                    parsed.netloc,
                    f"/api/projects/{project}/deployments",
                    "api-version=v1",
                    "",
                )
            )
        )
    return urls


def _project_name_from_path(path: str) -> str | None:
    parts = [part for part in path.strip("/").split("/") if part]
    if len(parts) >= 3 and parts[0] == "api" and parts[1] == "projects":
        return parts[2]
    return None


def _project_name_from_host(netloc: str) -> str | None:
    host = netloc.split("@")[-1].split(":")[0].lower()
    if not host.endswith(_AZURE_FOUNDRY_HOST_SUFFIX):
        return None
    resource_name = host.split(".", 1)[0]
    return f"{resource_name}_project" if resource_name else None


def _path_has_project_openai_v1(lower_path: str) -> bool:
    parts = [part for part in lower_path.strip("/").split("/") if part]
    return (
        len(parts) >= 5
        and parts[:2] == ["api", "projects"]
        and parts[-2:]
        == [
            "openai",
            "v1",
        ]
    )


def _normalize_deployments(payload: Any) -> list[AzureFoundryDeployment]:
    raw_items = payload.get("value") if isinstance(payload, dict) else None
    if not isinstance(raw_items, list):
        return []
    deployments: list[AzureFoundryDeployment] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        deployment = _normalize_deployment(item)
        if deployment is not None:
            deployments.append(deployment)
    return deployments


def _normalize_deployment(item: dict[str, Any]) -> AzureFoundryDeployment | None:
    model_id = item.get("name")
    if not isinstance(model_id, str) or not model_id.strip():
        return None
    normalized_model_id = model_id.strip()
    capabilities = _capabilities(item.get("capabilities"))
    if not capabilities:
        return None
    pricing = _known_pricing(normalized_model_id)
    return AzureFoundryDeployment(
        model_id=normalized_model_id,
        display_name=normalized_model_id,
        context_window=200000,
        input_cost_per_1m_usd=pricing[0] if pricing else None,
        output_cost_per_1m_usd=pricing[1] if pricing else None,
        capabilities=capabilities,
    )


def _known_pricing(model_id: str) -> tuple[float, float] | None:
    key = model_id.strip().lower().replace("_", "-")
    return _KNOWN_PRICING_PER_1M_USD.get(key)


def _capabilities(raw: Any) -> list[str]:
    if not isinstance(raw, dict):
        return ["text"]
    capabilities: set[str] = set()
    if _truthy(raw.get("chat_completion")):
        capabilities.add("text")
    if _truthy(raw.get("embeddings")):
        capabilities.add("embedding")
    if _truthy(raw.get("image_generation")):
        capabilities.add("image")
    return sorted(capabilities)


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)
