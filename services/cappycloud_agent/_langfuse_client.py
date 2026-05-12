"""Cliente Langfuse partilhado para telemetria de agentes.

Degrada graciosamente: se ``LANGFUSE_PUBLIC_KEY`` / ``LANGFUSE_SECRET_KEY`` não
estiverem definidas (ou se o pacote não estiver instalado) ``get_langfuse()``
devolve ``None`` e o resto do código segue normal.

O host default é ``http://langfuse-web:3000`` (nome do serviço dentro da
rede ``cappycloud_net``). Em produção, sobrescrever via ``LANGFUSE_HOST``.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

log = logging.getLogger(__name__)

_client: Any = None
_initialized = False


def get_langfuse() -> Optional[Any]:
    """Devolve um Langfuse client cacheado, ou ``None`` se desactivado."""
    global _client, _initialized
    if _initialized:
        return _client
    _initialized = True

    pub = os.getenv("LANGFUSE_PUBLIC_KEY")
    sec = os.getenv("LANGFUSE_SECRET_KEY")
    if not pub or not sec:
        log.info("Langfuse desactivado (chaves ausentes)")
        return None

    try:
        from langfuse import Langfuse  # type: ignore[import-not-found]
    except ImportError:
        log.warning("pacote 'langfuse' não instalado — telemetria desactivada")
        return None

    try:
        _client = Langfuse(
            public_key=pub,
            secret_key=sec,
            host=os.getenv("LANGFUSE_HOST", "http://langfuse-web:3000"),
        )
        log.info("Langfuse iniciado (host=%s)", os.getenv("LANGFUSE_HOST"))
    except Exception as exc:  # noqa: BLE001 — falha silenciosa
        log.error("falha a iniciar Langfuse: %s", exc)
        _client = None

    return _client


def flush() -> None:
    """Força envio de eventos pendentes (chamar no shutdown)."""
    if _client is not None:
        try:
            _client.flush()
        except Exception:  # noqa: BLE001
            pass
