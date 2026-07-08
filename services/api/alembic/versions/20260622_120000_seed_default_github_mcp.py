"""seed_default_github_mcp

Revision ID: 20260622_120000
Revises: f278fe418b7c
Create Date: 2026-06-22 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260622_120000"
down_revision: str | Sequence[str] | None = "f278fe418b7c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Seed the default GitHub MCP on the default sandbox without secrets."""
    op.execute(
        sa.text(
            """
            INSERT INTO mcp_servers (id, sandbox_id, name, command, args, env, enabled)
            SELECT
                gen_random_uuid(),
                s.id,
                'github',
                '/usr/local/bin/github-mcp-server-wrapper',
                '[]'::jsonb,
                '{}'::jsonb,
                TRUE
            FROM sandboxes s
            WHERE s.name = 'cappycloud-sandbox'
              AND NOT EXISTS (
                  SELECT 1
                  FROM mcp_servers m
                  WHERE m.sandbox_id = s.id
                    AND m.name = 'github'
              )
            """
        )
    )


def downgrade() -> None:
    """Remove only the default row created by this migration."""
    op.execute(
        sa.text(
            """
            DELETE FROM mcp_servers m
            USING sandboxes s
            WHERE m.sandbox_id = s.id
              AND s.name = 'cappycloud-sandbox'
              AND m.name = 'github'
              AND m.command = '/usr/local/bin/github-mcp-server-wrapper'
              AND m.args = '[]'::jsonb
              AND m.env = '{}'::jsonb
            """
        )
    )
