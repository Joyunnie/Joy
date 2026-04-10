"""fix jw user role to PHARMACIST

Revision ID: 98d504bc4064
Revises: d459ced6da36
Create Date: 2026-04-11 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "98d504bc4064"
down_revision: str = "d459ced6da36"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE users SET role = 'PHARMACIST' WHERE username = 'jw'")


def downgrade() -> None:
    op.execute("UPDATE users SET role = 'STAFF' WHERE username = 'jw'")
