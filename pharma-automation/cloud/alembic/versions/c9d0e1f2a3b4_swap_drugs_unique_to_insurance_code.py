"""swap drugs unique constraint from standard_code to insurance_code

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-04-10 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9d0e1f2a3b4"
down_revision: str = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("drugs_standard_code_key", "drugs", type_="unique")
    op.drop_index("idx_drugs_insurance_code", "drugs")
    op.create_unique_constraint("uq_drugs_insurance_code", "drugs", ["insurance_code"])


def downgrade() -> None:
    raise NotImplementedError("Downgrade not supported — drugs data has changed shape.")
