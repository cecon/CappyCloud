from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from cappy_doc_import_extractor import EXTRACTOR_VERSION, SOURCE_EXTRACTOR
from cappy_doc_import_extractor.db import load_documents
from cappy_doc_import_extractor.dispatcher import extract_document
from cappy_doc_import_extractor.models import Graph


def main() -> int:
    parser = argparse.ArgumentParser(prog="cappy-doc-import-extractor")
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--document-ids")
    parser.add_argument("--out", required=True)
    parser.add_argument("--db-url", required=True)
    args = parser.parse_args()
    return asyncio.run(_main_async(args))


async def _main_async(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    repo_id = str(args.repo_id).strip()
    commit_sha = str(args.commit_sha).strip()
    out_path = Path(args.out).resolve()
    document_ids = _document_ids(args.document_ids)
    if not repo_id or not commit_sha:
        print("--repo-id and --commit-sha are required.", file=sys.stderr)
        return 1
    try:
        documents = await load_documents(
            db_url=str(args.db_url),
            repo_id=repo_id,
            document_ids=document_ids,
        )
    except Exception as exc:
        print(f"Failed to load documents: {exc}", file=sys.stderr)
        return 1

    graph = Graph()
    for document in documents:
        extract_document(
            graph=graph, document=document, repo_id=repo_id, commit_sha=commit_sha
        )

    elapsed = int((time.perf_counter() - started) * 1000)
    payload = {
        "source_extractor": SOURCE_EXTRACTOR,
        "extractor_version": EXTRACTOR_VERSION,
        "nodes": list(graph.nodes.values()),
        "edges": list(graph.edges.values()),
        "diagnostics": graph.diagnostics,
        "timings_ms": {"total": elapsed, "documents": len(documents)},
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    print(
        "cappy-doc-import-extractor completed "
        f"documents={len(documents)} nodes={len(graph.nodes)} "
        f"edges={len(graph.edges)} elapsed_ms={elapsed}"
    )
    return 0


def _document_ids(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    values = [item.strip() for item in raw.split(",") if item.strip()]
    return values or None


if __name__ == "__main__":
    raise SystemExit(main())
