"""add email_confirmations, password_resets y users.email_confirmed_at

Revision ID: c5d0a91b7e38
Revises: a3f7c1d9e204
Create Date: 2026-08-29 20:10:00.000000

Las tres piezas del alta propia y de la recuperación de contraseña. Van juntas porque son una
sola unidad: sin la columna, confirmar no deja marca; sin las tablas, no hay link que
confirmar ni link que recuperar.

**Los usuarios que ya existen quedan con `email_confirmed_at` en NULL**, y está bien: nadie
confirmó nada porque hasta hoy no había nada que confirmar. La columna no es una condición
para entrar —para eso está `is_active`, que ya vale `true` en todos ellos— así que ninguno se
queda afuera por esto. Backfillearla con `now()` sería escribir que confirmaron una dirección
que nunca se les preguntó.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c5d0a91b7e38"
down_revision: Union[str, Sequence[str], None] = "a3f7c1d9e204"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _token_table(name: str, consumed_column: str) -> None:
    """Las dos tablas tienen la misma forma y solo cambia el nombre de la columna de consumo.

    Escribirlas dos veces a mano sería copiar quince líneas para cambiar una palabra, y la
    copia es justo donde se cuelan las diferencias que nadie quiso: un índice que falta en una,
    un `unique` que quedó solo en la otra.
    """
    op.create_table(
        name,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        # El hash del token, nunca el token. 64 caracteres = un SHA-256 en hexadecimal.
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(consumed_column, sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("modified_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["modified_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    # `unique` sobre el hash: es la clave con la que se resuelve un link, y dos filas con el
    # mismo hash serían dos permisos donde tiene que haber uno.
    op.create_index(f"ix_{name}_token_hash", name, ["token_hash"], unique=True)
    # Por usuario: lo usa el apagado en lote de los resets al consumir uno.
    op.create_index(f"ix_{name}_user_id", name, ["user_id"])


def upgrade() -> None:
    _token_table("email_confirmations", "confirmed_at")
    _token_table("password_resets", "used_at")
    op.add_column(
        "users", sa.Column("email_confirmed_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("users", "email_confirmed_at")
    op.drop_index("ix_password_resets_user_id", table_name="password_resets")
    op.drop_index("ix_password_resets_token_hash", table_name="password_resets")
    op.drop_table("password_resets")
    op.drop_index("ix_email_confirmations_user_id", table_name="email_confirmations")
    op.drop_index("ix_email_confirmations_token_hash", table_name="email_confirmations")
    op.drop_table("email_confirmations")
