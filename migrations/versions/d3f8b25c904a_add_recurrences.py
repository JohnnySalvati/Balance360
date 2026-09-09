"""previsión de gastos: tabla recurrences y transactions.recurrence_id

Revision ID: d3f8b25c904a
Revises: a7c4e91d2b60
Create Date: 2026-09-09 10:00:00.000000

La recurrencia es el **plan** —qué se repite, con qué ritmo, hasta cuándo— y va en su propia
tabla, no como columnas en `transactions`. Si el ritmo colgara de una fila de `transactions`,
esa fila sería la dueña de la serie: borrarla se llevaría toda la previsión, y actualizar el
monto previsto significaría editar un hecho pasado. Es el mismo reparto que ya hay entre
`import_rules` y `transactions`.

**Escrita a mano y no con `--autogenerate`**: los dos CHECK no los detecta (ya está anotado en
los gotchas de CLAUDE.md), y `ondelete="SET NULL"` tampoco sale solo de la declaración del
modelo.

`interval_count > 0` no es cosmético. Con 0, el generador de ocurrencias avanza siempre a la
misma fecha y solo corta contra su tope de seguridad, o sea que una fila mal escrita por un
script se convierte en mil ocurrencias iguales en la grilla.

`ondelete="SET NULL"` en `recurrence_id`, igual que en `applied_rule_id`: borrar el plan
no puede borrar las transacciones que ya pasaron.

No hay backfill: antes de esto no existía ninguna previsión, así que todas las transacciones
arrancan con `recurrence_id` en NULL, que es el valor correcto.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d3f8b25c904a"
down_revision: Union[str, Sequence[str], None] = "a7c4e91d2b60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recurrences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("description", sa.String(length=200), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column(
            "type",
            # `postgresql.ENUM` y no `sa.Enum`: el tipo ya existe en la base desde
            # `transactions.type`, y `create_type=False` —lo que evita el
            # "type transactiontype already exists"— es un argumento del dialecto. En un
            # `sa.Enum` se acepta sin quejarse y no hace nada: la migración igual intenta el
            # CREATE TYPE y corta. Verificado corriéndola.
            postgresql.ENUM("income", "expense", name="transactiontype", create_type=False),
            nullable=False,
        ),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("contact_id", sa.Uuid(), nullable=True),
        sa.Column("category_id", sa.Uuid(), nullable=True),
        sa.Column("is_transfer", sa.Boolean(), nullable=False),
        sa.Column(
            "interval_unit",
            sa.Enum("day", "week", "month", "year", name="intervalunit"),
            nullable=False,
        ),
        sa.Column("interval_count", sa.Integer(), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("modified_by", sa.Uuid(), nullable=True),
        sa.CheckConstraint("interval_count > 0", name="ck_recurrences_interval_count_positive"),
        sa.CheckConstraint(
            "ends_on IS NULL OR ends_on >= starts_on", name="ck_recurrences_ends_after_starts"
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"]),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"]),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["modified_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.add_column("transactions", sa.Column("recurrence_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_transactions_recurrence_id",
        "transactions",
        "recurrences",
        ["recurrence_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # `get_occupied_dates` filtra por `recurrence_id IS NOT NULL` en cada render de la grilla
    # con previsión. Parcial porque la enorme mayoría de las transacciones no pertenece a
    # ninguna serie y esas filas no aportan nada al índice.
    op.create_index(
        "ix_transactions_recurrence_id",
        "transactions",
        ["recurrence_id"],
        postgresql_where=sa.text("recurrence_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_transactions_recurrence_id", table_name="transactions")
    op.drop_constraint("fk_transactions_recurrence_id", "transactions", type_="foreignkey")
    op.drop_column("transactions", "recurrence_id")
    op.drop_table("recurrences")
    sa.Enum(name="intervalunit").drop(op.get_bind(), checkfirst=True)
