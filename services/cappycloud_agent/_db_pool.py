"""Pools asyncpg que sobrevivem a longos períodos sem uso.

A rede overlay do Swarm descarta conexões TCP paradas por muito tempo sem
avisar nenhum dos lados. A API só descobria na consulta seguinte
("connection was closed in the middle of operation") e a conversa ficava sem
resposta. Keepalive do servidor mantém a conexão viva; o tempo máximo de
inatividade fecha as que sobrarem antes de qualquer timeout de rede.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

import asyncpg

log = logging.getLogger(__name__)

KEEPALIVE_SETTINGS = {
    "tcp_keepalives_idle": "30",
    "tcp_keepalives_interval": "10",
    "tcp_keepalives_count": "3",
}
MAX_INACTIVE_SECONDS = 60.0

DISCONNECT_ERRORS: tuple[type[BaseException], ...] = (
    asyncpg.exceptions.ConnectionDoesNotExistError,
    ConnectionResetError,
    BrokenPipeError,
)


async def create_pool(dsn: str, *, min_size: int, max_size: int) -> asyncpg.Pool:
    """Cria um pool com keepalive e descarte de conexões ociosas."""
    return await asyncpg.create_pool(
        dsn,
        min_size=min_size,
        max_size=max_size,
        max_inactive_connection_lifetime=MAX_INACTIVE_SECONDS,
        server_settings=KEEPALIVE_SETTINGS,
    )


async def retry_read[T](op: Callable[[], Awaitable[T]]) -> T:
    """Executa uma leitura e repete uma vez se a conexão tiver caído.

    Só para consultas sem efeito colateral: o pool descarta a conexão quebrada
    e a segunda tentativa usa outra.
    """
    try:
        return await op()
    except DISCONNECT_ERRORS as exc:
        log.warning("Conexão com o Postgres caiu (%s); repetindo a leitura.", exc)
        return await op()
