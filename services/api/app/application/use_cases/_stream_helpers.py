"""Helpers de streaming para o use case StreamMessage."""

from __future__ import annotations

import uuid


async def inject_diff_comments(conversation_id: uuid.UUID, content: str) -> str:
    """Prefixa o conteúdo com comentários de diff pendentes e marca-os como bundled."""
    try:
        from sqlalchemy import text

        from app.infrastructure.database import async_session_factory

        async with async_session_factory() as session:
            rows = await session.execute(
                text(
                    "SELECT id, file_path, line, content FROM diff_comments "
                    "WHERE conversation_id = :cid AND bundled_at IS NULL "
                    "ORDER BY file_path, line"
                ),
                {"cid": str(conversation_id)},
            )
            comments = rows.fetchall()
            if not comments:
                return content

            lines = [f"at `{row.file_path}:{row.line}`: {row.content}" for row in comments]
            ids = ", ".join(f"'{row.id}'" for row in comments)
            await session.execute(
                text(f"UPDATE diff_comments SET bundled_at = NOW() WHERE id IN ({ids})")
            )
            await session.commit()
            return "\n".join(lines) + "\n\n" + content
    except Exception:
        return content
