"""backfill_azure_foundry_model_prices

Revision ID: f828a0d8fff6
Revises: 861952b7c568
Create Date: 2026-07-21 12:52:00.725262

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f828a0d8fff6'
down_revision: Union[str, Sequence[str], None] = '861952b7c568'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        UPDATE ai_models AS model
        SET
            input_cost_per_1m_usd = price.input_cost,
            output_cost_per_1m_usd = price.output_cost,
            tier = 'paid'
        FROM (
            VALUES
                ('DeepSeek-V4-Flash', 0.190000, 0.510000),
                ('DeepSeek-V4-Pro', 1.740000, 3.480000),
                ('gpt-5.4', 2.500000, 15.000000),
                ('gpt-5.4-mini', 0.750000, 4.500000),
                ('gpt-5-chat', 1.250000, 10.000000),
                ('Kimi-K2.6-1', 0.950000, 4.000000),
                ('text-embedding-3-large', 0.143000, 0.000000)
        ) AS price(model_id, input_cost, output_cost)
        JOIN ai_providers AS provider ON provider.id = model.provider_id
        WHERE model.model_id = price.model_id
          AND (
              lower(provider.name) LIKE '%azure%'
              OR lower(provider.base_url) LIKE '%azure%'
              OR lower(provider.base_url) LIKE '%.services.ai.%'
          )
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        """
        UPDATE ai_models AS model
        SET
            input_cost_per_1m_usd = NULL,
            output_cost_per_1m_usd = NULL,
            tier = 'unknown'
        FROM ai_providers AS provider
        WHERE provider.id = model.provider_id
          AND model.model_id IN (
              'DeepSeek-V4-Flash',
              'DeepSeek-V4-Pro',
              'gpt-5.4',
              'gpt-5.4-mini',
              'gpt-5-chat',
              'Kimi-K2.6-1',
              'text-embedding-3-large'
          )
          AND (
              lower(provider.name) LIKE '%azure%'
              OR lower(provider.base_url) LIKE '%azure%'
              OR lower(provider.base_url) LIKE '%.services.ai.%'
          )
        """
    )
