from __future__ import annotations

import base64
import logging
import os
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import httpx
from cryptography.fernet import Fernet

log = logging.getLogger(__name__)
EMBEDDING_DIM = 1536


@dataclass(frozen=True)
class EmbeddingConfig:
    base_url: str
    api_key: str
    model: str


@dataclass(frozen=True)
class LlmConfig:
    base_url: str
    api_key: str
    model: str
    api_format: str


async def resolve_embedding_config(db_url: str) -> EmbeddingConfig | None:
    row = await _fetch_model_config(db_url, capability="embedding", model_id=None)
    if row is None:
        return _env_embedding_config()
    api_key = _decrypt_secret(str(row["api_key_encrypted"] or ""))
    if not api_key:
        return _env_embedding_config()
    return EmbeddingConfig(
        base_url=_normalise_base_url(str(row["base_url"] or "")),
        api_key=api_key,
        model=str(row["model_id"] or ""),
    )


async def resolve_llm_config(db_url: str, model_id: str | None) -> LlmConfig | None:
    row = await _fetch_model_config(db_url, capability="text", model_id=model_id)
    if row is not None:
        api_key = _decrypt_secret(str(row["api_key_encrypted"] or ""))
        if api_key:
            return LlmConfig(
                base_url=_normalise_base_url(str(row["base_url"] or "")),
                api_key=api_key,
                model=str(row["model_id"] or ""),
                api_format=_normalise_api_format(str(row["api_format"] or "")),
            )
    return _env_llm_config(model_id)


async def embed_text(text: str, config: EmbeddingConfig | None) -> list[float] | None:
    results = await embed_texts([text], config)
    return results[0] if results else None


async def embed_texts(
    texts: list[str],
    config: EmbeddingConfig | None,
    *,
    batch_size: int = 64,
) -> list[list[float] | None]:
    if config is None:
        return [None for _ in texts]
    cleaned = [text.strip()[:8000] for text in texts]
    results: list[list[float] | None] = [None for _ in cleaned]
    non_empty = [(index, text) for index, text in enumerate(cleaned) if text]
    if not non_empty:
        return results
    async with httpx.AsyncClient(timeout=httpx.Timeout(90.0)) as client:
        for start in range(0, len(non_empty), batch_size):
            window = non_empty[start : start + batch_size]
            batch = [text for _, text in window]
            body: dict[str, object] = {"model": config.model, "input": batch}
            if config.model.lower().startswith("text-embedding-3-"):
                body["dimensions"] = EMBEDDING_DIM
            response = await client.post(
                f"{config.base_url.rstrip('/')}/embeddings",
                headers=_headers(config.api_key),
                json=body,
            )
            if response.status_code >= 400:
                log.warning(
                    "embedding request failed: HTTP %s %s",
                    response.status_code,
                    response.text[:200],
                )
                continue
            data = response.json()
            items = data.get("data") if isinstance(data, dict) else None
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                index = item.get("index")
                embedding = item.get("embedding")
                if isinstance(index, int) and isinstance(embedding, list):
                    absolute_index = (
                        window[index][0] if 0 <= index < len(window) else -1
                    )
                    if 0 <= absolute_index < len(results):
                        results[absolute_index] = embedding
    return results


async def _fetch_model_config(
    db_url: str,
    *,
    capability: str,
    model_id: str | None,
) -> asyncpg.Record | None:
    try:
        conn = await asyncpg.connect(db_url)
        try:
            if model_id:
                row = await conn.fetchrow(
                    """
                    SELECT m.model_id, p.base_url, p.api_key_encrypted, p.api_format
                    FROM ai_models m
                    JOIN ai_providers p ON p.id = m.provider_id
                    WHERE m.active = TRUE AND p.active = TRUE
                      AND m.capabilities ? $1 AND m.model_id = $2
                    LIMIT 1
                    """,
                    capability,
                    model_id,
                )
                if row:
                    return row
            return await conn.fetchrow(
                """
                SELECT m.model_id, p.base_url, p.api_key_encrypted, p.api_format
                FROM ai_models m
                JOIN ai_providers p ON p.id = m.provider_id
                WHERE m.active = TRUE AND p.active = TRUE AND m.capabilities ? $1
                ORDER BY COALESCE((m.is_default->>$1)::boolean, FALSE) DESC, m.display_name
                LIMIT 1
                """,
                capability,
            )
        finally:
            await conn.close()
    except Exception as exc:
        log.warning("failed to resolve %s provider config: %s", capability, exc)
        return None


def _env_embedding_config() -> EmbeddingConfig | None:
    api_key = os.getenv("EMBEDDING_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
    model = os.getenv("EMBEDDING_MODEL", "").strip()
    base_url = os.getenv("EMBEDDING_BASE_URL", "").strip()
    if not api_key or not model or not base_url:
        return None
    return EmbeddingConfig(
        base_url=_normalise_base_url(base_url), api_key=api_key, model=model
    )


def _env_llm_config(model_id: str | None) -> LlmConfig | None:
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENROUTER_API_KEY") or ""
    if not api_key:
        return None
    return LlmConfig(
        base_url=_normalise_base_url(
            os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
        ),
        api_key=api_key,
        model=model_id or os.getenv("LLM_MODEL") or "claude-sonnet-4-5",
        api_format=_normalise_api_format(
            os.getenv("LLM_API_FORMAT", "chat_completions")
        ),
    )


def _decrypt_secret(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    try:
        raw = (os.getenv("ENCRYPTION_KEY") or "0" * 64).strip()
        if len(raw) == 64 and all(c in "0123456789abcdefABCDEF" for c in raw):
            key = base64.urlsafe_b64encode(bytes.fromhex(raw))
        else:
            key = raw.encode()
        return Fernet(key).decrypt(ciphertext.encode()).decode()
    except Exception as exc:
        log.warning("failed to decrypt provider secret: %s", exc)
        return ""


def _headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def _normalise_api_format(value: str) -> str:
    return value if value in {"chat_completions", "responses"} else "chat_completions"


def _normalise_base_url(raw_url: str) -> str:
    raw = (raw_url or "").strip()
    parsed = urlsplit(raw)
    path = parsed.path.rstrip("/")
    lower_path = path.lower()
    for suffix in ("/responses", "/chat/completions", "/embeddings"):
        if lower_path.endswith(suffix):
            path = path[: -len(suffix)]
            lower_path = path.lower()
            break
    host = parsed.netloc.split("@")[-1].split(":")[0].lower()
    if host.endswith(".services.ai.azure.com") and (
        not path or _path_has_project_openai_v1(path)
    ):
        path = "/openai/v1"
    return urlunsplit((parsed.scheme, parsed.netloc, path.rstrip("/"), "", ""))


def _path_has_project_openai_v1(path: str) -> bool:
    parts = [part.lower() for part in path.strip("/").split("/") if part]
    return (
        len(parts) >= 5
        and parts[:2] == ["api", "projects"]
        and parts[-2:]
        == [
            "openai",
            "v1",
        ]
    )
