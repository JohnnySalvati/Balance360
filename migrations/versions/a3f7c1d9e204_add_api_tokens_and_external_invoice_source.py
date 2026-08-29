"""add api tokens and external invoice source

Revision ID: a3f7c1d9e204
Revises: 54b69e76dda6
Create Date: 2026-08-29

Las tres cosas que necesita la integración con FactuMov:

- `api_tokens`, para que una app pueda entrar a `/api` sin ser una persona con cookie.
- `invoices.external_source` / `external_id`, la clave de idempotencia del registro.
- `invoice_lines.unit_price` a cuatro decimales, sin la cual una factura B de $100 no se
  puede reexpresar en neto sin perder un centavo contra el CAE.

La ampliación del `unit_price` es lo único que toca datos que ya están, y no los cambia:
numeric(18,2) → numeric(18,4) conserva cada valor tal cual. El `downgrade` sí redondea, y por
eso puede perder los decimales de las líneas que hayan entrado por la integración.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3f7c1d9e204"
down_revision: Union[str, Sequence[str], None] = "54b69e76dda6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "api_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("modified_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["modified_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_api_tokens_token_hash"), "api_tokens", ["token_hash"], unique=True
    )

    op.add_column("invoices", sa.Column("external_source", sa.String(length=20), nullable=True))
    op.add_column("invoices", sa.Column("external_id", sa.Uuid(), nullable=True))
    # Unique sobre dos columnas nullable: en Postgres los NULL no chocan entre sí, así que
    # todos los comprobantes cargados a mano —que tienen las dos en NULL— conviven sin
    # problema y la restricción solo se aplica a los que sí vinieron de afuera.
    op.create_unique_constraint(
        "uq_invoices_external", "invoices", ["external_source", "external_id"]
    )

    op.alter_column(
        "invoice_lines",
        "unit_price",
        existing_type=sa.Numeric(precision=18, scale=2),
        type_=sa.Numeric(precision=18, scale=4),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "invoice_lines",
        "unit_price",
        existing_type=sa.Numeric(precision=18, scale=4),
        type_=sa.Numeric(precision=18, scale=2),
        existing_nullable=False,
    )
    op.drop_constraint("uq_invoices_external", "invoices", type_="unique")
    op.drop_column("invoices", "external_id")
    op.drop_column("invoices", "external_source")
    op.drop_index(op.f("ix_api_tokens_token_hash"), table_name="api_tokens")
    op.drop_table("api_tokens")
