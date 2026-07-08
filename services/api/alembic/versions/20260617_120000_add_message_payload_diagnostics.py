"""add_message_payload_diagnostics

Revision ID: 20260617_120000
Revises: cb923ebe7375
Create Date: 2026-06-16 22:51:58.979574

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260617_120000"
down_revision: Union[str, Sequence[str], None] = "cb923ebe7375"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "messages",
        sa.Column(
            "payload_diagnostics",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("messages", "payload_diagnostics")
