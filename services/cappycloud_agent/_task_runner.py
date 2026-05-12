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
from datetime import datetime, timezone
from typing import Optional

import asyncpg

from ._grpc_helpers import PendingAction
from ._grpc_session import GrpcSession
from ._langfuse_client import get_langfuse

log = logging.getLogger(__name__)

# Tamanho máximo de campo enviado ao Langfuse (output de tool, texto, etc.).
_LF_FIELD_LIMIT = 16_000


class TaskRunner:
    """Wraps a GrpcSession e persiste todos os eventos no DB."""

    def __init__(
        self,
        task_id: str,
        session: GrpcSession,
        db_url: str,
        model_used: str = "",
        conversation_id: Optional[str] = None,
        initial_prompt: Optional[str] = None,
    ) -> None:
        self._task_id = task_id
        self._session = session
        self._db_url = db_url
        self._model_used = model_used
        self._conversation_id = conversation_id
        self._initial_prompt = initial_prompt
        self._pool: Optional[asyncpg.Pool] = None
        self._task: Optional[asyncio.Task] = None
        # Telemetria Langfuse (None se não configurada).
        self._lf_trace = None
        self._lf_text_buffer: list[str] = []

    # ── Public API ────────────────────────────────────────────────

    async def start(self) -> None:
        """Inicia a task de execução em background."""
        self._pool = await asyncpg.create_pool(self._db_url, min_size=1, max_size=3)
        self._lf_start_trace()
        self._task = asyncio.create_task(
            self._run(), name=f"runner-{self._task_id[:8]}"
        )

    async def send_input(self, reply: str) -> None:
        """Repassa a resposta do utilizador ao stream gRPC pausado."""
        await self._session.send_input(reply)

    async def send_message(self, message: str) -> None:
        """Envia uma nova mensagem numa sessão já activa."""
        await self._session.send_message(message)

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
        """Loop principal: drena o stream gRPC e persiste eventos no DB."""
        await self._update_task(status="running", started_at=_now())
        try:
            while True:
                try:
                    event_type, data = await asyncio.wait_for(
                        self._session._out_queue.get(), timeout=300.0
                    )
                except asyncio.TimeoutError:
                    await self._insert_event(
                        "timeout", {"message": "Stream silencioso por 5 min."}
                    )
                    await self._update_task(status="error", completed_at=_now())
                    return

                payload = _normalise(data)
                await self._insert_event(event_type, payload)
                self._lf_emit_event(event_type, payload)
                await self._touch_task()

                if event_type == "action_required":
                    await self._update_task(status="paused")
                    # Aguarda resposta — o stream interno já está pausado
                    # TaskDispatcher chama send_input() quando o utilizador responder
                    await self._wait_for_resume()
                    await self._update_task(status="running")

                elif event_type in ("done",):
                    usage = data if isinstance(data, dict) else {}
                    model_used = str(usage.get("model_used") or self._model_used)
                    prompt_tokens = int(usage.get("prompt_tokens") or 0)
                    completion_tokens = int(usage.get("completion_tokens") or 0)
                    await self._persist_usage(
                        model_used=model_used,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                    )
                    await self._update_task(status="done", completed_at=_now())
                    self._lf_finalize(
                        status="done",
                        model=model_used,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                    )
                    return

                elif event_type in ("error", "timeout"):
                    await self._update_task(status="error", completed_at=_now())
                    self._lf_finalize(status=event_type, error=payload.get("message"))
                    return

        except asyncio.CancelledError:
            log.info("[TaskRunner %s] cancelled", self._task_id[:8])
            self._lf_finalize(status="cancelled")
            raise
        except Exception as exc:
            log.exception("[TaskRunner %s] unexpected error", self._task_id[:8])
            await self._insert_event("error", {"message": str(exc)})
            await self._update_task(status="error", completed_at=_now())
            self._lf_finalize(status="error", error=str(exc))

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
        """Calcula custo via lookup em ``ai_models`` e grava em ``agent_tasks``.

        Quando o ``model_used`` não estiver no catálogo, gravamos os tokens
        e ``cost_usd=0`` (e logamos um aviso para que o admin sincronize via
        ``POST /api/ai-models/sync-from-openrouter``).
        """
        if not self._pool:
            return
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT input_cost_per_1m_usd, output_cost_per_1m_usd
                    FROM ai_models
                    WHERE model_id = $1 AND active = TRUE
                    LIMIT 1
                    """,
                    model_used,
                )
                input_cost = float(row["input_cost_per_1m_usd"] or 0) if row else 0.0
                output_cost = float(row["output_cost_per_1m_usd"] or 0) if row else 0.0
                cost_usd = round(
                    (prompt_tokens * input_cost + completion_tokens * output_cost)
                    / 1_000_000.0,
                    6,
                )
                if not row:
                    log.warning(
                        "[TaskRunner %s] modelo '%s' não consta de ai_models — "
                        "custo=0. Faça sync OpenRouter.",
                        self._task_id[:8],
                        model_used,
                    )
                await conn.execute(
                    """
                    UPDATE agent_tasks
                    SET model_used=$1,
                        prompt_tokens=$2,
                        completion_tokens=$3,
                        cost_usd=$4,
                        last_event_at=NOW()
                    WHERE id=$5::uuid
                    """,
                    model_used,
                    prompt_tokens,
                    completion_tokens,
                    cost_usd,
                    self._task_id,
                )
        except Exception as exc:
            log.error(
                "[TaskRunner %s] persist_usage failed: %s",
                self._task_id[:8],
                exc,
            )

    # ── Langfuse helpers ──────────────────────────────────────────

    def _lf_start_trace(self) -> None:
        """Abre uma trace Langfuse para esta task. Silencioso se desactivado."""
        lf = get_langfuse()
        if lf is None:
            return
        try:
            self._lf_trace = lf.trace(
                id=self._task_id,
                name="agent_task",
                session_id=self._conversation_id,
                input=_truncate(self._initial_prompt) if self._initial_prompt else None,
                metadata={
                    "model": self._model_used,
                    "conversation_id": self._conversation_id,
                },
                tags=["agent", "cappycloud"],
            )
        except Exception as exc:  # noqa: BLE001
            log.debug("[TaskRunner %s] langfuse trace start failed: %s", self._task_id[:8], exc)
            self._lf_trace = None

    def _lf_emit_event(self, event_type: str, data: dict) -> None:
        """Mapeia um evento gRPC para uma observação Langfuse."""
        if self._lf_trace is None:
            return
        try:
            if event_type == "text":
                # Acumula tokens de texto para emitir como output final.
                content = data.get("content", "")
                if content:
                    self._lf_text_buffer.append(content)
                return

            if event_type == "tool_start":
                self._lf_trace.span(
                    id=f"{self._task_id}:{data.get('id', 'noid')}",
                    name=f"tool:{data.get('name', 'unknown')}",
                    input=_truncate(data.get("input")),
                )
                return

            if event_type == "tool_result":
                output = data.get("output")
                if isinstance(output, (bytes, bytearray)):
                    output = output.decode("utf-8", errors="replace")
                self._lf_trace.span(
                    id=f"{self._task_id}:{data.get('id', 'noid')}:result",
                    name=f"tool:{data.get('name', 'unknown')}:result",
                    output=_truncate(output),
                    level="ERROR" if data.get("is_error") else "DEFAULT",
                )
                return

            if event_type == "action_required":
                self._lf_trace.event(
                    name="action_required",
                    input={"question": data.get("question"), "type": data.get("action_type")},
                )
                return

            if event_type == "status":
                self._lf_trace.event(name=f"status:{data.get('stage', '')}", input=data)
                return

            if event_type == "error":
                self._lf_trace.event(
                    name="error",
                    input=data,
                    level="ERROR",
                )
        except Exception as exc:  # noqa: BLE001
            log.debug("[TaskRunner %s] langfuse emit failed: %s", self._task_id[:8], exc)

    def _lf_finalize(
        self,
        status: str,
        model: str = "",
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        error: Optional[str] = None,
    ) -> None:
        """Fecha a trace, anexando uso de tokens e output acumulado."""
        if self._lf_trace is None:
            return
        try:
            full_text = "".join(self._lf_text_buffer)
            self._lf_trace.update(
                output=_truncate(full_text) if full_text else None,
                metadata={
                    "status": status,
                    "model": model or self._model_used,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "error": error,
                },
            )
            if model and (prompt_tokens or completion_tokens):
                # Generation dedicada para o LLM call agregado (token cost view).
                self._lf_trace.generation(
                    name="llm_call",
                    model=model,
                    input=_truncate(self._initial_prompt) if self._initial_prompt else None,
                    output=_truncate(full_text) if full_text else None,
                    usage={
                        "input": prompt_tokens,
                        "output": completion_tokens,
                        "unit": "TOKENS",
                    },
                )
        except Exception as exc:  # noqa: BLE001
            log.debug("[TaskRunner %s] langfuse finalize failed: %s", self._task_id[:8], exc)
        finally:
            self._lf_trace = None


def _truncate(value):
    """Trunca strings/bytes ao limite do Langfuse para evitar payloads gigantes."""
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8", errors="replace")
    if isinstance(value, str) and len(value) > _LF_FIELD_LIMIT:
        return value[:_LF_FIELD_LIMIT] + f"... [truncated {len(value) - _LF_FIELD_LIMIT}b]"
    return value


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
