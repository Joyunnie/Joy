"""add CHECK(current_quantity >= 0) to inventory tables

Revision ID: d459ced6da36
Revises: de3341c5e90d
Create Date: 2026-04-10 23:10:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "d459ced6da36"
down_revision: str = "de3341c5e90d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ["drug_stock", "otc_inventory", "prescription_inventory", "narcotics_inventory"]


def upgrade() -> None:
    # Clamp any existing negative values to 0 before adding constraint
    for table in _TABLES:
        op.execute(f"UPDATE {table} SET current_quantity = 0 WHERE current_quantity < 0")
        op.create_check_constraint(
            f"ck_{table}_qty_nonneg",
            table,
            "current_quantity >= 0",
        )


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.drop_constraint(f"ck_{table}_qty_nonneg", table, type_="check")
