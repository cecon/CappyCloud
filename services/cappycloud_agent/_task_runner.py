"""TaskRunner — executa uma AgentTask de forma autônoma.

Persiste todos os eventos gRPC no banco de dados (tabela agent_events) e
atualiza o status da task (agent_tasks) durante o ciclo de vida. Não depende
de nenhum cliente HTTP estar conectado — corre como asyncio.Task independente.

Ciclo de vida:
  1. run() arranca → status = running
  2. Para cada evento do stream gRPC → INSERT agent_events
  3. ActionRequired → status = paused (aguarda send_input ou auto-approve)
  4. done / error → status = done | error
  5. On Pipeline restart → TaskDispatcher reconecta tasks running/paused órfãs
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import asyncpg

from ._grpc_helpers import PendingAction
from ._grpc_session import GrpcSession
from ._task_usage import persist_usage

log = logging.getLogger(__name__)

# Janela de silêncio (sem QUALQUER evento do stream gRPC) antes de matar a
# sessão. Em tasks longas de análise/relatório o LLM pode passar minutos a
# pensar entre chunks; um valor pequeno mata investigações legítimas. Cada
# chunk recebido reinicia o relógio (ver _run loop).
STREAM_IDLE_TIMEOUT_S = float(os.getenv("AGENT_STREAM_IDLE_TIMEOUT_S", "900"))


class TaskRunner:
    """Wraps a GrpcSession e persiste todos os eventos no DB."""

    def __init__(
        self,
        task_id: str,
        session: GrpcSession,
        db_url: str,
        model_used: str = "",
    ) -> None:
        self._task_id = task_id
        self._session = session
        self._db_url = db_url
        self._model_used = model_used
        self._pool: Optional[asyncpg.Pool] = None
        self._task: Optional[asyncio.Task] = None

    # ── Public API ────────────────────────────────────────────────

    async def start(self) -> None:
        """Inicia a task de execução em background."""
        self._pool = await asyncpg.create_pool(self._db_url, min_size=1, max_size=3)
        self._task = asyncio.create_task(
            self._run(), name=f"runner-{self._task_id[:8]}"
        )

    async def send_input(self, reply: str) -> None:
        """Repassa a resposta do utilizador ao stream gRPC pausado."""
        await self._session.send_input(reply)

    async def send_message(
        self,
        message: str,
        attachments: list[dict] | None = None,
    ) -> None:
        """Envia uma nova mensagem numa sessão já activa."""
        await self._session.send_message(message, attachments=attachments)

    def is_alive(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def pending_action(self) -> Optional[PendingAction]:
        return self._session.pending_action

    async def close(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._session.close()
        if self._pool:
            await self._pool.close()

    # ── Internal ──────────────────────────────────────────────────

    async def _run(self) -> None:
        """Loop principal: drena o stream gRPC e persiste eventos no DB.

        O timeout (``STREAM_IDLE_TIMEOUT_S``) reinicia a cada evento recebido —
        é uma janela de silêncio, não um wall-clock total. Permite tasks de
        análise/relatório de 30+ min desde que o LLM emita chunks regulares.
        """
        await self._update_task(status="running", started_at=_now())
        agent_stage_marked = False
        try:
            while True:
                try:
                    event_type, data = await asyncio.wait_for(
                        self._session._out_queue.get(),
                        timeout=STREAM_IDLE_TIMEOUT_S,
                    )
                except asyncio.TimeoutError:
                    minutes = int(STREAM_IDLE_TIMEOUT_S // 60)
                    await self._insert_event(
                        "timeout",
                        {"message": f"Stream silencioso por {minutes} min."},
                    )
                    await self._update_task(status="error", completed_at=_now())
                    return

                if event_type == "done":
                    usage = data if isinstance(data, dict) else {}
                    await self._persist_usage(
                        model_used=str(usage.get("model_used") or self._model_used),
                        prompt_tokens=int(usage.get("prompt_tokens") or 0),
                        completion_tokens=int(usage.get("completion_tokens") or 0),
                    )

                await self._insert_event(event_type, _normalise(data))
                await self._touch_task()

                # Marca o stage 'agent' como done apenas quando o LLM responde
                # de facto (text/tool/action). Se nunca chegar resposta — caso
                # típico de done-vazio ou erro de provider — o passo "Agente
                # iniciado" fica explicitamente pending e o erro detalhado
                # aparece logo abaixo, sem o falso "tudo verde".
                if not agent_stage_marked and event_type in (
                    "text",
                    "tool_start",
                    "tool_result",
                    "action_required",
                ):
                    agent_stage_marked = True
                    await self._insert_event(
                        "status",
                        {
                            "message": "Agente respondeu",
                            "stage": "agent",
                            "mode": "initializing",
                            "state": "done",
                        },
                    )

                if event_type == "action_required":
                    await self._update_task(status="paused")
                    # Aguarda resposta — o stream interno já está pausado
                    # TaskDispatcher chama send_input() quando o utilizador responder
                    await self._wait_for_resume()
                    await self._update_task(status="running")

                elif event_type in ("done",):
                    await self._update_task(status="done", completed_at=_now())
                    return

                elif event_type in ("error", "timeout"):
                    await self._update_task(status="error", completed_at=_now())
                    return

        except asyncio.CancelledError:
            log.info("[TaskRunner %s] cancelled", self._task_id[:8])
            raise
        except Exception as exc:
            log.exception("[TaskRunner %s] unexpected error", self._task_id[:8])
            await self._insert_event("error", {"message": str(exc)})
            await self._update_task(status="error", completed_at=_now())

    async def _wait_for_resume(self) -> None:
        """Espera até a sessão deixar de estar em pending_action."""
        while self._session.pending_action is not None:
            await asyncio.sleep(0.5)

    # ── DB helpers ────────────────────────────────────────────────

    async def _insert_event(self, event_type: str, data: dict) -> None:
        if not self._pool:
            return
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO agent_events (task_id, event_type, data)
                    VALUES ($1::uuid, $2, $3::jsonb)
                    """,
                    self._task_id,
                    event_type,
                    _json(data),
                )
        except Exception as exc:
            log.error("[TaskRunner %s] insert_event failed: %s", self._task_id[:8], exc)

    async def _update_task(
        self,
        status: str,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
    ) -> None:
        if not self._pool:
            return
        try:
            async with self._pool.acquire() as conn:
                if started_at:
                    await conn.execute(
                        "UPDATE agent_tasks SET status=$1, started_at=$2, last_event_at=NOW() WHERE id=$3::uuid",
                        status,
                        started_at,
                        self._task_id,
                    )
                elif completed_at:
                    await conn.execute(
                        "UPDATE agent_tasks SET status=$1, completed_at=$2, last_event_at=NOW() WHERE id=$3::uuid",
                        status,
                        completed_at,
                        self._task_id,
                    )
                else:
                    await conn.execute(
                        "UPDATE agent_tasks SET status=$1, last_event_at=NOW() WHERE id=$2::uuid",
                        status,
                        self._task_id,
                    )
        except Exception as exc:
            log.error("[TaskRunner %s] update_task failed: %s", self._task_id[:8], exc)

    async def _touch_task(self) -> None:
        if not self._pool:
            return
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    "UPDATE agent_tasks SET last_event_at=NOW() WHERE id=$1::uuid",
                    self._task_id,
                )
        except Exception:
            pass

    async def _persist_usage(
        self,
        model_used: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        await persist_usage(
            self._pool, self._task_id, model_used, prompt_tokens, completion_tokens
        )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalise(data) -> dict:
    """Converte qualquer tipo de dado de evento para dict serializável."""
    if data is None:
        return {}
    if isinstance(data, dict):
        return data
    if isinstance(data, str):
        return {"message": data}
    # PendingAction ou outros dataclasses
    try:
        return {k: v for k, v in vars(data).items() if not k.startswith("_")}
    except TypeError:
        return {"value": str(data)}


def _json(data: dict) -> str:
    import json

    return json.dumps(data, ensure_ascii=False, default=str)
