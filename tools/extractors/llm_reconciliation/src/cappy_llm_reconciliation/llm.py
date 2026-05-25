from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

from cappy_llm_reconciliation.models import PLACEHOLDER_KIND_TABLE, Candidate, RefEdge
from cappy_llm_reconciliation.providers import LlmConfig


@dataclass(frozen=True)
class LlmDecision:
    decision: str
    matched_qualified_name: str | None
    confidence: str
    rationale: str
    input_tokens_estimated: int
    output_tokens_estimated: int


async def decide_match(
    *,
    config: LlmConfig,
    ref: RefEdge,
    candidates: list[Candidate],
) -> LlmDecision | None:
    prompt = _prompt(ref=ref, candidates=candidates)
    for attempt in range(2):
        payload = await _call(config, prompt if attempt == 0 else _retry_prompt(prompt))
        decision = _parse_decision(payload, candidates)
        if decision is not None:
            return LlmDecision(
                **decision,
                input_tokens_estimated=max(1, len(prompt) // 4),
                output_tokens_estimated=max(1, len(json.dumps(payload)) // 4),
            )
    return None


async def _call(config: LlmConfig, prompt: str) -> Any:
    url = f"{config.base_url.rstrip('/')}/{_endpoint(config.api_format)}"
    body = _body(config, prompt)
    async with httpx.AsyncClient(timeout=httpx.Timeout(90.0)) as client:
        response = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            },
            json=body,
        )
        response.raise_for_status()
        data = response.json()
    text = _extract_text(data, config.api_format)
    return json.loads(text)


def _endpoint(api_format: str) -> str:
    return "responses" if api_format == "responses" else "chat/completions"


def _body(config: LlmConfig, prompt: str) -> dict[str, Any]:
    if config.api_format == "responses":
        return {
            "model": config.model,
            "input": prompt,
            "temperature": 0,
            "text": {"format": {"type": "json_object"}},
        }
    return {
        "model": config.model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }


def _extract_text(data: dict[str, Any], api_format: str) -> str:
    if api_format == "responses":
        if isinstance(data.get("output_text"), str):
            return data["output_text"]
        for item in data.get("output", []) or []:
            for content in item.get("content", []) or []:
                if isinstance(content.get("text"), str):
                    return content["text"]
    choices = data.get("choices") or []
    if choices:
        content = choices[0].get("message", {}).get("content")
        if isinstance(content, str):
            return content
    return "{}"


def _parse_decision(payload: Any, candidates: list[Candidate]) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    decision = str(payload.get("decision") or "")
    matched = payload.get("matched_qualified_name")
    confidence = str(payload.get("confidence") or "")
    rationale = str(payload.get("rationale") or "")[:120]
    if decision not in {"match", "none"} or confidence not in {"high", "medium", "low"}:
        return None
    if decision == "none":
        return {
            "decision": "none",
            "matched_qualified_name": None,
            "confidence": confidence,
            "rationale": rationale,
        }
    allowed = {candidate.qualified_name for candidate in candidates}
    if not isinstance(matched, str) or matched not in allowed:
        return None
    return {
        "decision": "match",
        "matched_qualified_name": matched,
        "confidence": confidence,
        "rationale": rationale,
    }


def _retry_prompt(prompt: str) -> str:
    return (
        f"{prompt}\n\nYour previous output was invalid. Return only the JSON object, "
        "and matched_qualified_name must be one of the candidate qualified_name values."
    )


def _prompt(*, ref: RefEdge, candidates: list[Candidate]) -> str:
    if ref.placeholder_kind == PLACEHOLDER_KIND_TABLE:
        return _table_prompt(ref=ref, candidates=candidates)
    return _ref_prompt(ref=ref, candidates=candidates)


def _table_prompt(*, ref: RefEdge, candidates: list[Candidate]) -> str:
    evidence = ref.evidence or {}
    schema, physical_name = ref.table_schema_and_name
    schema_or_unknown = schema or "unknown"
    candidates_block = "\n".join(
        _table_candidate_line(candidate) for candidate in candidates
    )
    return f"""# Role
You disambiguate references between a declared EF entity mapping and a database schema. You DO NOT invent matches. You pick from a fixed candidate list or refuse.

# Input
A C# entity class declares it maps to physical table `{physical_name}` (schema: {schema_or_unknown}). We need to determine which table in the documented schema this corresponds to.

## Declaration evidence
File: {evidence.get("file")}
Lines {evidence.get("line_start")}-{evidence.get("line_end")}:
{evidence.get("snippet")}

## Candidate database tables
{candidates_block}

Each candidate is a (schema, table_name, source_chunk_excerpt) tuple.

# Rules
1. Pick EXACTLY ONE outcome:
   a. One specific candidate (by qualified_name) is the correct match.
   b. None — the declared physical table does not appear in the candidate list.
2. The declared name is a literal physical table name. Treat it as authoritative; reject candidates whose names differ unless the difference is purely schema/case.
3. If schema is provided in the declaration and no candidate matches it, prefer "none" over a wrong-schema match.
4. Rationale ≤ 120 chars, cite the line of the declaration or the chunk excerpt.

# Output
Return ONLY JSON:
{{
  "decision": "match" | "none",
  "matched_qualified_name": "string or null",
  "confidence": "high" | "medium" | "low",
  "rationale": "string, max 120 chars"
}}"""


def _table_candidate_line(candidate: Candidate) -> str:
    schema, table = candidate.table_schema_and_name
    return f"- ({schema or 'unknown'}, {table}, {candidate.chunk_excerpt})"


def _ref_prompt(*, ref: RefEdge, candidates: list[Candidate]) -> str:
    evidence = ref.evidence or {}
    candidates_block = "\n".join(
        f"- ({candidate.kind}, {candidate.qualified_name}, {candidate.chunk_excerpt})"
        for candidate in candidates
    )
    return f"""Role
You disambiguate references between C# code and a database schema. You DO NOT invent matches. You pick from a fixed candidate list or refuse.
Input
A C# method contains a reference to an identifier {ref.ref_name}. We need to determine whether this identifier corresponds to a database entity in the schema, and if so, which one.
C# evidence
File: {evidence.get("file")}
Lines {evidence.get("line_start")}-{evidence.get("line_end")}:
{evidence.get("snippet")}
Candidate database entities
{candidates_block}
Each candidate is a (kind, qualified_name, source_chunk_excerpt) tuple. The chunk excerpt is the schema documentation segment where the candidate is defined.
Rules

Pick EXACTLY ONE of these outcomes:
a. One specific candidate (by its qualified_name) is the correct match.
b. None of the candidates is correct (the C# identifier likely refers to something else: DTO, view model, generic type, framework type, etc.).
Decide based on evidence in the C# snippet and the chunk excerpts. Do not guess based on name alone if the snippet contradicts the schema (e.g., the C# usage is clearly a DTO assignment, not a query).
If multiple candidates seem plausible and you cannot disambiguate from the evidence, return "none". Ambiguity is not a match.
Your rationale must cite the evidence: which line of the snippet and/or which chunk excerpt drove the decision. Max 120 characters.
Output
Return ONLY a JSON object, no prose, no markdown fences:
{{
"decision": "match" | "none",
"matched_qualified_name": "string (required if decision=match, else null)",
"confidence": "high" | "medium" | "low",
"rationale": "string, max 120 chars"
}}"""
