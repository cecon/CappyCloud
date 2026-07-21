"""backfill default sandbox image

Revision ID: 4d90cbbafcbd
Revises: 3eddd8b3a893
Create Date: 2026-07-20 14:10:00.263239

"""

from collections.abc import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "4d90cbbafcbd"
down_revision: str | Sequence[str] | None = "3eddd8b3a893"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Preenche a imagem da sandbox padrão criada antes da coluna ``image``."""
    op.execute(
        """
        UPDATE sandboxes
        SET image = 'cappycloud-sandbox:latest'
        WHERE name = 'cappycloud-sandbox'
          AND COALESCE(image, '') = ''
        """
    )


def downgrade() -> None:
    """Reverte apenas o valor preenchido por esta migration."""
    op.execute(
        """
        UPDATE sandboxes
        SET image = ''
        WHERE name = 'cappycloud-sandbox'
          AND image = 'cappycloud-sandbox:latest'
        """
    )
