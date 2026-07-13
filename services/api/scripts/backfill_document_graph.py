"""Backfill document graph rows from already indexed document chunks."""

from __future__ import annotations

import asyncio
import logging

from app.infrastructure.database import async_session_factory
from app.infrastructure.document_graph import replace_document_graph
from app.infrastructure.orm_models import Document, Skill
from sqlalchemy import select

log = logging.getLogger(__name__)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    async with async_session_factory() as session:
        rows = await session.execute(
            select(Document).where(Document.status == "indexed").order_by(Document.created_at)
        )
        documents = list(rows.scalars())
        for document in documents:
            chunk_rows = await session.execute(
                select(Skill).where(Skill.document_id == document.id).order_by(Skill.chunk_index)
            )
            chunks = [skill.content for skill in chunk_rows.scalars() if skill.content]
            if not chunks:
                continue
            await replace_document_graph(session, document, "\n\n".join(chunks))
            log.info("backfilled document graph: %s (%d chunks)", document.title, len(chunks))
        await session.commit()


if __name__ == "__main__":
    asyncio.run(main())
