"""drop rpa_commands, prescription_ocr_records, prescription_ocr_drugs tables

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-04-10 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d0e1f2a3b4c5"
down_revision: str = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS rpa_commands")
    op.execute("DROP TABLE IF EXISTS prescription_ocr_drugs")
    op.execute("DROP TABLE IF EXISTS prescription_ocr_records")


def downgrade() -> None:
    raise NotImplementedError("Downgrade not supported — tables have been removed from the codebase.")
