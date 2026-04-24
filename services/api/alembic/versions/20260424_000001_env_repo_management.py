"""env_repo_management

Adiciona:
  - skills.repository_id   FK → repositories(id) ON DELETE SET NULL
  - sandboxes.register_token  para auto-registro seguro do container

Revision ID: a1b2c3d4e5f6
Revises: e574cbd3e4fe
Create Date: 2026-04-24 00:00:01.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "e574cbd3e4fe"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── skills.repository_id ──────────────────────────────────
    op.add_column(
        "skills",
        sa.Column("repository_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_skills_repository",
        "skills",
        "repositories",
        ["repository_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_skills_repository_id", "skills", ["repository_id"])

    # ── sandboxes.register_token ──────────────────────────────
    op.add_column(
        "sandboxes",
        sa.Column("register_token", sa.String(length=256), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sandboxes", "register_token")

    op.drop_index("ix_skills_repository_id", table_name="skills")
    op.drop_constraint("fk_skills_repository", "skills", type_="foreignkey")
    op.drop_column("skills", "repository_id")
