"""remove_agentic_delivery_factory

Revision ID: 3eddd8b3a893
Revises: 0870d5b25ab2
Create Date: 2026-07-14 18:32:21.433114

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "3eddd8b3a893"
down_revision: Union[str, Sequence[str], None] = "0870d5b25ab2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_AGENTIC_DELIVERY_TABLES = (
    "agentic_delivery_metrics",
    "agentic_delivery_external_action_authorizations",
    "agentic_delivery_knowledge_reuse_relationships",
    "agentic_delivery_knowledge_items",
    "agentic_delivery_sensitive_surfaces",
    "agentic_delivery_permissions",
    "agentic_delivery_review_decisions",
    "agentic_delivery_review_gates",
    "agentic_delivery_output_evidence_links",
    "agentic_delivery_outputs",
    "agentic_delivery_evidence_sources",
    "agentic_delivery_work_packages",
    "agentic_delivery_lifecycle_transitions",
    "agentic_delivery_cycles",
)


def upgrade() -> None:
    """Upgrade schema."""
    for table_name in _AGENTIC_DELIVERY_TABLES:
        op.execute(f'DROP TABLE IF EXISTS "{table_name}" CASCADE')


def downgrade() -> None:
    """Downgrade schema."""
    raise RuntimeError(
        "Agentic Delivery Factory was removed from the application. "
        "Reverting this migration requires restoring the removed feature slice first."
    )
