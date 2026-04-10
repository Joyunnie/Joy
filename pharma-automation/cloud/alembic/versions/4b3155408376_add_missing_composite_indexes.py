"""add missing composite indexes for alert_logs and narcotics_transactions

Revision ID: 4b3155408376
Revises: b3c4d5e6f7a8
Create Date: 2026-04-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "4b3155408376"
down_revision: str = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # alert_logs: filter by alert_type (AlertsPage type chips)
    op.create_index(
        "idx_alert_logs_pharmacy_type",
        "alert_logs",
        ["pharmacy_id", "alert_type"],
    )
    # narcotics_transactions: list ordered by created_at
    op.create_index(
        "idx_narcotics_tx_pharmacy_created",
        "narcotics_transactions",
        ["pharmacy_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_narcotics_tx_pharmacy_created", table_name="narcotics_transactions")
    op.drop_index("idx_alert_logs_pharmacy_type", table_name="alert_logs")
