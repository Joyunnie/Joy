"""change drug_id FK from CASCADE to RESTRICT on inventory tables, add SET NULL on prediction visit FK

Revision ID: de3341c5e90d
Revises: 4b3155408376
Create Date: 2026-04-10 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "de3341c5e90d"
down_revision: str = "4b3155408376"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (table, constraint_name, column, ref_table, new_ondelete)
_FK_CHANGES = [
    ("otc_inventory", "otc_inventory_drug_id_fkey", "drug_id", "drugs", "RESTRICT"),
    ("drug_thresholds", "drug_thresholds_drug_id_fkey", "drug_id", "drugs", "RESTRICT"),
    ("drug_stock", "drug_stock_drug_id_fkey", "drug_id", "drugs", "RESTRICT"),
    ("narcotics_inventory", "narcotics_inventory_drug_id_fkey", "drug_id", "drugs", "RESTRICT"),
    ("visit_predictions", "visit_predictions_last_visit_id_fkey", "last_visit_id", "patient_visit_history", "SET NULL"),
]


def upgrade() -> None:
    for table, constraint, column, ref_table, ondelete in _FK_CHANGES:
        op.drop_constraint(constraint, table, type_="foreignkey")
        op.create_foreign_key(
            constraint, table, ref_table,
            [column], ["id"], ondelete=ondelete,
        )


def downgrade() -> None:
    # Revert to CASCADE / no-ondelete
    _REVERT = [
        ("otc_inventory", "otc_inventory_drug_id_fkey", "drug_id", "drugs", "CASCADE"),
        ("drug_thresholds", "drug_thresholds_drug_id_fkey", "drug_id", "drugs", "CASCADE"),
        ("drug_stock", "drug_stock_drug_id_fkey", "drug_id", "drugs", "CASCADE"),
        ("narcotics_inventory", "narcotics_inventory_drug_id_fkey", "drug_id", "drugs", "CASCADE"),
        ("visit_predictions", "visit_predictions_last_visit_id_fkey", "last_visit_id", "patient_visit_history", None),
    ]
    for table, constraint, column, ref_table, ondelete in _REVERT:
        op.drop_constraint(constraint, table, type_="foreignkey")
        op.create_foreign_key(
            constraint, table, ref_table,
            [column], ["id"], ondelete=ondelete,
        )
