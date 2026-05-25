"""Cliente de embeddings OpenAI-compatible.

O runtime resolve primeiro o modelo default de embedding no catálogo ``ai_models``.
As variáveis ``EMBEDDING_*`` continuam como fallback operacional.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import httpx

from app.infrastructure.azure_foundry_models import normalize_azure_openai_v1_base_url
from app.infrastructure.config import get_settings
from app.infrastructure.encryption import get_encryptor

log = logging.getLogger(__name__)

EMBEDDING_DIM = 1536


class EmbeddingError(RuntimeError):
    """Erro ao calcular embedding."""


@dataclass(frozen=True)
class EmbeddingRuntimeConfig:
    base_url: str
    api_key: str
    model: str


async def embed_text(text: str) -> list[float] | None:
    """Calcula o embedding de um texto único; devolve None em caso de falha."""
    res = await embed_texts([text])
    return res[0] if res else None


async def embed_texts(texts: Iterable[str]) -> list[list[float]]:
    """Calcula embeddings em batch.

    Retorna lista vazia se a chave de API não estiver configurada (modo degradado).
    Lança ``EmbeddingError`` em caso de erro de rede/HTTP.
    """
    payload_inputs = [t.strip()[:8000] for t in texts if t and t.strip()]
    if not payload_inputs:
        return []

    config = await resolve_embedding_runtime_config()
    if config is None:
        log.warning("Embedding provider não configurado — RAG por LIKE")
        return []

    url = f"{config.base_url.rstrip('/')}/embeddings"
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }
    body: dict[str, object] = {"model": config.model, "input": payload_inputs}
    if _supports_custom_dimensions(config.model):
        body["dimensions"] = EMBEDDING_DIM

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            r = await client.post(url, headers=headers, json=body)
            if r.status_code >= 400:
                raise EmbeddingError(f"HTTP {r.status_code}: {r.text[:300]}")
            data = r.json()
    except httpx.HTTPError as exc:
        raise EmbeddingError(str(exc)) from exc

    embeddings: list[list[float]] = []
    for item in data.get("data", []):
        emb = item.get("embedding")
        if isinstance(emb, list) and len(emb) == EMBEDDING_DIM:
            embeddings.append(emb)
        elif isinstance(emb, list):
            log.warning(
                "Embedding ignorado: dimensão %d diferente de %d para modelo %s",
                len(emb),
                EMBEDDING_DIM,
                config.model,
            )
    return embeddings


async def resolve_embedding_runtime_config() -> EmbeddingRuntimeConfig | None:
    """Resolve o modelo default de embedding do banco, com fallback por env vars."""
    dynamic = await _resolve_db_embedding_runtime_config()
    if dynamic is not None:
        return dynamic
    return _resolve_env_embedding_runtime_config()


async def _resolve_db_embedding_runtime_config() -> EmbeddingRuntimeConfig | None:
    database_url = _database_url()
    if not database_url:
        return None
    try:
        conn = await asyncpg.connect(database_url)
        try:
            row = await conn.fetchrow(
                """
                SELECT m.model_id, p.base_url, p.api_key_encrypted
                FROM ai_models m
                JOIN ai_providers p ON p.id = m.provider_id
                WHERE m.active = TRUE
                  AND p.active = TRUE
                  AND m.capabilities ? 'embedding'
                ORDER BY
                  COALESCE((m.is_default->>'embedding')::boolean, FALSE) DESC,
                  m.display_name
                LIMIT 1
                """
            )
        finally:
            await conn.close()
        if not row:
            return None
        api_key = _decrypt_secret(str(row["api_key_encrypted"] or ""))
        if not api_key:
            log.warning("Modelo de embedding ativo não tem chave de provider configurada.")
            return None
        base_url = _normalise_embedding_base_url(str(row["base_url"] or ""))
        model = str(row["model_id"] or "").strip()
        if not base_url or not model:
            return None
        return EmbeddingRuntimeConfig(base_url=base_url, api_key=api_key, model=model)
    except Exception as exc:
        log.warning("Falha ao resolver modelo de embedding no catálogo: %s", exc)
        return None


def _resolve_env_embedding_runtime_config() -> EmbeddingRuntimeConfig | None:
    base_url_raw = os.getenv("EMBEDDING_BASE_URL", "").strip()
    model = os.getenv("EMBEDDING_MODEL", "").strip()
    api_key = os.getenv("EMBEDDING_API_KEY", "").strip()
    if not api_key and base_url_raw and model:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    base_url = _normalise_embedding_base_url(base_url_raw)
    if not base_url or not model:
        return None
    return EmbeddingRuntimeConfig(base_url=base_url, api_key=api_key, model=model)


def _supports_custom_dimensions(model: str) -> bool:
    """OpenAI/Azure text-embedding-3 models can return vectors at a chosen size."""
    return model.strip().lower().startswith("text-embedding-3-")


def _database_url() -> str:
    return get_settings().database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


def _decrypt_secret(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    try:
        return get_encryptor().decrypt(ciphertext)
    except Exception as exc:
        log.warning("Falha ao decriptar chave do provider de embedding: %s", exc)
        return ""


def _normalise_embedding_base_url(raw_url: str) -> str:
    raw = (raw_url or "").strip()
    if not raw:
        return ""
    normalized = normalize_azure_openai_v1_base_url(raw)
    parsed = urlsplit(normalized)
    path = parsed.path.rstrip("/")
    lower_path = path.lower()
    for suffix in ("/embeddings", "/responses", "/chat/completions"):
        if lower_path.endswith(suffix):
            path = path[: -len(suffix)]
            break
    return urlunsplit((parsed.scheme, parsed.netloc, path.rstrip("/"), "", ""))
