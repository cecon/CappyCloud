"""Gravação automática da memória do workspace depois de cada turno.

O agente quase nunca grava por iniciativa própria. Ao fim de um turno com
resposta, o runner chama ``POST /memory/extract`` no sandbox, que extrai da
pergunta e da resposta só o que foi confirmado e grava no agentmemory. Roda em
segundo plano: falha aqui nunca afeta a conversa.
"""

from __future__ import annotations

import asyncio
import logging
import os
import posixpath
from dataclasses import dataclass

import httpx

from ._workspace_paths import workspace_root_of

log = logging.getLogger(__name__)

# Uma volta do modelo sem ferramentas; folga para fila do login do Claude.
_EXTRACT_TIMEOUT_S = 180.0
_background: set[asyncio.Task] = set()


@dataclass(frozen=True)
class MemoryCapture:
    session_url: str
    workspace: str
    question: str
    model: str


def memory_capture_for(
    *,
    session_url: str,
    session_root: str | None,
    question: str | None,
    model: str,
    claude_cli: bool,
) -> MemoryCapture | None:
    """Só sessão de workspace no Claude CLI: a extração usa o login do sandbox."""
    root = workspace_root_of(session_root)
    if not (claude_cli and root and session_url and (question or "").strip()):
        return None
    return MemoryCapture(session_url, posixpath.basename(root), question or "", model)


async def capture_turn_memory(capture: MemoryCapture, answer: str) -> int:
    """Pede a extração ao sandbox; devolve quantas memórias foram gravadas (0 em erro)."""
    if not answer.strip():
        return 0
    try:
        async with httpx.AsyncClient(timeout=_EXTRACT_TIMEOUT_S) as client:
            resp = await client.post(
                f"{capture.session_url.rstrip('/')}/memory/extract",
                json={
                    "workspace": capture.workspace,
                    "question": capture.question,
                    "answer": answer,
                    "model": capture.model,
                },
                headers={"X-Internal-Token": os.getenv("INTERNAL_API_TOKEN", "").strip()},
            )
        resp.raise_for_status()
        saved = int(resp.json().get("saved") or 0)
        if saved:
            log.info("[memory] %s: %d memória(s) gravada(s)", capture.workspace, saved)
        return saved
    except Exception as exc:
        log.warning("[memory] extração falhou em %s: %s", capture.workspace, exc)
        return 0


def schedule_turn_memory(capture: MemoryCapture | None, answer: str) -> None:
    """Dispara a extração sem esperar (guarda a referência até terminar)."""
    if capture is None or not answer.strip():
        return
    task = asyncio.create_task(capture_turn_memory(capture, answer), name="memory-capture")
    _background.add(task)
    task.add_done_callback(_background.discard)
