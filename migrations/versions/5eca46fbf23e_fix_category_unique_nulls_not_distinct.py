"""fix category unique nulls not distinct

Revision ID: 5eca46fbf23e
Revises: 9e8cf1ba33c4
Create Date: 2026-05-08 10:29:53.551222

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5eca46fbf23e"
down_revision: Union[str, Sequence[str], None] = "9e8cf1ba33c4"
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
