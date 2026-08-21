"""convert entity_memberships.role to native enum

Revision ID: f2d7a1f428dc
Revises: e58d2605766e
Create Date: 2026-06-25 16:10:01.923223

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2d7a1f428dc"
down_revision: Union[str, Sequence[str], None] = "e58d2605766e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


role_enum = sa.Enum("owner", "operator", name="role")


def upgrade() -> None:
    """Upgrade schema."""
    role_enum.create(op.get_bind(), checkfirst=True)
    op.alter_column(
        "entity_memberships",
        "role",
        existing_type=sa.VARCHAR(length=20),
        type_=role_enum,
        existing_nullable=False,
        postgresql_using="role::role",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "entity_memberships",
        "role",
        existing_type=role_enum,
        type_=sa.VARCHAR(length=20),
        existing_nullable=False,
    )
    role_enum.drop(op.get_bind(), checkfirst=True)
