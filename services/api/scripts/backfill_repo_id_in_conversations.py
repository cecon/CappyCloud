#!/usr/bin/env python3
"""Backfill ``repo_id`` no JSONB ``conversations.repos``.

Conversas criadas antes do commit que introduziu ``skills.repo_id`` t\u00eam
``repos`` salvas como ``[{slug, alias, base_branch, branch_name, worktree_path}]``
sem o campo ``repo_id``. Este script resolve cada ``slug`` na tabela
``repositories`` e atualiza a conversa com ``repo_id`` preenchido.

\u00c9 idempotente: itens que j\u00e1 t\u00eam ``repo_id`` (n\u00e3o-nulo) s\u00e3o pulados.

Uso:
    python -m scripts.backfill_repo_id_in_conversations [--dry-run]

Vari\u00e1veis de ambiente lidas:
    DATABASE_URL  postgresql://user:pass@host/db (sem o ``+asyncpg``)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("backfill_repo_id")


def _db_url() -> str:
    raw = os.getenv("DATABASE_URL", "").strip()
    if not raw:
        log.error("DATABASE_URL n\u00e3o definida.")
        sys.exit(2)
    return raw.replace("postgresql+asyncpg://", "postgresql://", 1)


async def _build_slug_to_id(conn: asyncpg.Connection) -> dict[str, str]:
    rows = await conn.fetch("SELECT id, slug FROM repositories")
    return {r["slug"]: str(r["id"]) for r in rows}


async def _process(conn: asyncpg.Connection, dry_run: bool) -> tuple[int, int, int]:
    slug_to_id = await _build_slug_to_id(conn)
    log.info("%d repositories no cat\u00e1logo.", len(slug_to_id))

    rows = await conn.fetch(
        "SELECT id, repos FROM conversations WHERE repos IS NOT NULL AND repos::text <> '[]'"
    )
    log.info("%d conversas com repos para inspecionar.", len(rows))

    updated = 0
    items_filled = 0
    items_unresolved = 0
    for row in rows:
        repos = row["repos"]
        if isinstance(repos, str):
            repos = json.loads(repos)
        if not isinstance(repos, list):
            continue
        changed = False
        for item in repos:
            if not isinstance(item, dict):
                continue
            if item.get("repo_id"):
                continue
            slug = item.get("slug")
            if not slug:
                continue
            resolved = slug_to_id.get(slug)
            if resolved:
                item["repo_id"] = resolved
                items_filled += 1
                changed = True
            else:
                item["repo_id"] = None
                items_unresolved += 1
        if changed:
            updated += 1
            if not dry_run:
                await conn.execute(
                    "UPDATE conversations SET repos = $1::jsonb WHERE id = $2",
                    json.dumps(repos),
                    row["id"],
                )
    return updated, items_filled, items_unresolved


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="N\u00e3o escreve no banco.")
    args = parser.parse_args()

    conn = await asyncpg.connect(_db_url())
    try:
        updated, filled, unresolved = await _process(conn, args.dry_run)
    finally:
        await conn.close()

    mode = "DRY-RUN" if args.dry_run else "APPLIED"
    log.info(
        "%s: %d conversas atualizadas, %d itens preenchidos, %d slugs sem match.",
        mode,
        updated,
        filled,
        unresolved,
    )


if __name__ == "__main__":
    asyncio.run(main())
