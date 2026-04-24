"""Conversation and messaging use cases — business logic for chat management."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator

from app.application.use_cases._stream_helpers import inject_diff_comments
from app.domain.entities import Conversation, Message
from app.ports.agent import AgentPort
from app.ports.repositories import (
    ConversationRepository,
    MessageRepository,
    RepositoryRepository,
)

_TITLE_MAX_LEN = 80
_DEFAULT_TITLE = "Nova conversa"


def _next_chunk(gen):
    try:
        return next(gen)
    except StopIteration:
        return None


# ── Conversation use cases ────────────────────────────────────


class ListConversations:
    def __init__(self, conversations: ConversationRepository) -> None:
        self._conversations = conversations

    async def execute(self, user_id: uuid.UUID) -> list[Conversation]:
        return await self._conversations.list_by_user(user_id)


class CreateConversation:
    """Create a new conversation, setting up multi-repo session metadata.

    Resolve cada ``slug`` em ``repos`` para o ``repo_id`` correspondente na
    tabela ``repositories`` e armazena ambos no JSONB de ``Conversation.repos``.
    Esse ``repo_id`` flui at\u00e9 ao pipeline e habilita filtros de skills por
    reposit\u00f3rio. Se o slug n\u00e3o existir em ``repositories``, o item segue sem
    ``repo_id`` (compatibilidade) e o pipeline cai no fallback lazy.
    """

    def __init__(
        self,
        conversations: ConversationRepository,
        repositories: RepositoryRepository | None = None,
    ) -> None:
        self._conversations = conversations
        self._repositories = repositories

    async def execute(
        self,
        user_id: uuid.UUID,
        title: str | None = None,
        sandbox_id: uuid.UUID | None = None,
        repos: list[dict] | None = None,
        agent_id: uuid.UUID | None = None,
    ) -> Conversation:
        conv_id = uuid.uuid4()
        short_id = conv_id.hex[:12]

        resolved_repos: list[dict] = []
        for r in repos or []:
            slug = r["slug"]
            alias = r.get("alias") or slug
            base = r.get("base_branch") or "main"
            branch_name = f"cappy/{slug}/{short_id}-{alias}"
            worktree_path = f"/repos/sessions/{short_id}/{alias}"
            repo_entity = await self._repositories.get_by_slug(slug) if self._repositories else None
            resolved_repos.append(
                {
                    "slug": slug,
                    "alias": alias,
                    "base_branch": base,
                    "branch_name": branch_name,
                    "worktree_path": worktree_path,
                    "repo_id": str(repo_entity.id) if repo_entity else None,
                }
            )

        session_root = f"/repos/sessions/{short_id}"

        conv = Conversation(
            id=conv_id,
            user_id=user_id,
            title=title or _DEFAULT_TITLE,
            sandbox_id=sandbox_id,
            agent_id=agent_id,
            repos=resolved_repos,
            session_root=session_root,
        )
        return await self._conversations.save(conv)


class ListMessages:
    def __init__(
        self,
        conversations: ConversationRepository,
        messages: MessageRepository,
    ) -> None:
        self._conversations = conversations
        self._messages = messages

    async def execute(self, conversation_id: uuid.UUID, user_id: uuid.UUID) -> list[Message]:
        conv = await self._conversations.get(conversation_id, user_id)
        if not conv:
            raise LookupError("Conversa não encontrada.")
        return await self._messages.list_by_conversation(conversation_id)


class StreamMessage:
    """Orchestrate sending a user message and streaming the agent response."""

    def __init__(
        self,
        conversations: ConversationRepository,
        messages: MessageRepository,
        agent: AgentPort,
        repositories: RepositoryRepository | None = None,
    ) -> None:
        self._conversations = conversations
        self._messages = messages
        self._agent = agent
        self._repositories = repositories

    async def execute(
        self,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        content: str,
        model_id: str = "cappycloud",
        cursor: int | None = None,
        override_model: str | None = None,
    ) -> AsyncGenerator[bytes]:
        conv = await self._conversations.get(conversation_id, user_id)
        if not conv:
            raise LookupError("Conversa não encontrada.")

        injected_prompt = await inject_diff_comments(conversation_id, content)

        await self._messages.save(
            Message(
                id=uuid.uuid4(),
                conversation_id=conv.id,
                role="user",
                content=content,
            )
        )

        if conv.title == _DEFAULT_TITLE:
            conv.title = content[:_TITLE_MAX_LEN] + ("…" if len(content) > _TITLE_MAX_LEN else "")
            await self._conversations.update(conv)

        history = await self._messages.list_by_conversation(conversation_id)
        messages_payload = [{"role": m.role, "content": m.content} for m in history]

        await self._ensure_repo_ids(conv)
        pipeline_body = await self._build_pipeline_body(
            conv, user_id, cursor, override_model
        )

        return self._stream_chunks(
            injected_prompt, model_id, messages_payload, pipeline_body, conversation_id
        )

    async def _ensure_repo_ids(self, conv: Conversation) -> None:
        """Backfill lazy: resolve slug \u2192 repo_id para conversas antigas.

        Persiste de volta na conversa para que mensagens seguintes n\u00e3o paguem
        o lookup de novo.
        """
        if not self._repositories or not conv.repos:
            return
        changed = False
        for r in conv.repos:
            if r.get("repo_id"):
                continue
            slug = r.get("slug")
            if not slug:
                continue
            repo_entity = await self._repositories.get_by_slug(slug)
            if repo_entity:
                r["repo_id"] = str(repo_entity.id)
                changed = True
        if changed:
            await self._conversations.update(conv)

    async def _enrich_repos_for_pipeline(self, repos: list[dict]) -> list[dict]:
        """Retorna nova lista com clone_url autenticada (token embutido).

        O token N\u00c3O \u00e9 persistido na conversa \u2014 \u00e9 injetado apenas no payload
        do pipeline para que session_start.sh consiga autenticar.
        """
        if not self._repositories:
            return repos
        enriched: list[dict] = []
        for r in repos:
            repo_id_str = r.get("repo_id")
            if repo_id_str:
                try:
                    auth_url = await self._repositories.get_authenticated_clone_url(
                        uuid.UUID(repo_id_str)
                    )
                    if auth_url:
                        enriched.append({**r, "clone_url": auth_url})
                        continue
                except Exception:
                    pass
            enriched.append(r)
        return enriched

    async def _build_pipeline_body(
        self,
        conv: Conversation,
        user_id: uuid.UUID,
        cursor: int | None,
        override_model: str | None = None,
    ) -> dict:
        repos_for_pipeline = await self._enrich_repos_for_pipeline(conv.repos)
        return {
            "user_id": str(user_id),
            "conversation_id": str(conv.id),
            "user": {"id": str(user_id)},
            "cursor": cursor,
            "repos": repos_for_pipeline,
            "session_root": conv.session_root or "",
            "sandbox_id": str(conv.sandbox_id) if conv.sandbox_id else "",
            "agent_id": str(conv.agent_id) if conv.agent_id else "",
            "override_model": override_model,
        }

    async def _stream_chunks(
        self,
        content: str,
        model_id: str,
        messages_payload: list[dict],
        pipeline_body: dict,
        conversation_id: uuid.UUID,
    ) -> AsyncGenerator[bytes]:
        accumulated_text: list[str] = []
        accumulated_error: list[str] = []
        gen = self._agent.pipe(content, model_id, messages_payload, pipeline_body)

        while True:
            chunk = await asyncio.to_thread(_next_chunk, gen)
            if chunk is None:
                break
            line = chunk.strip()
            if line.startswith("data: "):
                try:
                    evt = json.loads(line[6:])
                    if evt.get("type") == "text":
                        accumulated_text.append(evt.get("content", ""))
                    elif evt.get("type") == "error":
                        accumulated_error.append(evt.get("message", ""))
                except Exception:
                    pass
            yield chunk.encode("utf-8")

        assistant_text = "".join(accumulated_text).strip()
        if assistant_text:
            await self._messages.save(
                Message(
                    id=uuid.uuid4(),
                    conversation_id=conversation_id,
                    role="assistant",
                    content=assistant_text,
                )
            )
        elif accumulated_error:
            await self._messages.save(
                Message(
                    id=uuid.uuid4(),
                    conversation_id=conversation_id,
                    role="assistant",
                    content="**Erro:** " + " ".join(accumulated_error),
                )
            )
