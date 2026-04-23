"""Cliente de embeddings (OpenAI text-embedding-3-small, 1536 dims).

Suporta também a forma compatível OpenRouter (mesma API). Quando ``OPENAI_API_KEY``
e ``OPENAI_BASE_URL`` estão configurados, usa-os; senão tenta as vars do projeto
(``OPENROUTER_API_KEY``).
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterable

import httpx

log = logging.getLogger(__name__)

EMBEDDING_DIM = 1536
# Default: OpenRouter compat-OpenAI; o ID inclui o provider (``openai/...``).
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "openai/text-embedding-3-small")
_EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "https://openrouter.ai/api/v1")
# Aceita EMBEDDING_API_KEY explícita; senão OPENROUTER_API_KEY; senão OPENAI_API_KEY.
_EMBEDDING_API_KEY = (
    os.getenv("EMBEDDING_API_KEY")
    or os.getenv("OPENROUTER_API_KEY")
    or os.getenv("OPENAI_API_KEY")
    or ""
)


class EmbeddingError(RuntimeError):
    """Erro ao calcular embedding."""


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

    if not _EMBEDDING_API_KEY:
        log.warning("EMBEDDING_API_KEY não configurada — embeddings desactivados (RAG por LIKE)")
        return []

    url = f"{_EMBEDDING_BASE_URL.rstrip('/')}/embeddings"
    headers = {
        "Authorization": f"Bearer {_EMBEDDING_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {"model": EMBEDDING_MODEL, "input": payload_inputs}

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
    return embeddings
