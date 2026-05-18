"""add_signoz_service_name_to_repositories

Revision ID: 20260513_130001
Revises: 20260513_130000
Create Date: 2026-05-13 13:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260513_130001"
down_revision: Union[str, Sequence[str], None] = "20260513_130000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _has_column("repositories", "signoz_service_name"):
        op.add_column(
            "repositories",
            sa.Column("signoz_service_name", sa.String(256), nullable=True),
        )


def downgrade() -> None:
    if _has_column("repositories", "signoz_service_name"):
        op.drop_column("repositories", "signoz_service_name")
