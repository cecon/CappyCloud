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
    ) -> Generator[str, None, None]:
        """Stream SSE-formatted chunks from the agent.

        Each yielded string is a complete SSE line, e.g.::

            data: {"type": "text", "content": "Hello"}\\n\\n

        Args:
            user_message: The latest user input.
            model_id: Identifier for the model/pipeline variant.
            messages: Full conversation history as role/content dicts.
            body: Request metadata (user_id, conversation_id, env_slug, etc.).
        """

    @abstractmethod
    async def dispatch(
        self,
        prompt: str,
        env_slug: str,
        conversation_id: str | None = None,
        triggered_by: str = "system",
        trigger_payload: dict | None = None,
        base_branch: str = "",
    ) -> str | None:
        """Dispatch an agent task and return the task_id.

        Unlike pipe(), this is fire-and-forget: it creates the task in the DB
        and starts execution in the background. Returns task_id or None.

        Args:
            prompt: The instruction/question for the agent.
            env_slug: Target environment slug.
            conversation_id: Optional conversation to associate the task with.
            triggered_by: Source of the trigger (user/github/gitlab/routine/schedule).
            trigger_payload: Additional metadata about the trigger.
            base_branch: Git base branch override (empty = use repo default).
        """

    @abstractmethod
    async def on_startup(self) -> None:
        """Initialise resources (connections, background tasks)."""

    @abstractmethod
    async def on_shutdown(self) -> None:
        """Release resources gracefully."""

    @abstractmethod
    def get_env_status(self, env_slug: str) -> dict[str, object]:
        """Return the current status of a global environment container.

        Possible values for the ``status`` key:
        - ``none``     — no record or container
        - ``stopped``  — container exists but is stopped
        - ``starting`` — container is being created or restarted
        - ``running``  — container is running and gRPC is accessible

        Args:
            env_slug: Unique identifier (slug) of the repo environment.
        """

    @abstractmethod
    def wake_env(self, env_slug: str) -> None:
        """Trigger environment container creation/restart (fire-and-forget).

        Args:
            env_slug: Unique identifier (slug) of the repo environment.
        """

    @abstractmethod
    def destroy_env(self, env_slug: str) -> None:
        """Stop and remove the environment container for a slug (fire-and-forget).

        Args:
            env_slug: Unique identifier (slug) of the repo environment.
        """

    @abstractmethod
    def cancel_conversation(self, conversation_id: str) -> bool:
        """Cancel the active task for a conversation.

        Returns True if there was a running task to cancel.

        Args:
            conversation_id: UUID of the conversation whose task to cancel.
        """
