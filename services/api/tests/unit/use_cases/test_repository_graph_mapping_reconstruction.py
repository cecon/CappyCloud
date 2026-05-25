from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from app.adapters.secondary.sandbox_repo_graph_provider import SandboxRepoGraphError
from app.application.use_cases.repository_graph_mapping import translate_sandbox_graph
from app.application.use_cases.repository_graph_materialization import resolve_repo_graph_commit_sha
from app.application.use_cases.repository_graph_reconstruction import reconstruct_graph_from_rows

from tests.unit.use_cases.test_repository_graph_mapping import _sample_graph


def test_translate_sandbox_graph_accepts_explicit_persisted_edge_ids() -> None:
    repo_id = uuid.uuid4()
    source_id = f"repo:{repo_id}@abc:file:EmpresaBO.cs#M"
    target_id = f"repo:{repo_id}@abc:doc:doc#table:dbo.Empresa"
    graph = _sample_graph()
    graph["semantic_nodes"] = []
    graph["semantic_edges"] = [
        {
            "id": "llm_gap:edge",
            "source": source_id,
            "target": target_id,
            "type": "resolves_to",
            "source_extractor": "llm_gap",
            "extractor_version": "0.1.0",
            "evidence": {"file": "EmpresaBO.cs", "line_start": 10, "snippet": "Empresa"},
            "attrs": {"original_edge_key": "abc"},
        }
    ]

    rows = translate_sandbox_graph(repo_id=repo_id, commit_sha="abc", graph=graph)
    edge = next(row for row in rows.edges if row.source_extractor == "llm_gap")

    assert edge.source_id == source_id
    assert edge.target_id == target_id
    assert edge.target_external is None
    assert edge.evidence["attrs"]["original_edge_key"] == "abc"


def test_reconstruct_graph_preserves_sandbox_shape() -> None:
    repo_id = uuid.uuid4()
    graph = _sample_graph()
    rows = translate_sandbox_graph(repo_id=repo_id, commit_sha="abc", graph=graph)

    reconstructed = reconstruct_graph_from_rows(
        repo_slug="demo",
        repo_path="/repos/demo",
        nodes=[SimpleNamespace(**row.__dict__) for row in rows.nodes],
        edges=[SimpleNamespace(**row.__dict__) for row in rows.edges],
    )

    assert reconstructed == {key: graph[key] for key in reconstructed}


class _CommitProvider:
    def __init__(self) -> None:
        self.refs: list[str] = []

    async def fetch_commit_sha(self, **kwargs) -> str:  # type: ignore[no-untyped-def]
        ref = str(kwargs["ref"])
        self.refs.append(ref)
        if ref == "Master":
            raise SandboxRepoGraphError("ref inválido", status_code=404)
        return "abc123head"


@pytest.mark.asyncio
async def test_resolve_repo_graph_commit_sha_falls_back_to_head() -> None:
    provider = _CommitProvider()
    repo = SimpleNamespace(default_branch="Master", slug="repo-demo")
    sandbox = SimpleNamespace(host="sandbox", session_port=8080)

    commit = await resolve_repo_graph_commit_sha(
        provider=provider,  # type: ignore[arg-type]
        repo=repo,  # type: ignore[arg-type]
        sandbox=sandbox,  # type: ignore[arg-type]
    )

    assert commit == "abc123head"
    assert provider.refs == ["Master", "HEAD"]
