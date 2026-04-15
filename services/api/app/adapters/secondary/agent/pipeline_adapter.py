"""PipelineAdapter — wraps the CappyCloud Pipeline to satisfy AgentPort ABC.

This adapter decouples the HTTP/use-case layer from the concrete Pipeline class.
Routers and use cases depend only on AgentPort; they never import Pipeline directly.
"""

from __future__ import annotations

from collections.abc import Generator

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
        messages: list[dict],  # type: ignore[type-arg]
        body: dict,  # type: ignore[type-arg]
    ) -> Generator[str, None, None]:
        """Delegate streaming to the underlying Pipeline.pipe()."""
        return self._pipeline.pipe(user_message, model_id, messages, body)

    async def on_startup(self) -> None:
        """Initialise the Pipeline (connects to Docker, Redis, PostgreSQL)."""
        await self._pipeline.on_startup()

    async def on_shutdown(self) -> None:
        """Gracefully shut down the Pipeline and its background tasks."""
        await self._pipeline.on_shutdown()

    def get_env_status(self, user_id: str) -> dict:  # type: ignore[type-arg]
        """Delegate environment status query to the underlying Pipeline."""
        return self._pipeline.get_env_status(user_id)  # type: ignore[no-any-return]

    def wake_env(self, user_id: str) -> None:
        """Delegate environment wake to the underlying Pipeline."""
        self._pipeline.wake_env(user_id)
