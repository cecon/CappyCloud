from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PROJECT = ROOT / "tools" / "extractors" / "csharp" / "Cappy.RoslynExtractor.csproj"
FIXTURES = ROOT / "services" / "api" / "tests" / "fixtures"


def _run_extractor(repo: Path, out_path: Path) -> tuple[subprocess.CompletedProcess[str], dict]:
    result = subprocess.run(
        [
            "dotnet",
            "run",
            "--project",
            str(PROJECT),
            "--",
            "--repo",
            str(repo),
            "--out",
            str(out_path),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    payload = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    return result, payload


def test_roslyn_extractor_emits_snapshot_counts(tmp_path: Path) -> None:
    result, payload = _run_extractor(FIXTURES / "csharp_basic", tmp_path / "graph.json")

    assert result.returncode == 0, result.stderr
    assert payload["source_extractor"] == "static_roslyn"
    assert payload["extractor_version"] == "0.2.0"
    assert len(payload["nodes"]) == 23
    assert len(payload["edges"]) == 37
    assert payload["diagnostics"] == []
    assert {node["type"] for node in payload["nodes"]} >= {
        "namespace",
        "class",
        "interface",
        "method",
        "property",
        "field",
        "event",
    }
    assert any(edge["type"] == "implements" for edge in payload["edges"])
    assert any(edge["type"] == "calls" and edge.get("target") for edge in payload["edges"])
    assert any(
        edge["type"] == "references"
        and edge.get("target_external") == "ref:dbo.Users"
        and edge["confidence"] == "low"
        for edge in payload["edges"]
    )


def test_roslyn_extractor_emits_entity_refs_for_ef_usage(tmp_path: Path) -> None:
    result, payload = _run_extractor(FIXTURES / "csharp_ef_usage", tmp_path / "graph.json")

    assert result.returncode == 0, result.stderr
    assert payload["extractor_version"] == "0.2.0"
    assert len(payload["nodes"]) == 41
    assert len(payload["edges"]) == 58

    ref_edges = [
        edge
        for edge in payload["edges"]
        if edge["type"] == "references" and edge.get("target_external", "").startswith("ref:")
    ]
    pairs = {(edge["source"].split("#", 1)[1], edge["target_external"]) for edge in ref_edges}
    assert pairs == {
        (
            "Demo.Services.EFUsage.AddOrders(System.Collections.Generic.List__Demo.Domain.Order__)",
            "ref:Order",
        ),
        ("Demo.Services.EFUsage.AddUser(Demo.Domain.User)", "ref:User"),
        ("Demo.Services.EFUsage.Products()", "ref:Product"),
        ("Demo.Services.EFUsage.SetOrder()", "ref:Order"),
        ("Demo.Services.EFUsage.UsersTwice()", "ref:User"),
    }
    assert {edge["target_external"] for edge in ref_edges}.isdisjoint(
        {
            "ref:Set",
            "ref:SaveChanges",
            "ref:Add",
            "ref:Entry",
            "ref:Database",
        }
    )
    assert (
        sum(
            1
            for edge in ref_edges
            if edge["source"].endswith("#Demo.Services.EFUsage.UsersTwice()")
            and edge["target_external"] == "ref:User"
        )
        == 1
    )
    assert any(edge["evidence"]["snippet"] == "ctx.Set<Order>()" for edge in ref_edges)
    assert any(edge["evidence"]["snippet"] == "ctx.AddRange(orders)" for edge in ref_edges)
    assert any(
        diagnostic.get("code") == "ef_set_unresolved_generic" and diagnostic["level"] == "info"
        for diagnostic in payload["diagnostics"]
    )


def test_roslyn_extractor_emits_ef_table_mappings(tmp_path: Path) -> None:
    result, payload = _run_extractor(FIXTURES / "csharp_ef_mappings", tmp_path / "graph.json")

    assert result.returncode == 0, result.stderr
    assert payload["extractor_version"] == "0.2.0"

    mapping_edges = [edge for edge in payload["edges"] if edge["type"] == "maps_to_table"]
    triples = {
        (
            edge["source"].split("#", 1)[1],
            edge["target_external"],
            edge["attrs"]["mapping_source"],
        )
        for edge in mapping_edges
    }
    assert triples == {
        ("Demo.Mapping.EntityA", "table:PhysicalA", "fluent_on_model_creating"),
        ("Demo.Mapping.EntityB", "table:dbo.PhysicalB", "fluent_on_model_creating"),
        ("Demo.Mapping.EntityC", "table:PhysicalC", "fluent_on_model_creating"),
        ("Demo.Mapping.EntityD", "table:PhysicalD", "entity_type_configuration"),
        ("Demo.Mapping.EntityE", "table:PhysicalE", "entity_type_configuration"),
        ("Demo.Mapping.EntityG", "table:PhysicalG", "entity_type_configuration"),
        ("Demo.Mapping.EntityF", "table:X", "data_annotation"),
        ("Demo.Mapping.EntityF", "table:Y", "fluent_on_model_creating"),
    }
    assert sum(1 for edge in mapping_edges if edge["target_external"] == "table:PhysicalA") == 1
    assert any(
        edge["target_external"] == "table:dbo.PhysicalB" and edge["attrs"]["schema"] == "dbo"
        for edge in mapping_edges
    )
    assert any(
        edge["attrs"].get("configuration_class") == "Demo.Mapping.EntityDConfiguration"
        for edge in mapping_edges
    )
    assert any(
        diagnostic.get("code") == "ef_table_attr_non_literal" and diagnostic["level"] == "info"
        for diagnostic in payload["diagnostics"]
    )
    assert any(
        diagnostic.get("code") == "ef_mapping_conflict" and diagnostic["level"] == "warning"
        for diagnostic in payload["diagnostics"]
    )


def test_roslyn_extractor_returns_partial_output_for_broken_files(tmp_path: Path) -> None:
    result, payload = _run_extractor(FIXTURES / "csharp_broken", tmp_path / "graph.json")

    assert result.returncode == 0, result.stderr
    assert len(payload["nodes"]) == 6
    assert len(payload["edges"]) == 4
    assert len(payload["diagnostics"]) >= 1
    assert any(node["label"] == "Good" for node in payload["nodes"])
