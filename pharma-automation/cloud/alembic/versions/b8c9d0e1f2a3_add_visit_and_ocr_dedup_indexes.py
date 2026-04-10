"""add visit and OCR dedup indexes

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-04-09 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b8c9d0e1f2a3'
down_revision: Union[str, Sequence[str], None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # P0: FK index on visit_drugs.drug_id (needed for FK enforcement + JOINs)
    op.create_index("idx_visit_drugs_drug_id", "visit_drugs", ["drug_id"])
    # P0: composite for prediction batch (pharmacy_id + visit_date range)
    op.create_index("idx_visit_history_pharmacy_date", "patient_visit_history", ["pharmacy_id", "visit_date"])
    # P1: dedup check on receipt upload
    op.create_index("idx_receipt_ocr_pharmacy_receipt_num", "receipt_ocr_records", ["pharmacy_id", "receipt_number"])
    # P1: dedup check on prescription upload
    op.create_index("idx_prescription_ocr_pharmacy_presc_num", "prescription_ocr_records", ["pharmacy_id", "prescription_number"])


def downgrade() -> None:
    op.drop_index("idx_prescription_ocr_pharmacy_presc_num", table_name="prescription_ocr_records")
    op.drop_index("idx_receipt_ocr_pharmacy_receipt_num", table_name="receipt_ocr_records")
    op.drop_index("idx_visit_history_pharmacy_date", table_name="patient_visit_history")
    op.drop_index("idx_visit_drugs_drug_id", table_name="visit_drugs")
