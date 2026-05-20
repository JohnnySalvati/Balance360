"""add status to invoices

Revision ID: f31293cabed9
Revises: 4603344d6003
Create Date: 2026-05-18 11:12:40.493925

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f31293cabed9'
down_revision: Union[str, Sequence[str], None] = '4603344d6003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.execute("CREATE TYPE voucherstatus AS ENUM ('pending', 'paid')")
    op.add_column('invoices', sa.Column('status', sa.Enum('pending', 'paid', name='voucherstatus'), nullable=False, server_default='pending'))

def downgrade() -> None:
    op.drop_column('invoices', 'status')
    op.execute("DROP TYPE voucherstatus")