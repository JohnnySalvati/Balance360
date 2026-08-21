"""add_pending_serial_status

Revision ID: 88392e8db1fc
Revises: 88df471ee022
Create Date: 2026-06-04 10:12:40.940290

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "88392e8db1fc"
down_revision: Union[str, Sequence[str], None] = "88df471ee022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("COMMIT")  # cierra la transacción abierta por Alembic
    op.execute("ALTER TYPE serialstatus ADD VALUE 'pending'")


def downgrade():
    # Postgres no permite borrar valores de un enum
    # hay que recrearlo — por ahora dejamos pass
    pass
