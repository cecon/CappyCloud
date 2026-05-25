from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT / "tools" / "extractors" / "llm_reconciliation" / "src"))

from cappy_llm_reconciliation.ids import original_edge_key  # noqa: E402
from cappy_llm_reconciliation.llm import decide_match  # noqa: E402
from cappy_llm_reconciliation.matching import (  # noqa: E402
    confident_fuzzy_match,
    rank_candidates,
    strict_match,
    strict_match_for_ref,
)
from cappy_llm_reconciliation.models import Candidate, RefEdge  # noqa: E402
from cappy_llm_reconciliation.providers import LlmConfig  # noqa: E402


def test_strict_match_rules() -> None:
    candidates = [
        _candidate("repo:1@a:doc:d#table:dbo.Empresa", "table", "dbo.Empresa"),
        _candidate("repo:1@a:doc:d#table:dbo.User", "table", "dbo.User"),
        _candidate("repo:1@a:doc:d#table:dbo.Customer", "table", "dbo.Customer"),
    ]

    assert strict_match("Empresa", candidates).qualified_name == "dbo.Empresa"  # type: ignore[union-attr]
    assert strict_match("User", candidates) is None
    assert strict_match("Id", candidates) is None
    assert strict_match("Customers", candidates).qualified_name == "dbo.Customer"  # type: ignore[union-attr]


def test_strict_match_table_placeholder_rules() -> None:
    candidates = [
        _candidate("repo:1@a:doc:d#table:dbo.tgGerAlmo", "table", "dbo.tgGerAlmo"),
        _candidate("repo:1@a:doc:d#table:archive.Almoxarifado", "table", "archive.Almoxarifado"),
        _candidate("repo:1@a:doc:d#table:dbo.Almoxarifado", "table", "dbo.Almoxarifado"),
        _candidate("repo:1@a:doc:d#table:dbo.Configuracao", "table", "dbo.Configuracao"),
    ]

    assert (
        strict_match_for_ref(_ref("table:tgGerAlmo", "maps_to_table"), candidates).qualified_name
        == "dbo.tgGerAlmo"
    )
    assert strict_match_for_ref(_ref("table:Almoxarifado", "maps_to_table"), candidates) is None
    assert strict_match_for_ref(_ref("table:Configuracoes", "maps_to_table"), candidates) is None
    assert (
        strict_match_for_ref(_ref("table:tggerAlmo", "maps_to_table"), candidates).qualified_name
        == "dbo.tgGerAlmo"
    )
    assert (
        strict_match_for_ref(
            _ref("table:dbo.tgGerAlmo", "maps_to_table"),
            candidates,
        ).qualified_name
        == "dbo.tgGerAlmo"
    )
    assert (
        strict_match_for_ref(
            _ref("table:dbo.Almoxarifado", "maps_to_table"),
            candidates,
        ).qualified_name
        == "dbo.Almoxarifado"
    )
    archive_only = [
        _candidate("repo:1@a:doc:d#table:archive.tgGerAlmo", "table", "archive.tgGerAlmo")
    ]
    assert strict_match_for_ref(_ref("table:dbo.tgGerAlmo", "maps_to_table"), archive_only) is None
    assert strict_match_for_ref(_ref("table:dbo.Missing", "maps_to_table"), candidates) is None


def test_fuzzy_confident_match_uses_score_and_gap() -> None:
    candidates = [
        _candidate("repo:1@a:doc:d#table:dbo.Empresa", "table", "dbo.Empresa", [1.0, 0.0]),
        _candidate("repo:1@a:doc:d#table:dbo.Cliente", "table", "dbo.Cliente", [0.0, 1.0]),
    ]

    ranked = rank_candidates(
        ref_name="Empresas",
        candidates=candidates,
        snippet_embedding=[1.0, 0.0],
    )

    assert ranked[0].score >= 0.85
    assert confident_fuzzy_match(ranked).qualified_name == "dbo.Empresa"  # type: ignore[union-attr]


