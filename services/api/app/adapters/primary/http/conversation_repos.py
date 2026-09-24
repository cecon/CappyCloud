"""Repositórios de uma conversa, como o diff, os arquivos e o PR os enxergam.

Conversa legada (um repositório, sem workspace): caminhos relativos ao worktree,
como sempre foram. Conversa de workspace ou com vários repositórios: cada
caminho começa pelo alias do repositório (``backend/src/app.py``).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.orm_models_platform import Repository

_CONVERSATION_REPOS_SQL = """
SELECT c.repos, c.session_root, c.workspace_id, cs.repos AS session_repos
FROM conversations c
LEFT JOIN cappy_sessions cs ON cs.chat_id = c.id::text
WHERE c.id = :cid AND c.user_id = :uid
"""


@dataclass(frozen=True)
class ConversationRepo:
    alias: str
    slug: str
    worktree_path: str
    base_branch: str
    read_only: bool = False
    clone_url: str = ""
    provider_id: uuid.UUID | None = None


@dataclass(frozen=True)
class ConversationRepos:
    repos: list[ConversationRepo]
    # True: caminhos da UI prefixados pelo alias do repositório.
    prefixed: bool

    @property
    def editable(self) -> list[ConversationRepo]:
        """Repositórios com worktree próprio (entram no diff e no PR)."""
        return [repo for repo in self.repos if not repo.read_only]

    def to_ui_path(self, repo: ConversationRepo, rel_path: str) -> str:
        if not self.prefixed or not rel_path:
            return rel_path
        return f"{repo.alias}/{rel_path}"

    def from_ui_path(self, ui_path: str) -> tuple[ConversationRepo, str]:
        """Repositório e caminho relativo a partir do caminho mostrado na UI."""
        if not self.prefixed:
            return self.repos[0], ui_path
        alias, _, rel = ui_path.partition("/")
        for repo in self.repos:
            if repo.alias == alias and rel:
                return repo, rel
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Arquivo fora dos repositórios da conversa: {ui_path}",
        )


def _json_list(raw: Any) -> list[dict]:
    """JSONB pode vir decodificado ou como texto (registros antigos)."""
    value = raw
    for _ in range(2):
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except ValueError:
                return []
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _merge(conv_repos: list[dict], session_repos: list[dict]) -> list[dict]:
    """Dados da conversa + caminhos/branches que a sessão do agente gravou."""
    by_alias = {str(r.get("alias") or r.get("slug") or ""): r for r in session_repos}
    merged = []
    for repo in conv_repos or session_repos:
        alias = str(repo.get("alias") or repo.get("slug") or "")
        merged.append({**repo, **{k: v for k, v in by_alias.get(alias, {}).items() if v}})
    return merged


async def load_conversation_repos(
    db: AsyncSession, conversation_id: uuid.UUID, user_id: uuid.UUID | str
) -> ConversationRepos:
    """Carrega os repositórios da conversa do utilizador ou lança 404."""
    row = (
        await db.execute(
            text(_CONVERSATION_REPOS_SQL), {"cid": str(conversation_id), "uid": str(user_id)}
        )
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada")
    session_root = str(row[1] or f"/repos/sessions/{conversation_id.hex[:12]}").rstrip("/")
    raw = _merge(_json_list(row[0]), _json_list(row[3]))

    slugs = [str(r.get("slug") or "") for r in raw if r.get("slug")]
    catalog = {}
    if slugs:
        found = await db.execute(select(Repository).where(Repository.slug.in_(slugs)))
        catalog = {repo.slug: repo for repo in found.scalars()}

    repos: list[ConversationRepo] = []
    for item in raw:
        slug = str(item.get("slug") or "")
        alias = str(item.get("alias") or slug)
        if not alias:
            continue
        entry = catalog.get(slug)
        repos.append(
            ConversationRepo(
                alias=alias,
                slug=slug,
                worktree_path=str(item.get("worktree_path") or f"{session_root}/{alias}"),
                base_branch=str(item.get("base_branch") or "main"),
                read_only=bool(item.get("read_only")),
                clone_url=entry.clone_url if entry else "",
                provider_id=entry.provider_id if entry else None,
            )
        )
    if not repos:
        # Conversa sem repositório: a própria pasta da sessão.
        repos = [
            ConversationRepo(alias="", slug="", worktree_path=session_root, base_branch="main")
        ]
    prefixed = row[2] is not None or len(repos) > 1
    return ConversationRepos(repos=repos, prefixed=prefixed)
