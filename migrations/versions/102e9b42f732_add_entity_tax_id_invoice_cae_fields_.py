"""add entity tax_id, invoice cae fields, voucher status authorized

Revision ID: 102e9b42f732
Revises: d354674a5892
Create Date: 2026-05-22 10:54:32.006845

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "102e9b42f732"
down_revision: Union[str, Sequence[str], None] = "d354674a5892"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("entities", sa.Column("tax_id", sa.String(length=13), nullable=True))
    op.add_column("invoices", sa.Column("cae", sa.String(length=14), nullable=True))
    op.add_column("invoices", sa.Column("cae_expiry", sa.Date(), nullable=True))
    op.execute("ALTER TYPE voucherstatus ADD VALUE IF NOT EXISTS 'authorized' AFTER 'pending'")


def downgrade() -> None:
    op.drop_column("invoices", "cae_expiry")
    op.drop_column("invoices", "cae")
    op.drop_column("entities", "tax_id")
    # Nota: PostgreSQL no permite eliminar valores de un enum
    # Para downgrade completo habría que recrear el tipo, por ahora lo dejamos documentado
