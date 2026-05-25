from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from cappy_llm_reconciliation import EXTRACTOR_VERSION
from cappy_llm_reconciliation.db import load_inputs
from cappy_llm_reconciliation.llm import decide_match
from cappy_llm_reconciliation.matching import (
    confident_fuzzy_match,
    rank_candidates_for_ref,
    strict_match_for_ref,
)
from cappy_llm_reconciliation.models import (
    Candidate,
    Graph,
    Metrics,
    RankedCandidate,
    RefEdge,
)
from cappy_llm_reconciliation.providers import (
    LlmConfig,
    embed_text,
    embed_texts,
    resolve_embedding_config,
    resolve_llm_config,
)


@dataclass(frozen=True)
class ReconcileOptions:
    repo_id: str
    commit_sha: str
    db_url: str
    limit: int | None = None
    mode: str = "all"
    llm_model: str | None = None


async def reconcile(options: ReconcileOptions) -> dict[str, Any]:
    refs, candidates = await load_inputs(
        db_url=options.db_url,
        repo_id=options.repo_id,
        commit_sha=options.commit_sha,
        limit=options.limit,
    )
    graph = Graph()
    metrics = Metrics(refs_total=len(refs))
    for ref in refs:
        metrics.add_total(ref)
    embedding_config = await resolve_embedding_config(options.db_url)
    llm_config = (
        None
        if options.mode != "all"
        else await resolve_llm_config(
            options.db_url,
            options.llm_model,
        )
    )
    embedding_cache: dict[str, list[float] | None] = {}
    rank_cache: dict[tuple[str, str], list[RankedCandidate]] = {}
    candidate_name_cache: dict[str, str] = {}
    if options.mode != "strict-only":
        await _prefetch_embeddings(
            refs=refs,
            embedding_config=embedding_config,
            embedding_cache=embedding_cache,
        )

    for ref in refs:
        started = time.perf_counter()
        strict = strict_match_for_ref(ref, candidates)
        metrics.duration_ms_strict += _elapsed_ms(started)
        if strict is not None:
            graph.add_resolution(
                repo_id=options.repo_id,
                commit_sha=options.commit_sha,
                ref=ref,
                target=strict,
                confidence="high",
                mode="strict",
                candidates=[strict],
            )
            metrics.resolved_strict += 1
            metrics.add_resolved(ref, "strict")
            continue
        if options.mode == "strict-only":
            _unresolved(graph, ref, [], code="unresolved_strict_only")
            metrics.unresolved_llm_no_match += 1
            metrics.add_unresolved(ref)
            continue

        started = time.perf_counter()
        ranked = await _rank(
            ref=ref,
            candidates=candidates,
            embedding_config=embedding_config,
            embedding_cache=embedding_cache,
            rank_cache=rank_cache,
            candidate_name_cache=candidate_name_cache,
        )
        metrics.duration_ms_fuzzy += _elapsed_ms(started)
        fuzzy = confident_fuzzy_match(ranked)
        considered = [item.candidate for item in ranked]
        if fuzzy is not None:
            graph.add_resolution(
                repo_id=options.repo_id,
                commit_sha=options.commit_sha,
                ref=ref,
                target=fuzzy,
                confidence="medium",
                mode="fuzzy",
                candidates=considered,
            )
            metrics.resolved_fuzzy += 1
            metrics.add_resolved(ref, "fuzzy")
            continue
        if options.mode == "no-llm" or llm_config is None:
            _unresolved(graph, ref, ranked, code="unresolved_no_llm")
            metrics.unresolved_llm_no_match += 1
            metrics.add_unresolved(ref)
            continue

        await _llm_phase(
            graph=graph,
            metrics=metrics,
            llm_config=llm_config,
            options=options,
            ref=ref,
            ranked=ranked,
        )

    summary = metrics.as_dict(
        repo_id=options.repo_id,
        commit_sha=options.commit_sha,
        llm_model=llm_config.model if llm_config else options.llm_model,
    )
    return {
        "nodes": [],
        "edges": list(graph.edges.values()),
        "diagnostics": graph.diagnostics,
        "summary": summary,
        "extractor_version": EXTRACTOR_VERSION,
        "llm_model": summary.get("llm_model"),
        "mode": options.mode,
    }


