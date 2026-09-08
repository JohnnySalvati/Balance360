"""add fulfilled_at to invoices

Separa el hecho fisico (entregado / recibido) del hecho fiscal (confirmado).

El backfill es lo importante: hasta ahora confirmar y mover la mercaderia eran el
mismo acto, asi que todo lo confirmado ya estaba movido. Poner `fulfilled_at = date`
deja el stock historico identico al de antes de esta migracion —`services/stock.py`
pasa a contar por `fulfilled_at`— y evita que cada comprobante viejo aparezca en la
lista de entregas pendientes.

Revision ID: a7c4e91d2b60
Revises: b1e6c4a70f52
Create Date: 2026-09-08 10:12:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7c4e91d2b60"
down_revision: Union[str, Sequence[str], None] = "b1e6c4a70f52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("invoices", sa.Column("fulfilled_at", sa.Date(), nullable=True))
    op.execute("UPDATE invoices SET fulfilled_at = date WHERE confirmed")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("invoices", "fulfilled_at")
