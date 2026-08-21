"""replace currency_code with currency_id in accounts

Revision ID: 8b4ae6859411
Revises: 0f69872f659f
Create Date: 2026-05-09 12:54:55.277305

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8b4ae6859411"
down_revision: Union[str, Sequence[str], None] = "0f69872f659f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DELETE FROM transactions")
    op.execute("DELETE FROM import_rules")

    op.add_column("accounts", sa.Column("currency_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_account_currency_id", "accounts", "currencies", ["currency_id"], ["id"]
    )

    op.execute("""
        UPDATE accounts
        SET currency_id = currencies.id
        FROM currencies
        WHERE currencies.code = accounts.currency_code
    """)

    op.alter_column("accounts", "currency_id", nullable=False)
    op.drop_column("accounts", "currency_code")


def downgrade() -> None:
    op.add_column("accounts", sa.Column("currency_code", sa.String(5), nullable=True))
    op.drop_constraint("fk_account_currency_id", "accounts", type_="foreignkey")
    op.drop_column("accounts", "currency_id")
