"""add ON DELETE to drug_id foreign keys

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-04-10 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2a3b4c5d6e7"
down_revision: str = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # CASCADE: delete child rows when drug is deleted
    for table, constraint in [
        ("visit_drugs", "visit_drugs_drug_id_fkey"),
        ("drug_stock", "drug_stock_drug_id_fkey"),
        ("otc_inventory", "otc_inventory_drug_id_fkey"),
        ("drug_thresholds", "drug_thresholds_drug_id_fkey"),
        ("narcotics_inventory", "narcotics_inventory_drug_id_fkey"),
    ]:
        op.drop_constraint(constraint, table, type_="foreignkey")
        op.create_foreign_key(constraint, table, "drugs",
                              ["drug_id"], ["id"], ondelete="CASCADE")

    # SET NULL: preserve history rows, clear drug reference
    for table, column, constraint in [
        ("prescription_inventory", "drug_id", "prescription_inventory_drug_id_fkey"),
        ("receipt_ocr_items", "drug_id", "receipt_ocr_items_drug_id_fkey"),
        ("receipt_ocr_items", "confirmed_drug_id", "receipt_ocr_items_confirmed_drug_id_fkey"),
    ]:
        op.drop_constraint(constraint, table, type_="foreignkey")
        op.create_foreign_key(constraint, table, "drugs",
                              [column], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    raise NotImplementedError("Downgrade not supported — FK ON DELETE behavior changed.")
