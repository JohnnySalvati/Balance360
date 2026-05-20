"""add VoucherStatus to invoices

Revision ID: 47803ff107e1
Revises: ecc4b78e141b
Create Date: 2026-05-18 12:25:24.448389

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '47803ff107e1'
down_revision: Union[str, Sequence[str], None] = 'ecc4b78e141b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.execute("ALTER TYPE voucherstatus ADD VALUE 'draft'")

def downgrade() -> None:
    # PostgreSQL no permite eliminar valores de un enum
    # Para hacer downgrade habría que recrear el tipo completo
    pass