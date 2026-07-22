"""add project chat suggestions

Revision ID: 6c4f9b2a7d81
Revises: f828a0d8fff6
Create Date: 2026-07-22 10:45:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6c4f9b2a7d81"
down_revision: str | Sequence[str] | None = "f828a0d8fff6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_suggestions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=96), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("safety_state", sa.String(length=32), nullable=False),
        sa.Column("freshness_state", sa.String(length=32), nullable=False),
        sa.Column("analysis_window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("analysis_window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_calibrated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suppressed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suppressed_by", sa.Uuid(), nullable=True),
        sa.Column("suppression_reason", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["suppressed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_project_suggestions_category", "project_suggestions", ["category"])
    op.create_index(
        "ix_project_suggestions_repository_id", "project_suggestions", ["repository_id"]
    )
    op.create_index(
        "ix_project_suggestions_repo_source",
        "project_suggestions",
        ["repository_id", "source"],
    )
    op.create_index(
        "ix_project_suggestions_repo_status_priority",
        "project_suggestions",
        ["repository_id", "status", "priority"],
    )
    op.create_index("ix_project_suggestions_safety_state", "project_suggestions", ["safety_state"])
    op.create_index("ix_project_suggestions_source", "project_suggestions", ["source"])
    op.create_index("ix_project_suggestions_status", "project_suggestions", ["status"])

    op.create_table(
        "project_suggestion_calibration_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("trigger", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("analysis_window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("analysis_window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("eligible_message_count", sa.Integer(), nullable=False),
        sa.Column("eligible_user_count", sa.Integer(), nullable=False),
        sa.Column("suggestions_created", sa.Integer(), nullable=False),
        sa.Column("suggestions_activated", sa.Integer(), nullable=False),
        sa.Column("suggestions_suppressed", sa.Integer(), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_project_suggestion_runs_repo_created",
        "project_suggestion_calibration_runs",
        ["repository_id", "created_at"],
    )
    op.create_index(
        "ix_project_suggestion_calibration_runs_repository_id",
        "project_suggestion_calibration_runs",
        ["repository_id"],
    )
    op.create_index(
        "ix_project_suggestion_calibration_runs_status",
        "project_suggestion_calibration_runs",
        ["status"],
    )
    op.create_index(
        "ix_project_suggestion_calibration_runs_trigger",
        "project_suggestion_calibration_runs",
        ["trigger"],
    )


def downgrade() -> None:
    op.drop_table("project_suggestion_calibration_runs")
    op.drop_table("project_suggestions")
