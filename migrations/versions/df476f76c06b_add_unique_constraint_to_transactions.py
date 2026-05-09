"""add unique constraint to transactions

Revision ID: df476f76c06b
Revises: 8b4ae6859411
Create Date: 2026-05-09 18:12:48.398938

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'df476f76c06b'
down_revision: Union[str, Sequence[str], None] = '8b4ae6859411'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_transaction",
        "transactions",
        ["account_id", "date", "description", "amount", "type"]
    )

def downgrade() -> None:
    op.drop_constraint("uq_transaction", "transactions", type_="unique")