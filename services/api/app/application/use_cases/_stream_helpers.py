"""Helpers de streaming para o use case StreamMessage."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.entities import Conversation
    from app.ports.repositories import MessageRepository, RepositoryRepository


async def compute_cost(messages: MessageRepository, usage: dict) -> float:
    """Calcula custo USD via lookup no catálogo ``ai_models``.

    Devolve ``0.0`` quando não há tokens, modelo ou pricing cadastrado.
    """
    model_used = usage.get("model_used") or ""
    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or 0)
    if not model_used or (prompt_tokens == 0 and completion_tokens == 0):
        return 0.0
    pricing = await messages.get_model_pricing(model_used)
    input_cost, output_cost = pricing or (0.0, 0.0)
    return round(
        (prompt_tokens * input_cost + completion_tokens * output_cost) / 1_000_000.0,
        6,
    )


async def ensure_repo_ids(
    repositories: RepositoryRepository | None,
    conversations: object,
    conv: Conversation,
) -> None:
    """Resolve ``repo_id`` em conv.repos a partir do slug, persiste se mudou."""
    if not repositories or not conv.repos:
        return
    changed = False
    for r in conv.repos:
        if r.get("repo_id"):
            continue
        slug = r.get("slug")
        if not slug:
            continue
        repo_entity = await repositories.get_by_slug(slug)
        if repo_entity:
            r["repo_id"] = str(repo_entity.id)
            if repo_entity.confluence_url:
                r["confluence_url"] = repo_entity.confluence_url
            changed = True
    if changed:
        await conversations.update(conv)  # type: ignore[attr-defined]


async def enrich_repos_for_pipeline(
    repositories: RepositoryRepository | None, repos: list[dict]
) -> list[dict]:
    """Adiciona ``clone_url`` autenticado e metadados opcionais a cada repo do pipeline."""
    if not repositories:
        return repos
    enriched: list[dict] = []
    for r in repos:
        next_repo = dict(r)
        repo_id_str = r.get("repo_id")
        if repo_id_str:
            try:
                repo_id = uuid.UUID(repo_id_str)
                auth_url = await repositories.get_authenticated_clone_url(repo_id)
                if auth_url:
                    next_repo["clone_url"] = auth_url
                confluence_url = await repositories.get_confluence_url(repo_id)
                if confluence_url:
                    next_repo["confluence_url"] = confluence_url
            except Exception:
                pass
        enriched.append(next_repo)
    return enriched


def build_pipeline_body(
    conv: Conversation,
    enriched_repos: list[dict],
    user_id: uuid.UUID,
    cursor: int | None,
    override_model: str | None,
    attachments_payload: list[dict] | None,
) -> dict:
    """Monta o dict que vai para o pipeline do agente."""
    body: dict = {
        "user_id": str(user_id),
        "conversation_id": str(conv.id),
        "user": {"id": str(user_id)},
        "cursor": cursor,
        "repos": enriched_repos,
        "session_root": conv.session_root or "",
        "sandbox_id": str(conv.sandbox_id) if conv.sandbox_id else "",
        "override_model": override_model,
    }
    # ``attachments_payload`` viaja como bytes brutos pelo pipeline → gRPC.
    # Não serializável para JSON, por isso fica fora de qualquer log.
    if attachments_payload:
        body["attachments_payload"] = attachments_payload
    return body


async def inject_diff_comments(conversation_id: uuid.UUID, content: str) -> str:
    """Prefixa o conteúdo com comentários de diff pendentes e marca-os como bundled."""
    try:
        from sqlalchemy import text

        from app.infrastructure.database import async_session_factory

        async with async_session_factory() as session:
            rows = await session.execute(
                text(
                    "SELECT id, file_path, line, content FROM diff_comments "
                    "WHERE conversation_id = :cid AND bundled_at IS NULL "
                    "ORDER BY file_path, line"
                ),
                {"cid": str(conversation_id)},
            )
            comments = rows.fetchall()
            if not comments:
                return content

            lines = [f"at `{row.file_path}:{row.line}`: {row.content}" for row in comments]
            ids = ", ".join(f"'{row.id}'" for row in comments)
            await session.execute(
                text(f"UPDATE diff_comments SET bundled_at = NOW() WHERE id IN ({ids})")
            )
            await session.commit()
            return "\n".join(lines) + "\n\n" + content
    except Exception:
        return content
