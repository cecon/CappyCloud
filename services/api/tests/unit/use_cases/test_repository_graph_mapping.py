from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from app.adapters.secondary.sandbox_repo_graph_provider import SandboxRepoGraphError
from app.application.use_cases.repository_graph_mapping import (
    stable_graph_node_id,
    translate_sandbox_graph,
)
from app.application.use_cases.repository_graph_materialization import resolve_repo_graph_commit_sha
from app.application.use_cases.repository_graph_reconstruction import reconstruct_graph_from_rows


def _sample_graph() -> dict:
    return {
        "slug": "demo",
        "repo_path": "/repos/demo",
        "generated_at": "2026-05-23T00:00:00Z",
        "extractor_version": "0.1.0",
        "stats": {
            "files": 1,
            "code_files": 1,
            "modules": 1,
            "links": 1,
            "isolated": 0,
            "symbols": 1,
            "entrypoints": 1,
            "unreferenced_files": 0,
            "ui_actions": 0,
            "flows": 1,
        },
        "nodes": [
            {"id": "repo:demo", "label": "demo", "type": "repo", "path": "/repos/demo"},
            {"id": "module:src", "label": "src", "type": "module", "path": "src"},
        ],
        "edges": [
            {
                "id": "contains:demo:module:src",
                "source": "repo:demo",
                "target": "module:src",
                "type": "contains",
                "weight": 1,
            }
        ],
        "files": [
            {
                "id": "file:src/app.js",
                "path": "src/app.js",
                "label": "app.js",
                "module": "src",
                "extension": "js",
                "line_count": 10,
                "symbol_count": 1,
                "imports": [],
                "imported_by": [],
                "import_count": 0,
                "imported_by_count": 0,
                "isolated": False,
                "entrypoint": True,
                "unreferenced": False,
                "symbols": ["symbol:src/app.js:3:start"],
            }
        ],
        "symbols": [
            {
                "id": "symbol:src/app.js:3:start",
                "name": "start",
                "kind": "function",
                "file_path": "src/app.js",
                "line": 3,
                "signature": "function start()",
                "exported": True,
                "container": "",
            }
        ],
        "file_edges": [],
        "semantic_nodes": [
            {
                "id": "route:/home",
                "label": "/home",
                "type": "route",
                "path": "",
                "line": 0,
                "detail": "rota/tela",
            }
        ],
        "semantic_edges": [
            {
                "id": "sem:symbol:src/app.js:3:start->route:/home:navigates",
                "source": "symbol:src/app.js:3:start",
                "target": "route:/home",
                "type": "navigates",
                "weight": 1,
            }
        ],
        "findings": [],
    }


def test_stable_graph_node_id_is_deterministic_and_commit_scoped() -> None:
    repo_id = uuid.uuid4()

    first = stable_graph_node_id(repo_id, "abc", kind="function", name="start", path="src/app.js")
    second = stable_graph_node_id(repo_id, "abc", kind="function", name="start", path="src/app.js")
    other_commit = stable_graph_node_id(
        repo_id, "def", kind="function", name="start", path="src/app.js"
    )

    assert first == second
    assert first != other_commit
    assert first == f"repo:{repo_id}@abc:file:src/app.js#start"


def test_stable_graph_node_id_uses_sql_namespace_for_sql_entities() -> None:
    repo_id = uuid.uuid4()

    node_id = stable_graph_node_id(
        repo_id,
        "abc",
        kind="table",
        name="public.users",
        path="schema/001.sql",
    )

    assert node_id == f"repo:{repo_id}@abc:sql:schema/001.sql#table:public.users"


def test_translate_sandbox_graph_rows_and_medium_confidence_for_edges_without_snippet() -> None:
    repo_id = uuid.uuid4()

    rows = translate_sandbox_graph(repo_id=repo_id, commit_sha="abc", graph=_sample_graph())

    assert len(rows.nodes) == 5
    assert len(rows.edges) == 2
    assert {row.kind for row in rows.nodes} >= {"repo", "module", "file", "function", "route"}
    assert all(edge.confidence == "medium" for edge in rows.edges)
    assert all(edge.evidence["snippet"] is None for edge in rows.edges)


def test_translate_sandbox_graph_disambiguates_duplicate_symbols() -> None:
    repo_id = uuid.uuid4()
    graph = _sample_graph()
    graph["symbols"] = [
        {
            "id": "symbol:src/app.js:3:start",
            "name": "start",
            "kind": "function",
            "file_path": "src/app.js",
            "line": 3,
            "container": "",
        },
        {
            "id": "symbol:src/app.js:8:start",
            "name": "start",
            "kind": "function",
            "file_path": "src/app.js",
            "line": 8,
            "container": "",
        },
    ]

    rows = translate_sandbox_graph(repo_id=repo_id, commit_sha="abc", graph=graph)
    ids = [row.id for row in rows.nodes]

    assert len(ids) == len(set(ids))
    assert f"repo:{repo_id}@abc:file:src/app.js#start" in ids
    assert f"repo:{repo_id}@abc:file:src/app.js#start@symbol:src/app.js:8:start" in ids


def test_translate_sandbox_graph_ignores_invalid_line_numbers() -> None:
    repo_id = uuid.uuid4()
    graph = _sample_graph()
    graph["symbols"][0]["line"] = "not-a-number"

    rows = translate_sandbox_graph(repo_id=repo_id, commit_sha="abc", graph=graph)
    symbol = next(row for row in rows.nodes if row.name == "start")

    assert symbol.line_start is None
    assert symbol.line_end is None


