"""add_ai_provider_api_format

Revision ID: d177e4b41f25
Revises: e89304b857a9
Create Date: 2026-05-22 18:32:09.471832

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d177e4b41f25"
down_revision: Union[str, Sequence[str], None] = "e89304b857a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ai_providers",
        sa.Column(
            "api_format",
            sa.String(length=32),
            server_default="chat_completions",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("ai_providers", "api_format")
