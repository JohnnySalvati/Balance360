"""tributetype enum on invoice_tributes

Revision ID: 562abdfac2c1
Revises: cf0357124647
Create Date: 2026-05-29 11:48:42.040670

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "562abdfac2c1"
down_revision: Union[str, Sequence[str], None] = "cf0357124647"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

tributetype = sa.Enum(
    "national",
    "provincial",
    "municipal",
    "domestic",
    "iibb",
    "iva_perception",
    "other",
    name="tributetype",
)


def upgrade() -> None:
    tributetype.create(op.get_bind(), checkfirst=True)
    op.alter_column(
        "invoice_tributes",
        "tribute_type",
        existing_type=sa.INTEGER(),
        type_=tributetype,
        existing_nullable=False,
        postgresql_using=(
            "CASE tribute_type"
            " WHEN 1 THEN 'national'"
            " WHEN 2 THEN 'provincial'"
            " WHEN 3 THEN 'municipal'"
            " WHEN 4 THEN 'domestic'"
            " WHEN 5 THEN 'iibb'"
            " WHEN 6 THEN 'iva_perception'"
            " WHEN 99 THEN 'other'"
            " END::tributetype"
        ),
    )


def downgrade() -> None:
    op.alter_column(
        "invoice_tributes",
        "tribute_type",
        existing_type=tributetype,
        type_=sa.INTEGER(),
        existing_nullable=False,
        postgresql_using=(
            "CASE tribute_type::text"
            " WHEN 'national' THEN 1"
            " WHEN 'provincial' THEN 2"
            " WHEN 'municipal' THEN 3"
            " WHEN 'domestic' THEN 4"
            " WHEN 'iibb' THEN 5"
            " WHEN 'iva_perception' THEN 6"
            " WHEN 'other' THEN 99"
            " END"
        ),
    )
    tributetype.drop(op.get_bind(), checkfirst=True)
