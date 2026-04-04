"""add_position_to_shelf_layouts

Revision ID: a1b2c3d4e5f6
Revises: e985679277a6
Create Date: 2026-04-04 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'e985679277a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'shelf_layouts',
        sa.Column('position', sa.String(length=10), nullable=False, server_default='front'),
    )


def downgrade() -> None:
    op.drop_column('shelf_layouts', 'position')