async def _rank(
    *,
    ref: RefEdge,
    candidates: list[Candidate],
    embedding_config: Any,
    embedding_cache: dict[str, list[float] | None],
    rank_cache: dict[tuple[str, str], list[RankedCandidate]],
    candidate_name_cache: dict[str, str],
) -> list[RankedCandidate]:
    snippet = str((ref.evidence or {}).get("snippet") or "")
    cache_key = (f"{ref.placeholder_kind}:{ref.ref_name}", snippet)
    if cache_key in rank_cache:
        return rank_cache[cache_key]
    if snippet not in embedding_cache:
        embedding_cache[snippet] = await embed_text(snippet, embedding_config)
    ranked = rank_candidates_for_ref(
        ref=ref,
        candidates=candidates,
        snippet_embedding=embedding_cache[snippet],
        candidate_name_cache=candidate_name_cache,
    )
    rank_cache[cache_key] = ranked
    return ranked


async def _prefetch_embeddings(
    *,
    refs: list[RefEdge],
    embedding_config: Any,
    embedding_cache: dict[str, list[float] | None],
) -> None:
    snippets = sorted(
        {
            str((ref.evidence or {}).get("snippet") or "")
            for ref in refs
            if str((ref.evidence or {}).get("snippet") or "").strip()
        }
    )
    missing = [snippet for snippet in snippets if snippet not in embedding_cache]
    if not missing:
        return
    embeddings = await embed_texts(missing, embedding_config)
    for snippet, embedding in zip(missing, embeddings, strict=False):
        embedding_cache[snippet] = embedding


async def _llm_phase(
    *,
    graph: Graph,
    metrics: Metrics,
    llm_config: LlmConfig,
    options: ReconcileOptions,
    ref: RefEdge,
    ranked: list[RankedCandidate],
) -> None:
    started = time.perf_counter()
    candidates = [item.candidate for item in ranked]
    metrics.llm_calls += 1
    decision = await decide_match(config=llm_config, ref=ref, candidates=candidates)
    metrics.duration_ms_llm += _elapsed_ms(started)
    if decision is None:
        graph.diagnostic(
            code="llm_invalid_output",
            level="warning",
            ref=ref,
            payload={"candidates": _candidate_trace(ranked)},
        )
        metrics.unresolved_invalid_output += 1
        metrics.add_unresolved(ref)
        return
    metrics.llm_input_tokens_estimated += decision.input_tokens_estimated
    metrics.llm_output_tokens_estimated += decision.output_tokens_estimated
    if decision.decision == "none":
        graph.diagnostic(
            code="llm_no_match",
            level="info",
            ref=ref,
            payload={
                "candidates": _candidate_trace(ranked),
                "llm_rationale": decision.rationale,
            },
        )
        metrics.unresolved_llm_no_match += 1
        metrics.add_unresolved(ref)
        return
    target = next(
        candidate
        for candidate in candidates
        if candidate.qualified_name == decision.matched_qualified_name
    )
    graph.add_resolution(
        repo_id=options.repo_id,
        commit_sha=options.commit_sha,
        ref=ref,
        target=target,
        confidence=decision.confidence,
        mode="llm",
        candidates=candidates,
        llm_model=llm_config.model,
        llm_rationale=decision.rationale,
    )
    metrics.resolved_llm += 1
    metrics.add_resolved(ref, "llm")


def _unresolved(
    graph: Graph,
    ref: RefEdge,
    ranked: list[RankedCandidate],
    *,
    code: str,
) -> None:
    graph.diagnostic(
        code=code,
        level="info",
        ref=ref,
        payload={"candidates": _candidate_trace(ranked)},
    )


def _candidate_trace(ranked: list[RankedCandidate]) -> list[dict[str, Any]]:
    return [
        {
            "node_id": item.candidate.id,
            "kind": item.candidate.kind,
            "qualified_name": item.candidate.qualified_name,
            "score": round(item.score, 4),
            "name_score": round(item.name_score, 4),
            "embedding_score": round(item.embedding_score, 4),
            "chunk_index": item.candidate.chunk_index,
        }
        for item in ranked[:5]
    ]


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