def test_fuzzy_ambiguous_gap_falls_through() -> None:
    candidates = [
        _candidate("repo:1@a:doc:d#table:dbo.Empresa", "table", "dbo.Empresa", [1.0, 0.0]),
        _candidate("repo:1@a:doc:d#table:dbo.Empresas", "table", "dbo.Empresas", [0.98, 0.0]),
    ]

    ranked = rank_candidates(
        ref_name="Empresa",
        candidates=candidates,
        snippet_embedding=[1.0, 0.0],
    )

    assert ranked[0].score >= 0.85
    assert ranked[0].score - ranked[1].score < 0.15
    assert confident_fuzzy_match(ranked) is None


@pytest.mark.asyncio
async def test_llm_decision_match_none_and_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    ref = RefEdge(
        source_id="repo:1@a:file:x.cs#M",
        target_external="ref:Empresa",
        edge_type="references",
        evidence={"file": "x.cs", "line_start": 1, "line_end": 1, "snippet": "EmpresaBO"},
    )
    candidates = [_candidate("repo:1@a:doc:d#table:dbo.Empresa", "table", "dbo.Empresa")]
    config = LlmConfig(
        base_url="https://llm.test",
        api_key="k",
        model="m",
        api_format="chat_completions",
    )

    async def fake_match(*args, **kwargs):  # type: ignore[no-untyped-def]
        return {
            "decision": "match",
            "matched_qualified_name": "dbo.Empresa",
            "confidence": "high",
            "rationale": "line 1 uses EmpresaBO",
        }

    monkeypatch.setattr("cappy_llm_reconciliation.llm._call", fake_match)
    match = await decide_match(config=config, ref=ref, candidates=candidates)
    assert match is not None
    assert match.decision == "match"

    async def fake_none(*args, **kwargs):  # type: ignore[no-untyped-def]
        return {
            "decision": "none",
            "matched_qualified_name": None,
            "confidence": "medium",
            "rationale": "DTO assignment",
        }

    monkeypatch.setattr("cappy_llm_reconciliation.llm._call", fake_none)
    none = await decide_match(config=config, ref=ref, candidates=candidates)
    assert none is not None
    assert none.decision == "none"

    async def fake_invalid(*args, **kwargs):  # type: ignore[no-untyped-def]
        return {
            "decision": "match",
            "matched_qualified_name": "dbo.Desconhecida",
            "confidence": "high",
            "rationale": "bad",
        }

    monkeypatch.setattr("cappy_llm_reconciliation.llm._call", fake_invalid)
    assert await decide_match(config=config, ref=ref, candidates=candidates) is None


def test_original_edge_key_is_stable_and_commit_scoped() -> None:
    first = original_edge_key(
        repo_id="repo",
        commit_sha="abc",
        source_id="method",
        target_external="ref:Empresa",
        edge_type="references",
    )
    second = original_edge_key(
        repo_id="repo",
        commit_sha="abc",
        source_id="method",
        target_external="ref:Empresa",
        edge_type="references",
    )
    other_commit = original_edge_key(
        repo_id="repo",
        commit_sha="def",
        source_id="method",
        target_external="ref:Empresa",
        edge_type="references",
    )

    assert first == second
    assert first != other_commit


def _candidate(
    node_id: str,
    kind: str,
    qualified_name: str,
    embedding: list[float] | None = None,
) -> Candidate:
    return Candidate(
        id=node_id,
        kind=kind,
        name=qualified_name.split(".")[-1],
        qualified_name=qualified_name,
        source_extractor="doc_import",
        chunk_index=1,
        embedding=embedding,
    )


def _ref(target_external: str, edge_type: str = "references") -> RefEdge:
    return RefEdge(
        source_id="repo:1@a:file:x.cs#M",
        target_external=target_external,
        edge_type=edge_type,
        evidence={"file": "x.cs", "line_start": 1, "line_end": 1, "snippet": target_external},
    )
