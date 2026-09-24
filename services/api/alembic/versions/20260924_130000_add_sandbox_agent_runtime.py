"""add sandbox agent runtime

Revision ID: badd8f7956d2
Revises: 5b7e2a91d4c3
Create Date: 2026-09-23 19:18:24.609994

Runtime do agente por sandbox: ``openclaude`` (gRPC, padrão) ou ``claude_cli``
(Claude Code oficial via Agent SDK). Sandboxes existentes ficam em openclaude.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "badd8f7956d2"
down_revision: str | Sequence[str] | None = "5b7e2a91d4c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "sandboxes",
        sa.Column(
            "agent_runtime",
            sa.String(length=32),
            server_default="openclaude",
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("sandboxes", "agent_runtime")
