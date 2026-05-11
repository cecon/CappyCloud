"""seed_default_sandbox

Revision ID: 72cdc895ab1c
Revises: 4d18192ad762
Create Date: 2026-04-19 12:41:33.820419

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "72cdc895ab1c"
down_revision: Union[str, Sequence[str], None] = "4d18192ad762"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Insere o sandbox padrão se ainda não existir."""
    pass


def downgrade() -> None:
    """Remove o sandbox padrão."""
    pass
