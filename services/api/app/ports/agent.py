"""Agent port — ABC for the AI agent pipeline.

The Pipeline class (cappycloud_agent) implements this interface via PipelineAdapter.
Test doubles (FakeAgent) also implement it, proving LSP substitutability.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Generator


class AgentPort(ABC):
    """Outbound port for the AI agent pipeline."""

    @abstractmethod
    def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: list[dict],
        body: dict,
    ) -> Generator[str]:
        """Stream SSE-formatted chunks from the agent.

        Each yielded string is a complete SSE line, e.g.::

            data: {"type": "text", "content": "Hello"}\\n\\n

        Args:
            user_message: The latest user input.
            model_id: Identifier for the model/pipeline variant.
            messages: Full conversation history as role/content dicts.
            body: Request metadata (user_id, conversation_id, etc.).
        """

    @abstractmethod
    async def dispatch(
        self,
        prompt: str,
        conversation_id: str | None = None,
        triggered_by: str = "system",
        trigger_payload: dict | None = None,
    ) -> str | None:
        """Dispatch an agent task and return the task_id.

        Unlike pipe(), this is fire-and-forget: it creates the task in the DB
        and starts execution in the background. Returns task_id or None.

        Args:
            prompt: The instruction/question for the agent.
            conversation_id: Optional conversation to associate the task with.
            triggered_by: Source of the trigger (user/github/gitlab/routine/schedule).
            trigger_payload: Additional metadata about the trigger.
        """

    @abstractmethod
    async def on_startup(self) -> None:
        """Initialise resources (connections, background tasks)."""

    @abstractmethod
    async def on_shutdown(self) -> None:
        """Release resources gracefully."""

    @abstractmethod
    def cancel_conversation(self, conversation_id: str) -> bool:
        """Cancel the active task for a conversation.

        Returns True if there was a running task to cancel.

        Args:
            conversation_id: UUID of the conversation whose task to cancel.
        """
