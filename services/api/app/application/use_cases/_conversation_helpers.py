"""Helper functions for conversation use cases."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.ports.repositories import RepositoryRepository


async def resolve_repos(
    repos: list[dict], short_id: str, repositories: RepositoryRepository | None
) -> list[dict]:
    resolved = []
    for r in repos:
        slug = r["slug"]
        alias = r.get("alias") or r["slug"]
        base = r.get("base_branch") or "main"
        repo_entity = await repositories.get_by_slug(slug) if repositories else None
        resolved.append(
            {
                "slug": slug,
                "alias": alias,
                "base_branch": base,
                "branch_name": f"cappy/{slug}/{short_id}-{alias}",
                "worktree_path": f"/repos/sessions/{short_id}/{alias}",
                "repo_id": str(repo_entity.id) if repo_entity else None,
            }
        )
    return resolved


def next_chunk(gen):
    try:
        return next(gen)
    except StopIteration:
        return None


async def compute_cost(usage: dict, messages_repo) -> float:
    model_used = usage.get("model_used") or ""
    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or 0)
    if not model_used or (prompt_tokens == 0 and completion_tokens == 0):
        return 0.0
    pricing = await messages_repo.get_model_pricing(model_used)
    input_cost, output_cost = pricing or (0.0, 0.0)
    return round((prompt_tokens * input_cost + completion_tokens * output_cost) / 1_000_000.0, 6)
