"""Repository MCP tool gateway backed by sandbox HTTP sidecar and SQL search."""

from __future__ import annotations

import uuid
from typing import Any
from urllib.parse import quote

import httpx
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.secondary.sandbox_repo_graph_provider import (
    SandboxRepoGraphError,
    SandboxRepositoryGraphProvider,
)
from app.application.use_cases.repository_graph_materialization import (
    enqueue_graph_materialization,
    load_materialized_repo_graph,
    resolve_repo_graph_commit_sha,
)
from app.domain.entities import UserMcpServer
from app.infrastructure.embeddings import embed_text
from app.infrastructure.orm_models import Repository, Sandbox, Skill
from app.ports.repository_mcp import RepositoryMcpToolGateway

_SKILL_SUMMARY_LIMIT = 300
_DOCUMENT_SUMMARY_LIMIT = 2000


class SQLAlchemyRepositoryMcpToolGateway(RepositoryMcpToolGateway):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def call_tool(
        self,
        server: UserMcpServer,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        repo, sandbox = await self._load_scope(server.repository_id)
        if tool_name == "repository_list_files":
            return await self._sandbox_get(sandbox, f"/repos/{quote(repo.slug, safe='')}/files")
        if tool_name == "repository_read_file":
            return await self._read_file(repo, sandbox, arguments)
        if tool_name == "repository_search":
            return await self._search(repo, sandbox, arguments, regex=False)
        if tool_name == "repository_grep":
            return await self._search(repo, sandbox, arguments, regex=True)
        if tool_name == "repository_graph":
            return await self._graph(repo, sandbox, arguments)
        if tool_name == "skills_search":
            return await self._skills_search(server.repository_id, arguments)
        if tool_name == "confluence_search":
            return await self._confluence_search(repo, sandbox, arguments)
        if tool_name == "confluence_get_page":
            return await self._confluence_page(repo, sandbox, arguments)
        raise ValueError(f"Tool desconhecida: {tool_name}")

    async def _load_scope(self, repository_id: uuid.UUID) -> tuple[Repository, Sandbox]:
        repo = await self._session.get(Repository, repository_id)
        if repo is None or not repo.active:
            raise ValueError("Repositório não encontrado ou inativo.")
        if repo.sandbox_id is None:
            raise ValueError("Repositório sem sandbox associado.")
        sandbox = await self._session.get(Sandbox, repo.sandbox_id)
        if sandbox is None or sandbox.status != "active":
            raise ValueError("Sandbox do repositório indisponível.")
        return repo, sandbox

    async def _sandbox_get(
        self,
        sandbox: Sandbox,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"http://{sandbox.host}:{sandbox.session_port}{path}"
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            response = await client.get(url, params=params)
        data: object = response.json() if "json" in response.headers.get("content-type", "") else {}
        if response.status_code < 400 and isinstance(data, dict):
            return data
        if isinstance(data, dict):
            detail = data.get("detail") or data.get("error")
        else:
            detail = response.text
        raise RuntimeError(str(detail or f"Sandbox HTTP {response.status_code}"))

    async def _read_file(
        self,
        repo: Repository,
        sandbox: Sandbox,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        rel_path = str(arguments.get("path") or "").strip()
        if not rel_path:
            raise ValueError("path é obrigatório.")
        return await self._sandbox_get(
            sandbox,
            f"/repos/{quote(repo.slug, safe='')}/file",
            {"path": rel_path},
        )

    async def _search(
        self,
        repo: Repository,
        sandbox: Sandbox,
        arguments: dict[str, Any],
        *,
        regex: bool,
    ) -> dict[str, Any]:
        key = "pattern" if regex else "query"
        query = str(arguments.get(key) or arguments.get("query") or "").strip()
        if not query:
            raise ValueError(f"{key} é obrigatório.")
        limit = max(1, min(int(arguments.get("limit") or 20), 50))
        return await self._sandbox_get(
            sandbox,
            f"/repos/{quote(repo.slug, safe='')}/search",
            {"q": query, "limit": limit, "regex": str(regex).lower()},
        )

    async def _graph(
        self,
        repo: Repository,
        sandbox: Sandbox,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        max_files = max(50, min(int(arguments.get("max_files") or 1200), 5000))
        materialized = _truthy(arguments.get("materialized"))
        if materialized:
            commit_sha = str(arguments.get("commit_sha") or "").strip()
            provider = SandboxRepositoryGraphProvider()
            if not commit_sha:
                try:
                    commit_sha = await resolve_repo_graph_commit_sha(
                        provider=provider,
                        repo=repo,
                        sandbox=sandbox,
                    )
                except SandboxRepoGraphError as exc:
                    raise RuntimeError(f"Falha ao resolver commit do graph: {exc}") from exc
            graph = await load_materialized_repo_graph(
                self._session,
                repo=repo,
                commit_sha=commit_sha,
            )
            if graph is not None:
                return graph
            job_id = await enqueue_graph_materialization(
                self._session,
                repo=repo,
                commit_sha=commit_sha,
                max_files=max_files,
            )
            await self._session.commit()
            return {"job_id": str(job_id), "status": "materializing", "commit_sha": commit_sha}
        return await self._sandbox_get(
            sandbox,
            f"/repos/{quote(repo.slug, safe='')}/graph",
            {"max_files": max_files},
        )

    async def _skills_search(self, repo_id: uuid.UUID, arguments: dict[str, Any]) -> dict[str, Any]:
        query = str(arguments.get("query") or "").strip()
        if not query:
            raise ValueError("query é obrigatório.")
        limit = max(1, min(int(arguments.get("limit") or 5), 10))
        rows = await self._search_skill_rows(repo_id, query, limit)
        return {"query": query, "count": len(rows), "results": rows}

    async def _search_skill_rows(
        self,
        repo_id: uuid.UUID,
        query: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        query_emb = await embed_text(query)
        filters = [Skill.active.is_(True), Skill.repository_id == repo_id]
        if query_emb is not None:
            distance = Skill.embedding.cosine_distance(query_emb)
            rows = await self._session.execute(
                select(Skill, distance.label("dist"))
                .where(*filters, Skill.embedding.is_not(None))
                .order_by("dist")
                .limit(limit)
            )
            out = [
                self._skill_payload(skill, max(0.0, 1.0 - float(dist)))
                for skill, dist in rows.all()
            ]
            if out:
                return out
        pattern = f"%{query}%"
        rows = await self._session.execute(
            select(Skill)
            .where(
                *filters,
                or_(
                    Skill.title.ilike(pattern),
                    Skill.summary.ilike(pattern),
                    Skill.content.ilike(pattern),
                ),
            )
            .order_by(Skill.title)
            .limit(limit)
        )
        return [self._skill_payload(skill, 0.5) for skill in rows.scalars()]

    @staticmethod
    def _skill_payload(skill: Skill, score: float) -> dict[str, Any]:
        return {
            "id": str(skill.id),
            "slug": skill.slug,
            "title": skill.title,
            "summary": _skill_summary(skill),
            "score": score,
            "source_url": skill.source_url,
        }

    async def _confluence_search(
        self,
        repo: Repository,
        sandbox: Sandbox,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        if not repo.confluence_url:
            raise ValueError("Repositório sem Confluence configurado.")
        query = str(arguments.get("query") or "").strip()
        if not query:
            raise ValueError("query é obrigatório.")
        labels = arguments.get("labels") or repo.confluence_labels or []
        return await self._sandbox_get(
            sandbox,
            "/confluence/search",
            {
                "base_url": repo.confluence_url,
                "q": query,
                "space": str(arguments.get("space") or repo.confluence_space or "all"),
                "labels": ",".join(str(label) for label in labels),
                "limit": max(1, min(int(arguments.get("limit") or 5), 10)),
            },
        )

    async def _confluence_page(
        self,
        repo: Repository,
        sandbox: Sandbox,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        if not repo.confluence_url:
            raise ValueError("Repositório sem Confluence configurado.")
        page_id = str(arguments.get("page_id") or "").strip()
        url = str(arguments.get("url") or "").strip()
        if not page_id and not url:
            raise ValueError("Informe page_id ou url.")
        return await self._sandbox_get(
            sandbox,
            "/confluence/page",
            {"base_url": repo.confluence_url, "id": page_id, "url": url},
        )


def _skill_summary(skill: Skill) -> str:
    if skill.document_id is not None:
        return (skill.content or skill.summary or "")[:_DOCUMENT_SUMMARY_LIMIT]
    return (skill.summary or skill.content or "")[:_SKILL_SUMMARY_LIMIT]


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "sim"}
