"""add_signoz_service_name_to_repositories

Revision ID: 20260513_130000
Revises: 20260513_100000
Create Date: 2026-05-13 13:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260513_130000"
down_revision: Union[str, Sequence[str], None] = "20260513_100000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "repositories",
        sa.Column("signoz_service_name", sa.String(256), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("repositories", "signoz_service_name")
