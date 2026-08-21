"""enum adding SerialStatus.returned

Revision ID: c71edbfe91e2
Revises: 9776915e3b74
Create Date: 2026-07-27 20:05:51.337974

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c71edbfe91e2"
down_revision: Union[str, Sequence[str], None] = "9776915e3b74"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("COMMIT")  # cierra la transacción abierta por Alembic
    op.execute("ALTER TYPE serialstatus ADD VALUE 'returned'")


def downgrade():
    # Postgres no permite borrar valores de un enum
    # hay que recrearlo — por ahora dejamos pass
    pass
