from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cappy_llm_reconciliation import EXTRACTOR_VERSION, SOURCE_EXTRACTOR
from cappy_llm_reconciliation.ids import original_edge_key

PLACEHOLDER_KIND_REF = "ref_entity"
PLACEHOLDER_KIND_TABLE = "table_physical"


@dataclass(frozen=True)
class RefEdge:
    source_id: str
    target_external: str
    edge_type: str
    evidence: dict[str, Any]

    @property
    def ref_name(self) -> str:
        return self.target_external.removeprefix("ref:").removeprefix("table:")

    @property
    def placeholder_kind(self) -> str:
        return (
            PLACEHOLDER_KIND_TABLE
            if self.target_external.startswith("table:")
            else PLACEHOLDER_KIND_REF
        )

    @property
    def table_schema_and_name(self) -> tuple[str | None, str]:
        value = self.target_external.removeprefix("table:")
        if "." not in value:
            return None, value
        schema, table = value.split(".", 1)
        return schema or None, table

    def key(self, *, repo_id: str, commit_sha: str) -> str:
        return original_edge_key(
            repo_id=repo_id,
            commit_sha=commit_sha,
            source_id=self.source_id,
            target_external=self.target_external,
            edge_type=self.edge_type,
        )


@dataclass(frozen=True)
class Candidate:
    id: str
    kind: str
    name: str
    qualified_name: str
    source_extractor: str
    document_id: str | None = None
    chunk_index: int | None = None
    chunk_excerpt: str = ""
    embedding: list[float] | None = None

    @property
    def table_schema_and_name(self) -> tuple[str | None, str]:
        if self.kind != "table" or "." not in self.qualified_name:
            return None, self.qualified_name
        schema, table = self.qualified_name.split(".", 1)
        return schema or None, table


@dataclass(frozen=True)
class RankedCandidate:
    candidate: Candidate
    score: float
    name_score: float
    embedding_score: float


@dataclass
class Metrics:
    refs_total: int = 0
    resolved_strict: int = 0
    resolved_fuzzy: int = 0
    resolved_llm: int = 0
    unresolved_llm_no_match: int = 0
    unresolved_invalid_output: int = 0
    duration_ms_strict: int = 0
    duration_ms_fuzzy: int = 0
    duration_ms_llm: int = 0
    llm_calls: int = 0
    llm_input_tokens_estimated: int = 0
    llm_output_tokens_estimated: int = 0
    placeholder_kinds: dict[str, dict[str, int]] = field(default_factory=dict)

    def add_total(self, ref: RefEdge) -> None:
        self._bucket(ref.placeholder_kind)["total"] += 1

    def add_resolved(self, ref: RefEdge, mode: str) -> None:
        self._bucket(ref.placeholder_kind)[f"resolved_{mode}"] += 1

    def add_unresolved(self, ref: RefEdge) -> None:
        self._bucket(ref.placeholder_kind)["unresolved"] += 1

    def _bucket(self, kind: str) -> dict[str, int]:
        return self.placeholder_kinds.setdefault(
            kind,
            {
                "total": 0,
                "resolved_strict": 0,
                "resolved_fuzzy": 0,
                "resolved_llm": 0,
                "unresolved": 0,
            },
        )

    def as_dict(
        self, *, repo_id: str, commit_sha: str, llm_model: str | None
    ) -> dict[str, Any]:
        return {
            "repo_id": repo_id,
            "commit_sha": commit_sha,
            "extractor_version": EXTRACTOR_VERSION,
            "llm_model": llm_model,
            **self.__dict__,
        }


@dataclass
class Graph:
    edges: dict[str, dict[str, Any]] = field(default_factory=dict)
    diagnostics: list[dict[str, Any]] = field(default_factory=list)

    def add_resolution(
        self,
        *,
        repo_id: str,
        commit_sha: str,
        ref: RefEdge,
        target: Candidate,
        confidence: str,
        mode: str,
        candidates: list[Candidate],
        llm_model: str | None = None,
        llm_rationale: str | None = None,
    ) -> None:
        edge_key = ref.key(repo_id=repo_id, commit_sha=commit_sha)
        edge_id = f"llm_gap:{edge_key}:{target.id}"
        chunk_ids = (
            sorted({c.chunk_index for c in candidates if c.chunk_index is not None})
            or None
        )
        attrs = {
            "original_edge_key": edge_key,
            "original_target_external": ref.target_external,
            "resolution_mode": mode,
            "placeholder_kind": ref.placeholder_kind,
            "candidates_considered": [c.id for c in candidates[:5]],
            "llm_model": llm_model if mode == "llm" else None,
            "llm_rationale": (llm_rationale or "")[:120] if mode == "llm" else None,
            "chunk_ids": chunk_ids,
        }
        self.edges.setdefault(
            edge_id,
            {
                "id": edge_id,
                "source": ref.source_id,
                "target": target.id,
                "target_id": target.id,
                "type": "resolves_to",
                "weight": 1,
                "evidence": _clean_evidence(ref.evidence),
                "confidence": confidence,
                "source_extractor": SOURCE_EXTRACTOR,
                "extractor_version": EXTRACTOR_VERSION,
                "attrs": attrs,
            },
        )

    def diagnostic(
        self, *, code: str, level: str, ref: RefEdge, payload: dict[str, Any]
    ) -> None:
        self.diagnostics.append(
            {
                "code": code,
                "level": level,
                "ref_name": ref.ref_name,
                "placeholder_kind": ref.placeholder_kind,
                "source_id": ref.source_id,
                "target_external": ref.target_external,
                **payload,
            }
        )


def _clean_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "file": evidence.get("file"),
        "line_start": evidence.get("line_start"),
        "line_end": evidence.get("line_end"),
        "snippet": evidence.get("snippet"),
    }
