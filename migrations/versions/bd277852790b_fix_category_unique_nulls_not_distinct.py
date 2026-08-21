"""fix category unique nulls not distinct

Revision ID: bd277852790b
Revises: df476f76c06b
Create Date: 2026-05-09 18:29:16.377826

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bd277852790b"
down_revision: Union[str, Sequence[str], None] = "df476f76c06b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("uq_parent_id_name", "categories", type_="unique")
    op.create_unique_constraint(
        "uq_parent_id_name", "categories", ["parent_id", "name"], postgresql_nulls_not_distinct=True
    )


def downgrade() -> None:
    op.drop_constraint("uq_parent_id_name", "categories", type_="unique")
    op.create_unique_constraint(
        "uq_parent_id_name",
        "categories",
        ["parent_id", "name"],
    )
