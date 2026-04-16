"""PipelineAdapter — wraps the CappyCloud Pipeline to satisfy AgentPort ABC.

This adapter decouples the HTTP/use-case layer from the concrete Pipeline class.
Routers and use cases depend only on AgentPort; they never import Pipeline directly.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import cast

from app.ports.agent import AgentPort

# Pipeline is imported lazily (at runtime) to avoid import-time side effects
# (e.g. environment variable reads, asyncio checks) during test collection.


class PipelineAdapter(AgentPort):
    """Adapts cappycloud_agent.Pipeline to the AgentPort interface."""

    def __init__(self) -> None:
        from cappycloud_agent import Pipeline

        self._pipeline = Pipeline()

    def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: list[dict],
        body: dict,
    ) -> Generator[str, None, None]:
        """Delegate streaming to the underlying Pipeline.pipe()."""
        result = self._pipeline.pipe(user_message, model_id, messages, body)
        return cast(Generator[str, None, None], result)

    async def dispatch(
        self,
        prompt: str,
        env_slug: str = "default",
        conversation_id: str | None = None,
        triggered_by: str = "system",
        trigger_payload: dict | None = None,
        base_branch: str = "",
    ) -> str | None:
        """Dispatch a task via the TaskDispatcher and return task_id."""
        dispatcher = self._pipeline._dispatcher
        if dispatcher is None:
            return None
        result = await dispatcher.dispatch(
            prompt=prompt,
            conversation_id=conversation_id,
            triggered_by=triggered_by,
            trigger_payload=trigger_payload or {},
            base_branch=base_branch,
        )
        return result if isinstance(result, str) else None

    async def on_startup(self) -> None:
        """Initialise the Pipeline (connects to Docker, Redis, PostgreSQL)."""
        await self._pipeline.on_startup()

    async def on_shutdown(self) -> None:
        """Gracefully shut down the Pipeline and its background tasks."""
        await self._pipeline.on_shutdown()

    def cancel_conversation(self, conversation_id: str) -> bool:
        """Delegate conversation cancel to the underlying Pipeline."""
        result = self._pipeline.cancel_conversation(conversation_id)
        return bool(result)
