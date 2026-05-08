"""refactor transaction account_id

Revision ID: f8a173ae053a
Revises: 5eca46fbf23e
Create Date: 2026-05-08 16:43:55.023454

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f8a173ae053a'
down_revision: Union[str, Sequence[str], None] = '5eca46fbf23e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DELETE FROM transactions")
    op.execute("DELETE FROM import_rules")

    op.drop_constraint('transactions_from_account_id_fkey', 'transactions', type_='foreignkey')
    op.drop_constraint('transactions_to_account_id_fkey', 'transactions', type_='foreignkey')
    op.drop_column('transactions', 'from_account_id')
    op.drop_column('transactions', 'to_account_id')

    op.add_column('transactions', sa.Column('account_id', sa.Uuid(), nullable=False))
    op.create_foreign_key('fk_transaction_account_id', 'transactions', 'accounts', ['account_id'], ['id'])

    op.add_column('import_rules', sa.Column('is_transfer', sa.Boolean(), nullable=False, server_default=sa.false()))

def downgrade() -> None:
    """Downgrade schema."""
    pass
