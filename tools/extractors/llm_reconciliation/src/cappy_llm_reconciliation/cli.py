from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from cappy_llm_reconciliation.reconciler import ReconcileOptions, reconcile

log = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = _parser().parse_args()
    try:
        payload = asyncio.run(
            reconcile(
                ReconcileOptions(
                    repo_id=args.repo_id,
                    commit_sha=args.commit_sha,
                    db_url=args.db_url,
                    limit=args.limit,
                    mode=args.mode,
                    llm_model=args.llm_model,
                )
            )
        )
        Path(args.out).write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
    except Exception as exc:
        log.exception("llm_reconciliation failed: %s", exc)
        sys.exit(1)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cappy-llm-reconciliation")
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--db-url", required=True)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--mode",
        choices=["all", "strict-only", "no-llm"],
        default="all",
    )
    parser.add_argument("--llm-model", default=None)
    return parser


if __name__ == "__main__":
    main()
