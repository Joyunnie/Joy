"""add insurance_code to drugs

Revision ID: 656fe8dcec77
Revises: c3d4e5f6a7b8
Create Date: 2026-04-09 13:53:09.997281

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '656fe8dcec77'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('drugs', sa.Column('insurance_code', sa.String(length=20), nullable=True, comment='건강보험 약품코드 (TBSIM040_01.DRUG_CODE)'))
    op.create_index('idx_drugs_insurance_code', 'drugs', ['insurance_code'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_drugs_insurance_code', table_name='drugs')
    op.drop_column('drugs', 'insurance_code')
