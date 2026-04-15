"""
Geração de embeddings com sentence-transformers (local, sem API externa).
Modelo padrão: all-MiniLM-L6-v2 (384 dims, ~80 MB, CPU-friendly).
"""
from __future__ import annotations

import logging
from typing import Any

from .config import settings

log = logging.getLogger(__name__)

_model: Any = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer  # type: ignore
        log.info("Carregando modelo de embeddings: %s", settings.embedding_model)
        _model = SentenceTransformer(settings.embedding_model)
        log.info("Modelo carregado.")
    return _model


def embed(texts: list[str]) -> list[list[float]]:
    """
    Gera embeddings para uma lista de textos.
    Retorna lista de vetores float (dimensão depende do modelo).
    """
    if not texts:
        return []
    model = _get_model()
    vectors = model.encode(
        texts,
        batch_size=settings.embedding_batch_size,
        show_progress_bar=False,
        normalize_embeddings=True,
    )
    return [v.tolist() for v in vectors]


def embed_one(text: str) -> list[float]:
    return embed([text])[0]
