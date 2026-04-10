"""extend prescription_inventory with cassette metadata, drop cassette_mappings

Revision ID: a7b8c9d0e1f2
Revises: 656fe8dcec77
Create Date: 2026-04-09 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, Sequence[str], None] = '656fe8dcec77'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add cassette metadata columns to prescription_inventory
    op.add_column('prescription_inventory', sa.Column('drug_insurance_code', sa.String(20), nullable=True, comment='건강보험 약품코드'))
    op.add_column('prescription_inventory', sa.Column('drug_name', sa.String(200), nullable=True))
    op.add_column('prescription_inventory', sa.Column('drug_type', sa.String(50), nullable=True))
    op.add_column('prescription_inventory', sa.Column('dispensing_mode', sa.String(20), nullable=True, comment='순차 or 동시'))
    op.add_column('prescription_inventory', sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False))
    op.create_index('idx_prescription_inventory_insurance_code', 'prescription_inventory', ['drug_insurance_code'])

    # Make drug_id nullable (drugs may not be synced yet when importing cassette mapping)
    op.alter_column('prescription_inventory', 'drug_id', existing_type=sa.BigInteger(), nullable=True)

    # Drop orphaned cassette_mappings table if it exists
    op.execute("DROP TABLE IF EXISTS cassette_mappings CASCADE")


def downgrade() -> None:
    op.alter_column('prescription_inventory', 'drug_id', existing_type=sa.BigInteger(), nullable=False)
    op.drop_index('idx_prescription_inventory_insurance_code', table_name='prescription_inventory')
    op.drop_column('prescription_inventory', 'is_active')
    op.drop_column('prescription_inventory', 'dispensing_mode')
    op.drop_column('prescription_inventory', 'drug_type')
    op.drop_column('prescription_inventory', 'drug_name')
    op.drop_column('prescription_inventory', 'drug_insurance_code')
