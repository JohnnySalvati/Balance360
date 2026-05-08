"""add applied_rule_id to transactions

Revision ID: 0f69872f659f
Revises: ac09b6628133
Create Date: 2026-05-08 19:13:54.957088

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0f69872f659f'
down_revision: Union[str, Sequence[str], None] = 'ac09b6628133'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('transactions', sa.Column('applied_rule_id', sa.Uuid(), nullable=True))
    op.create_foreign_key('fk_transaction_applied_rule_id', 'transactions', 'import_rules', ['applied_rule_id'], ['id'])

def downgrade() -> None:
    op.drop_constraint('fk_transaction_applied_rule_id', 'transactions', type_='foreignkey')
    op.drop_column('transactions', 'applied_rule_id')