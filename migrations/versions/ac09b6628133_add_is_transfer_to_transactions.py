"""add is_transfer to transactions

Revision ID: ac09b6628133
Revises: f8a173ae053a
Create Date: 2026-05-08 16:50:56.559918

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ac09b6628133"
down_revision: Union[str, Sequence[str], None] = "f8a173ae053a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("is_transfer", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("transactions", "is_transfer")
