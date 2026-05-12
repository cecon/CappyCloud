"""ai_model_pricing_and_usage_tracking

Adiciona suporte a:
- Pricing por modelo em ``ai_models`` (input/output cost por 1 milhão de tokens).
- Tracking de uso por execução em ``agent_tasks``
  (model_used, prompt_tokens, completion_tokens, cost_usd).
- Tracking de uso por mensagem em ``messages`` (mesmas colunas — preenchidas
  apenas em ``role='assistant'``).
- Index em ``ai_models.model_id`` para lookup rápido durante o cálculo de custo.

Revision ID: 8272efee3060
Revises: 94d6ed5e0f5e
Create Date: 2026-04-29 19:35:06.873577

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8272efee3060"
down_revision: str | Sequence[str] | None = "94d6ed5e0f5e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # ai_models: pricing por 1M tokens (formato OpenRouter)
    op.add_column(
        "ai_models",
        sa.Column("input_cost_per_1m_usd", sa.Numeric(12, 6), nullable=True),
    )
    op.add_column(
        "ai_models",
        sa.Column("output_cost_per_1m_usd", sa.Numeric(12, 6), nullable=True),
    )
    op.create_index("ix_ai_models_model_id", "ai_models", ["model_id"], unique=False)

    # agent_tasks: uso por execução
    op.add_column(
        "agent_tasks",
        sa.Column("model_used", sa.String(length=256), nullable=True),
    )
    op.add_column(
        "agent_tasks",
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "agent_tasks",
        sa.Column(
            "completion_tokens",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "agent_tasks",
        sa.Column(
            "cost_usd",
            sa.Numeric(12, 6),
            nullable=False,
            server_default="0",
        ),
    )

    # messages: uso por turno do assistente
    op.add_column(
        "messages",
        sa.Column("model_used", sa.String(length=256), nullable=True),
    )
    op.add_column(
        "messages",
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "messages",
        sa.Column(
            "completion_tokens",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "messages",
        sa.Column(
            "cost_usd",
            sa.Numeric(12, 6),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("messages", "cost_usd")
    op.drop_column("messages", "completion_tokens")
    op.drop_column("messages", "prompt_tokens")
    op.drop_column("messages", "model_used")

    op.drop_column("agent_tasks", "cost_usd")
    op.drop_column("agent_tasks", "completion_tokens")
    op.drop_column("agent_tasks", "prompt_tokens")
    op.drop_column("agent_tasks", "model_used")

    op.drop_index("ix_ai_models_model_id", table_name="ai_models")
    op.drop_column("ai_models", "output_cost_per_1m_usd")
    op.drop_column("ai_models", "input_cost_per_1m_usd")
