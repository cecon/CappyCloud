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


class ListConversations:
    def __init__(self, conversations: ConversationRepository) -> None:
        self._conversations = conversations

    async def execute(self, user_id: uuid.UUID) -> list[Conversation]:
        return await self._conversations.list_by_user(user_id)


class CreateConversation:
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
            repos=resolved_repos,
            session_root=session_root,
        )
        return await self._conversations.save(conv)


class UpdateConversationRepos:
    """Atualiza a lista de repositórios de uma conversa existente."""

    def __init__(
        self,
        conversations: ConversationRepository,
        repositories: RepositoryRepository | None = None,
    ) -> None:
        self._conversations = conversations
        self._repositories = repositories

    async def execute(
        self,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        repos: list[dict],
    ) -> Conversation:
        conv = await self._conversations.get(conversation_id, user_id)
        if not conv:
            raise LookupError("Conversa não encontrada.")

        short_id = conv.id.hex[:12]

        resolved_repos: list[dict] = []
        for r in repos:
            slug = r["slug"]
            alias = r.get("alias") or slug
            base = r.get("base_branch") or "main"
            branch_name = f"cappy/{slug}/{short_id}-{alias}"
            worktree_path = f"/repos/sessions/{short_id}/{alias}"
            repo_entity = (
                await self._repositories.get_by_slug(slug) if self._repositories else None
            )
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

        conv.repos = resolved_repos
        return await self._conversations.update(conv)


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
        pipeline_body = await self._build_pipeline_body(conv, user_id, cursor, override_model)

        return self._stream_chunks(
            injected_prompt, model_id, messages_payload, pipeline_body, conversation_id
        )

    async def _ensure_repo_ids(self, conv: Conversation) -> None:
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
        usage: dict = {}
        gen = self._agent.pipe(content, model_id, messages_payload, pipeline_body)

        while True:
            chunk = await asyncio.to_thread(_next_chunk, gen)
            if chunk is None:
                break
            line = chunk.strip()
            if line.startswith("data: "):
                try:
                    evt = json.loads(line[6:])
                    evt_type = evt.get("type")
                    if evt_type == "text":
                        accumulated_text.append(evt.get("content", ""))
                    elif evt_type == "error":
                        accumulated_error.append(evt.get("message", ""))
                    elif evt_type == "done":
                        # O TaskRunner enriquece o evento done com tokens/modelo
                        # para que possamos persistir o uso na mensagem assistant.
                        usage = {
                            "model_used": evt.get("model_used") or "",
                            "prompt_tokens": int(evt.get("prompt_tokens") or 0),
                            "completion_tokens": int(evt.get("completion_tokens") or 0),
                        }
                except Exception:
                    pass
            yield chunk.encode("utf-8")

        assistant_text = "".join(accumulated_text).strip()
        cost_usd = await self._compute_cost(usage)
        if assistant_text:
            await self._messages.save(
                Message(
                    id=uuid.uuid4(),
                    conversation_id=conversation_id,
                    role="assistant",
                    content=assistant_text,
                    model_used=usage.get("model_used") or None,
                    prompt_tokens=int(usage.get("prompt_tokens") or 0),
                    completion_tokens=int(usage.get("completion_tokens") or 0),
                    cost_usd=cost_usd,
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

    async def _compute_cost(self, usage: dict) -> float:
        """Calcula custo em USD via lookup no catálogo ``ai_models``.

        Devolve ``0.0`` quando não há tokens, modelo ou pricing cadastrado.
        """
        model_used = usage.get("model_used") or ""
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        if not model_used or (prompt_tokens == 0 and completion_tokens == 0):
            return 0.0
        pricing = await self._messages.get_model_pricing(model_used)
        input_cost, output_cost = pricing or (0.0, 0.0)
        return round(
            (prompt_tokens * input_cost + completion_tokens * output_cost) / 1_000_000.0,
            6,
        )