def test_translate_sandbox_graph_preserves_roslyn_extractor_and_external_targets() -> None:
    repo_id = uuid.uuid4()
    graph = _sample_graph()
    graph["semantic_nodes"] = [
        {
            "id": "roslyn:UserService.cs#Demo.Services.UserService.ListActiveUsers()",
            "label": "ListActiveUsers",
            "name": "Demo.Services.UserService.ListActiveUsers()",
            "type": "method",
            "path": "UserService.cs",
            "file_path": "UserService.cs",
            "line": 24,
            "line_end": 30,
            "source_extractor": "static_roslyn",
            "extractor_version": "0.1.0",
            "attrs": {"accessibility": "public"},
        }
    ]
    graph["semantic_edges"] = [
        {
            "id": "roslyn:sql",
            "source": "roslyn:UserService.cs#Demo.Services.UserService.ListActiveUsers()",
            "target": "ref:dbo.Users",
            "target_external": "ref:dbo.Users",
            "type": "references",
            "confidence": "low",
            "source_extractor": "static_roslyn",
            "extractor_version": "0.1.0",
            "evidence": {
                "file": "UserService.cs",
                "line_start": 27,
                "line_end": 27,
                "snippet": "SELECT * FROM dbo.Users",
            },
            "attrs": {"placeholder_kind": "db_reference_unresolved"},
        }
    ]

    rows = translate_sandbox_graph(repo_id=repo_id, commit_sha="abc", graph=graph)
    roslyn_node = next(row for row in rows.nodes if row.source_extractor == "static_roslyn")
    roslyn_edge = next(row for row in rows.edges if row.source_extractor == "static_roslyn")

    assert roslyn_node.id == (
        f"repo:{repo_id}@abc:file:UserService.cs#Demo.Services.UserService.ListActiveUsers()"
    )
    assert roslyn_node.line_end == 30
    assert roslyn_edge.target_id is None
    assert roslyn_edge.target_external == "ref:dbo.Users"
    assert roslyn_edge.confidence == "low"
    assert roslyn_edge.evidence["snippet"] == "SELECT * FROM dbo.Users"
    assert roslyn_edge.evidence["attrs"] == {"placeholder_kind": "db_reference_unresolved"}


def test_translate_sandbox_graph_preserves_static_sql_and_does_not_reconcile_refs() -> None:
    repo_id = uuid.uuid4()
    graph = _sample_graph()
    graph["semantic_nodes"] = [
        {
            "id": "sql:schema.sql#table:public.users",
            "label": "public.users",
            "name": "public.users",
            "type": "table",
            "path": "schema.sql",
            "file_path": "schema.sql",
            "line": 1,
            "source_extractor": "static_sql",
            "extractor_version": "0.1.0",
        },
        {
            "id": "roslyn:UserService.cs#Demo.Service.ListUsers()",
            "label": "ListUsers",
            "name": "Demo.Service.ListUsers()",
            "type": "method",
            "path": "UserService.cs",
            "file_path": "UserService.cs",
            "line": 10,
            "source_extractor": "static_roslyn",
            "extractor_version": "0.1.0",
        },
    ]
    graph["semantic_edges"] = [
        {
            "id": "roslyn:ref-users",
            "source": "roslyn:UserService.cs#Demo.Service.ListUsers()",
            "target": "ref:Users",
            "target_external": "ref:Users",
            "type": "references",
            "confidence": "low",
            "source_extractor": "static_roslyn",
            "extractor_version": "0.1.0",
        }
    ]

    rows = translate_sandbox_graph(repo_id=repo_id, commit_sha="abc", graph=graph)
    sql_node = next(row for row in rows.nodes if row.source_extractor == "static_sql")
    ref_edge = next(row for row in rows.edges if row.source_extractor == "static_roslyn")

    assert sql_node.id == f"repo:{repo_id}@abc:sql:schema.sql#table:public.users"
    assert ref_edge.target_id is None
    assert ref_edge.target_external == "ref:Users"


def test_translate_sandbox_graph_preserves_doc_import_ids_and_attrs() -> None:
    repo_id = uuid.uuid4()
    document_id = uuid.uuid4()
    table_id = f"repo:{repo_id}@abc:doc:{document_id}#table:dbo.Users"
    graph = _sample_graph()
    graph["semantic_nodes"] = [
        {
            "id": table_id,
            "label": "dbo.Users",
            "name": "dbo.Users",
            "type": "table",
            "path": "DATABASE_SCHEMA_Edu_CBE_2.md",
            "file_path": "DATABASE_SCHEMA_Edu_CBE_2.md",
            "line": 25,
            "source_extractor": "doc_import",
            "extractor_version": "0.1.0",
            "attrs": {"document_id": str(document_id), "chunk_index": 7},
        }
    ]
    graph["semantic_edges"] = []

    rows = translate_sandbox_graph(repo_id=repo_id, commit_sha="abc", graph=graph)
    doc_node = next(row for row in rows.nodes if row.source_extractor == "doc_import")

    assert doc_node.id == table_id
    assert doc_node.attrs["document_id"] == str(document_id)
    assert doc_node.attrs["chunk_index"] == 7


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
    repo = SimpleNamespace(default_branch="Master", slug="Seller")
    sandbox = SimpleNamespace(host="sandbox", session_port=8080)

    commit = await resolve_repo_graph_commit_sha(
        provider=provider,  # type: ignore[arg-type]
        repo=repo,  # type: ignore[arg-type]
        sandbox=sandbox,  # type: ignore[arg-type]
    )

    assert commit == "abc123head"
    assert provider.refs == ["Master", "HEAD"]
