from __future__ import annotations

import math
import re
from collections.abc import Callable

from cappy_llm_reconciliation.models import (
    PLACEHOLDER_KIND_TABLE,
    Candidate,
    RankedCandidate,
    RefEdge,
)

BLOCKLIST = {
    "user",
    "item",
    "entity",
    "data",
    "model",
    "service",
    "repository",
    "context",
    "base",
    "common",
    "config",
    "configuration",
    "manager",
    "helper",
    "result",
    "response",
    "request",
    "dto",
    "viewmodel",
}


def normalize_name(value: str) -> str:
    name = (value or "").removeprefix("ref:").split(".")[-1].lower().strip()
    name = re.sub(r"[^a-z0-9_]+", "", name)
    if len(name) > 1 and name.endswith("s"):
        name = name[:-1]
    return name


def normalize_table_name(value: str) -> str:
    return (value or "").removeprefix("table:").split(".")[-1].strip()


def strict_match_for_ref(ref: RefEdge, candidates: list[Candidate]) -> Candidate | None:
    if ref.placeholder_kind == PLACEHOLDER_KIND_TABLE:
        return strict_match_table(ref, candidates)
    return strict_match(ref.ref_name, candidates)


def strict_match(ref_name: str, candidates: list[Candidate]) -> Candidate | None:
    normalized = normalize_name(ref_name)
    if len(normalized) < 4 or normalized in BLOCKLIST:
        return None
    matches = [
        candidate
        for candidate in candidates
        if normalize_name(candidate.name) == normalized
    ]
    return matches[0] if len(matches) == 1 else None


def strict_match_table(ref: RefEdge, candidates: list[Candidate]) -> Candidate | None:
    placeholder_schema, placeholder_table = ref.table_schema_and_name
    matches: list[Candidate] = []
    for candidate in candidates:
        if candidate.kind != "table":
            continue
        candidate_schema, candidate_table = candidate.table_schema_and_name
        if placeholder_schema:
            if _same_name(candidate_schema, placeholder_schema) and _same_name(
                candidate_table, placeholder_table
            ):
                matches.append(candidate)
            continue
        if _same_name(candidate_table, placeholder_table):
            matches.append(candidate)
    return matches[0] if len(matches) == 1 else None


def rank_candidates_for_ref(
    *,
    ref: RefEdge,
    candidates: list[Candidate],
    snippet_embedding: list[float] | None,
    limit: int = 5,
    candidate_name_cache: dict[str, str] | None = None,
) -> list[RankedCandidate]:
    if ref.placeholder_kind == PLACEHOLDER_KIND_TABLE:
        return rank_candidates(
            ref_name=ref.ref_name,
            candidates=[
                candidate for candidate in candidates if candidate.kind == "table"
            ],
            snippet_embedding=snippet_embedding,
            limit=limit,
            candidate_name_cache=candidate_name_cache,
            normalizer=normalize_table_name,
            cache_prefix="table",
        )
    return rank_candidates(
        ref_name=ref.ref_name,
        candidates=candidates,
        snippet_embedding=snippet_embedding,
        limit=limit,
        candidate_name_cache=candidate_name_cache,
    )


def rank_candidates(
    *,
    ref_name: str,
    candidates: list[Candidate],
    snippet_embedding: list[float] | None,
    limit: int = 5,
    candidate_name_cache: dict[str, str] | None = None,
    normalizer: Callable[[str], str] = normalize_name,
    cache_prefix: str = "ref",
) -> list[RankedCandidate]:
    normalized_ref = normalizer(ref_name)
    ranked: list[RankedCandidate] = []
    name_cache = candidate_name_cache if candidate_name_cache is not None else {}
    embedding_score_cache: dict[int, float] = {}
    for candidate in candidates:
        cache_key = f"{cache_prefix}:{candidate.id}"
        normalized_candidate = name_cache.get(cache_key)
        if normalized_candidate is None:
            normalized_candidate = normalizer(candidate.name)
            name_cache[cache_key] = normalized_candidate
        name_score = levenshtein_similarity(normalized_ref, normalized_candidate)
        embedding_key = id(candidate.embedding)
        if embedding_key in embedding_score_cache:
            embedding_score = embedding_score_cache[embedding_key]
        else:
            embedding_score = cosine_similarity(snippet_embedding, candidate.embedding)
            embedding_score_cache[embedding_key] = embedding_score
        score = (name_score * 0.5) + (embedding_score * 0.5)
        ranked.append(
            RankedCandidate(
                candidate=candidate,
                score=score,
                name_score=name_score,
                embedding_score=embedding_score,
            )
        )
    ranked.sort(key=lambda item: item.score, reverse=True)
    return ranked[:limit]


def _same_name(left: str | None, right: str | None) -> bool:
    return (left or "").casefold() == (right or "").casefold()


def confident_fuzzy_match(ranked: list[RankedCandidate]) -> Candidate | None:
    if not ranked:
        return None
    top = ranked[0]
    second_score = ranked[1].score if len(ranked) > 1 else 0.0
    if top.score >= 0.85 and top.score - second_score >= 0.15:
        return top.candidate
    return None


def levenshtein_similarity(left: str, right: str) -> float:
    if left == right:
        return 1.0
    if not left or not right:
        return 0.0
    distance = _levenshtein(left, right)
    return max(0.0, 1.0 - (distance / max(len(left), len(right))))


def cosine_similarity(left: list[float] | None, right: list[float] | None) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return max(0.0, min(1.0, dot / (left_norm * right_norm)))


def _levenshtein(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for i, left_char in enumerate(left, start=1):
        current = [i]
        for j, right_char in enumerate(right, start=1):
            current.append(
                min(
                    current[j - 1] + 1,
                    previous[j] + 1,
                    previous[j - 1] + (0 if left_char == right_char else 1),
                )
            )
        previous = current
    return previous[-1]
