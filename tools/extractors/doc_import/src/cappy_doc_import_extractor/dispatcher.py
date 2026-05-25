from __future__ import annotations

import re

from cappy_doc_import_extractor.markdown_schema_catalog import (
    parse_markdown_schema_catalog,
)
from cappy_doc_import_extractor.models import Graph, SourceDocument

_CATALOG_HEADER_RE = re.compile(
    r"^####\s+[\w-]+\.[^\s(]+\s*\([\d.]+\s+linhas\)",
    re.M,
)


def extract_document(
    *,
    graph: Graph,
    document: SourceDocument,
    repo_id: str,
    commit_sha: str,
) -> None:
    doc_format = detect_format(document)
    if doc_format == "markdown_schema_catalog":
        parse_markdown_schema_catalog(
            graph=graph,
            document=document,
            repo_id=repo_id,
            commit_sha=commit_sha,
        )
        return
    graph.diagnostic(
        document_id=document.id,
        level="warning",
        code="unsupported_format",
        message=f"unsupported source_type={document.source_type}",
    )


def detect_format(document: SourceDocument) -> str | None:
    if document.source_type == "markdown" and _CATALOG_HEADER_RE.search(document.text):
        return "markdown_schema_catalog"
    return None
