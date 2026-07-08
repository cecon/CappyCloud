"""agentic_delivery_factory

Revision ID: cb923ebe7375
Revises: ded3d62e1adb
Create Date: 2026-06-16 19:26:40.899203

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "cb923ebe7375"
down_revision: Union[str, Sequence[str], None] = "ded3d62e1adb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _jsonb() -> postgresql.JSONB:
    return postgresql.JSONB(astext_type=sa.Text())


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    ]


_KNOWLEDGE_REUSE_INDEXES = {
    "source_repository_id": "ix_agentic_reuse_source_repo_id",
    "target_repository_id": "ix_agentic_reuse_target_repo_id",
    "source_domain_key": "ix_agentic_reuse_source_domain",
    "target_domain_key": "ix_agentic_reuse_target_domain",
}

_EXTERNAL_ACTION_AUTH_INDEXES = {
    "cycle_id": "ix_agentic_ext_auth_cycle_id",
    "authorized_by_user_id": "ix_agentic_ext_auth_authorized_by",
    "repository_id": "ix_agentic_ext_auth_repository_id",
    "domain_key": "ix_agentic_ext_auth_domain_key",
}


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "agentic_delivery_cycles",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "conversation_id", sa.UUID(), sa.ForeignKey("conversations.id", ondelete="SET NULL")
        ),
        sa.Column(
            "created_by_user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "repository_ids", _jsonb(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column("domain_key", sa.String(length=128)),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("business_goal", sa.Text(), nullable=False),
        sa.Column("scope_boundary", sa.Text(), nullable=False),
        sa.Column(
            "expected_outputs", _jsonb(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column(
            "acceptance_expectations",
            _jsonb(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="Draft"),
        sa.Column("execution_window_started_at", sa.DateTime(timezone=True)),
        sa.Column("execution_window_finished_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_agentic_delivery_cycles_created_by_user_id",
        "agentic_delivery_cycles",
        ["created_by_user_id"],
    )
    op.create_index(
        "ix_agentic_delivery_cycles_conversation_id", "agentic_delivery_cycles", ["conversation_id"]
    )
    op.create_index(
        "ix_agentic_delivery_cycles_domain_key", "agentic_delivery_cycles", ["domain_key"]
    )
    op.create_index("ix_agentic_delivery_cycles_status", "agentic_delivery_cycles", ["status"])

    op.create_table(
        "agentic_delivery_lifecycle_transitions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "cycle_id",
            sa.UUID(),
            sa.ForeignKey("agentic_delivery_cycles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_status", sa.String(length=32), nullable=False),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("changed_by_user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        *_timestamps(),
    )
    op.create_index(
        "ix_agentic_delivery_lifecycle_transitions_cycle_id",
        "agentic_delivery_lifecycle_transitions",
        ["cycle_id"],
    )

    op.create_table(
        "agentic_delivery_work_packages",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "cycle_id",
            sa.UUID(),
            sa.ForeignKey("agentic_delivery_cycles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("constraints", _jsonb(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column(
            "review_criteria", _jsonb(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column(
            "source_summary", _jsonb(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        *_timestamps(),
    )
    op.create_index(
        "ix_agentic_delivery_work_packages_cycle_id", "agentic_delivery_work_packages", ["cycle_id"]
    )
    op.create_index(
        "ix_agentic_delivery_work_packages_cycle_version",
        "agentic_delivery_work_packages",
        ["cycle_id", "version"],
    )

    op.create_table(
        "agentic_delivery_evidence_sources",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "cycle_id",
            sa.UUID(),
            sa.ForeignKey("agentic_delivery_cycles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column(
            "repository_id", sa.UUID(), sa.ForeignKey("repositories.id", ondelete="SET NULL")
        ),
        sa.Column("document_id", sa.UUID()),
        sa.Column("attachment_id", sa.UUID()),
        sa.Column("source_url", sa.Text()),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("scope_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("available", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *_timestamps(),
    )
    for col in ("cycle_id", "repository_id", "document_id", "attachment_id"):
        op.create_index(
            f"ix_agentic_delivery_evidence_sources_{col}",
            "agentic_delivery_evidence_sources",
            [col],
        )

    op.create_table(
        "agentic_delivery_outputs",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "cycle_id",
            sa.UUID(),
            sa.ForeignKey("agentic_delivery_cycles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("output_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("worktree_path", sa.Text()),
        sa.Column(
            "validation_status", sa.String(length=32), nullable=False, server_default="not_run"
        ),
        sa.Column("unsupported_claims_count", sa.Integer(), nullable=False, server_default="0"),
        *_timestamps(),
    )
    op.create_index(
        "ix_agentic_delivery_outputs_cycle_id", "agentic_delivery_outputs", ["cycle_id"]
    )

    op.create_table(
        "agentic_delivery_output_evidence_links",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "agent_output_id",
            sa.UUID(),
            sa.ForeignKey("agentic_delivery_outputs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "evidence_source_id",
            sa.UUID(),
            sa.ForeignKey("agentic_delivery_evidence_sources.id", ondelete="SET NULL"),
        ),
        sa.Column("claim_summary", sa.Text(), nullable=False),
        sa.Column("support_status", sa.String(length=32), nullable=False),
        *_timestamps(),
    )
    op.create_index(
        "ix_agentic_delivery_output_evidence_links_agent_output_id",
        "agentic_delivery_output_evidence_links",
        ["agent_output_id"],
    )

    op.create_table(
        "agentic_delivery_review_gates",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "cycle_id",
            sa.UUID(),
            sa.ForeignKey("agentic_delivery_cycles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("gate_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("trigger_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("assigned_user_id", sa.UUID()),
        sa.Column("decided_by_user_id", sa.UUID()),
        sa.Column("decision_rationale", sa.Text()),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
    )
    for col in ("cycle_id", "assigned_user_id", "decided_by_user_id"):
        op.create_index(
            f"ix_agentic_delivery_review_gates_{col}", "agentic_delivery_review_gates", [col]
        )

    op.create_table(
        "agentic_delivery_review_decisions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "cycle_id",
            sa.UUID(),
            sa.ForeignKey("agentic_delivery_cycles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("agent_output_id", sa.UUID()),
        sa.Column("review_gate_id", sa.UUID()),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("decided_by_user_id", sa.UUID(), nullable=False),
        *_timestamps(),
    )
    for col in ("cycle_id", "agent_output_id", "review_gate_id", "decided_by_user_id"):
        op.create_index(
            f"ix_agentic_delivery_review_decisions_{col}",
            "agentic_delivery_review_decisions",
            [col],
        )

    op.create_table(
        "agentic_delivery_permissions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("repository_id", sa.UUID()),
        sa.Column("domain_key", sa.String(length=128)),
        sa.Column("permission", sa.String(length=64), nullable=False),
        sa.Column("granted_by_user_id", sa.UUID(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *_timestamps(),
    )
    for col in ("user_id", "repository_id", "domain_key", "permission"):
        op.create_index(
            f"ix_agentic_delivery_permissions_{col}", "agentic_delivery_permissions", [col]
        )

    op.create_table(
        "agentic_delivery_sensitive_surfaces",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("repository_id", sa.UUID()),
        sa.Column("domain_key", sa.String(length=128)),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("match_rules", _jsonb(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *_timestamps(),
    )
    for col in ("repository_id", "domain_key"):
        op.create_index(
            f"ix_agentic_delivery_sensitive_surfaces_{col}",
            "agentic_delivery_sensitive_surfaces",
            [col],
        )

    op.create_table(
        "agentic_delivery_knowledge_items",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("repository_id", sa.UUID(), nullable=False),
        sa.Column("domain_key", sa.String(length=128)),
        sa.Column("cycle_id", sa.UUID(), nullable=False),
        sa.Column("knowledge_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "evidence_source_ids",
            _jsonb(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("needs_review", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        *_timestamps(),
    )
    for col in ("repository_id", "domain_key", "cycle_id"):
        op.create_index(
            f"ix_agentic_delivery_knowledge_items_{col}", "agentic_delivery_knowledge_items", [col]
        )

    op.create_table(
        "agentic_delivery_knowledge_reuse_relationships",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("source_repository_id", sa.UUID(), nullable=False),
        sa.Column("target_repository_id", sa.UUID(), nullable=False),
        sa.Column("source_domain_key", sa.String(length=128)),
        sa.Column("target_domain_key", sa.String(length=128)),
        sa.Column("authorized_by_user_id", sa.UUID(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *_timestamps(),
    )
    for col in (
        "source_repository_id",
        "target_repository_id",
        "source_domain_key",
        "target_domain_key",
    ):
        op.create_index(
            _KNOWLEDGE_REUSE_INDEXES[col],
            "agentic_delivery_knowledge_reuse_relationships",
            [col],
        )

    op.create_table(
        "agentic_delivery_external_action_authorizations",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("cycle_id", sa.UUID(), nullable=False),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column(
            "requested_payload",
            _jsonb(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("authorized_by_user_id", sa.UUID(), nullable=False),
        sa.Column("repository_id", sa.UUID()),
        sa.Column("domain_key", sa.String(length=128)),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column(
            "authorized_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("executed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "execution_status", sa.String(length=32), nullable=False, server_default="authorized"
        ),
    )
    for col in ("cycle_id", "authorized_by_user_id", "repository_id", "domain_key"):
        op.create_index(
            _EXTERNAL_ACTION_AUTH_INDEXES[col],
            "agentic_delivery_external_action_authorizations",
            [col],
        )

    op.create_table(
        "agentic_delivery_metrics",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("cycle_id", sa.UUID(), nullable=False),
        sa.Column("metric_name", sa.String(length=128), nullable=False),
        sa.Column("metric_value", sa.Numeric(18, 6)),
        sa.Column("metric_text", sa.Text()),
        sa.Column("metric_unit", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="system"),
        *_timestamps(),
    )
    op.create_index(
        "ix_agentic_delivery_metrics_cycle_id", "agentic_delivery_metrics", ["cycle_id"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_agentic_delivery_metrics_cycle_id", table_name="agentic_delivery_metrics")
    op.drop_table("agentic_delivery_metrics")
    for col in ("cycle_id", "authorized_by_user_id", "repository_id", "domain_key"):
        op.drop_index(
            _EXTERNAL_ACTION_AUTH_INDEXES[col],
            table_name="agentic_delivery_external_action_authorizations",
        )
    op.drop_table("agentic_delivery_external_action_authorizations")
    for col in (
        "source_repository_id",
        "target_repository_id",
        "source_domain_key",
        "target_domain_key",
    ):
        op.drop_index(
            _KNOWLEDGE_REUSE_INDEXES[col],
            table_name="agentic_delivery_knowledge_reuse_relationships",
        )
    op.drop_table("agentic_delivery_knowledge_reuse_relationships")
    for col in ("repository_id", "domain_key", "cycle_id"):
        op.drop_index(
            f"ix_agentic_delivery_knowledge_items_{col}",
            table_name="agentic_delivery_knowledge_items",
        )
    op.drop_table("agentic_delivery_knowledge_items")
    for col in ("repository_id", "domain_key"):
        op.drop_index(
            f"ix_agentic_delivery_sensitive_surfaces_{col}",
            table_name="agentic_delivery_sensitive_surfaces",
        )
    op.drop_table("agentic_delivery_sensitive_surfaces")
    for col in ("user_id", "repository_id", "domain_key", "permission"):
        op.drop_index(
            f"ix_agentic_delivery_permissions_{col}", table_name="agentic_delivery_permissions"
        )
    op.drop_table("agentic_delivery_permissions")
    for col in ("cycle_id", "agent_output_id", "review_gate_id", "decided_by_user_id"):
        op.drop_index(
            f"ix_agentic_delivery_review_decisions_{col}",
            table_name="agentic_delivery_review_decisions",
        )
    op.drop_table("agentic_delivery_review_decisions")
    for col in ("cycle_id", "assigned_user_id", "decided_by_user_id"):
        op.drop_index(
            f"ix_agentic_delivery_review_gates_{col}", table_name="agentic_delivery_review_gates"
        )
    op.drop_table("agentic_delivery_review_gates")
    op.drop_index(
        "ix_agentic_delivery_output_evidence_links_agent_output_id",
        table_name="agentic_delivery_output_evidence_links",
    )
    op.drop_table("agentic_delivery_output_evidence_links")
    op.drop_index("ix_agentic_delivery_outputs_cycle_id", table_name="agentic_delivery_outputs")
    op.drop_table("agentic_delivery_outputs")
    for col in ("cycle_id", "repository_id", "document_id", "attachment_id"):
        op.drop_index(
            f"ix_agentic_delivery_evidence_sources_{col}",
            table_name="agentic_delivery_evidence_sources",
        )
    op.drop_table("agentic_delivery_evidence_sources")
    op.drop_index(
        "ix_agentic_delivery_work_packages_cycle_version",
        table_name="agentic_delivery_work_packages",
    )
    op.drop_index(
        "ix_agentic_delivery_work_packages_cycle_id", table_name="agentic_delivery_work_packages"
    )
    op.drop_table("agentic_delivery_work_packages")
    op.drop_index(
        "ix_agentic_delivery_lifecycle_transitions_cycle_id",
        table_name="agentic_delivery_lifecycle_transitions",
    )
    op.drop_table("agentic_delivery_lifecycle_transitions")
    op.drop_index("ix_agentic_delivery_cycles_status", table_name="agentic_delivery_cycles")
    op.drop_index("ix_agentic_delivery_cycles_domain_key", table_name="agentic_delivery_cycles")
    op.drop_index(
        "ix_agentic_delivery_cycles_conversation_id", table_name="agentic_delivery_cycles"
    )
    op.drop_index(
        "ix_agentic_delivery_cycles_created_by_user_id", table_name="agentic_delivery_cycles"
    )
    op.drop_table("agentic_delivery_cycles")
