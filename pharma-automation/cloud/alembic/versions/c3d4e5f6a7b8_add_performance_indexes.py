"""add performance indexes for alert_logs, OCR tables, predictions, narcotics_transactions

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-08 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # P0: alert_logs — dedup query (sync cycle, narcotics/OTC writes)
    op.create_index(
        "idx_alert_dedup",
        "alert_logs",
        ["pharmacy_id", "alert_type", "ref_table", "ref_id", "sent_at"],
        postgresql_where="read_at IS NULL",
    )
    # P0: alert_logs — list endpoint sorted by sent_at (dashboard)
    op.create_index(
        "idx_alert_logs_pharmacy_sent",
        "alert_logs",
        ["pharmacy_id", "sent_at"],
    )
    # P1: receipt_ocr_records — list page (no index existed)
    op.create_index(
        "idx_receipt_ocr_pharmacy_created",
        "receipt_ocr_records",
        ["pharmacy_id", "created_at"],
    )
    # P1: receipt_ocr_items — FK child table (GROUP BY record_id, detail view)
    op.create_index(
        "idx_receipt_ocr_items_record",
        "receipt_ocr_items",
        ["record_id"],
    )
    # P1: prescription_ocr_records — list page (no index existed)
    op.create_index(
        "idx_prescription_ocr_pharmacy_created",
        "prescription_ocr_records",
        ["pharmacy_id", "created_at"],
    )
    # P1: prescription_ocr_drugs — FK child table (GROUP BY record_id)
    op.create_index(
        "idx_prescription_ocr_drugs_record",
        "prescription_ocr_drugs",
        ["record_id"],
    )
    # P2: visit_predictions — prediction list filter + sort
    op.create_index(
        "idx_predictions_pharmacy_date",
        "visit_predictions",
        ["pharmacy_id", "predicted_visit_date"],
    )
    # P2: narcotics_transactions — transaction list with tenant filter
    op.create_index(
        "idx_narcotics_tx_pharmacy",
        "narcotics_transactions",
        ["pharmacy_id", "narcotics_inventory_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_narcotics_tx_pharmacy", table_name="narcotics_transactions")
    op.drop_index("idx_predictions_pharmacy_date", table_name="visit_predictions")
    op.drop_index("idx_prescription_ocr_drugs_record", table_name="prescription_ocr_drugs")
    op.drop_index("idx_prescription_ocr_pharmacy_created", table_name="prescription_ocr_records")
    op.drop_index("idx_receipt_ocr_items_record", table_name="receipt_ocr_items")
    op.drop_index("idx_receipt_ocr_pharmacy_created", table_name="receipt_ocr_records")
    op.drop_index("idx_alert_logs_pharmacy_sent", table_name="alert_logs")
    op.drop_index("idx_alert_dedup", table_name="alert_logs")
