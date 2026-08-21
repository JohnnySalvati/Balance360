"""fiscal identity data migration

Revision ID: 194d0f0a9da5
Revises: 518b40f04c58
Create Date: 2026-07-24 11:03:32.606960

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "194d0f0a9da5"
down_revision: Union[str, Sequence[str], None] = "518b40f04c58"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Crear la tabla fiscal_identities.
    #    El tipo enum 'condicioniva' YA existe (lo usan entities y contacts),
    #    por eso create_type=False: reutiliza el tipo en vez de intentar recrearlo.
    op.create_table(
        "fiscal_identities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column(
            "condicion_iva",
            postgresql.ENUM(
                "INSCRIPTO",
                "EXENTO",
                "FINAL",
                "MONOTRIBUTO",
                name="condicioniva",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("tax_id", sa.String(length=11), nullable=False),
        sa.Column(
            "iibb_rate", sa.Numeric(precision=5, scale=2), server_default="0", nullable=False
        ),
        sa.Column("address", sa.String(length=200), nullable=True),
        sa.Column("iibb", sa.String(length=50), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["entity_id"],
            ["entities.id"],
        ),
        sa.ForeignKeyConstraint(
            ["modified_by"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("tax_id"),
    )

    # 2. Agregar la FK nullable en invoices (nombre explícito para poder dropearla en downgrade).
    op.add_column("invoices", sa.Column("fiscal_identity_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_invoices_fiscal_identity_id",
        "invoices",
        "fiscal_identities",
        ["fiscal_identity_id"],
        ["id"],
    )

    # 3. Migración de datos: una identidad fiscal por cada entidad que tenga CUIT.
    #    - gen_random_uuid() genera el id (el default del modelo es del lado de Python,
    #      no dispara en un INSERT SQL). Requiere PostgreSQL 13+.
    #    - regexp_replace deja solo dígitos por si algún tax_id vino con guiones,
    #      así no revienta el VARCHAR(11).
    #    - created_at/updated_at se llenan solos por su server_default now().
    op.execute(
        """
        INSERT INTO fiscal_identities
            (id, entity_id, name, condicion_iva, tax_id, iibb_rate, address, iibb, start_date)
        SELECT
            gen_random_uuid(),
            id,
            name,
            condicion_iva,
            regexp_replace(tax_id, '[^0-9]', '', 'g'),
            iibb_rate,
            address,
            iibb,
            start_date
        FROM entities
        WHERE tax_id IS NOT NULL
        """
    )

    # 4. Linkear las facturas de VENTA existentes a la identidad de su entidad.
    #    Las compras quedan con fiscal_identity_id NULL (su emisor es el proveedor).
    #    En este punto cada entidad tiene exactamente una identidad, así que el
    #    match por entity_id es inequívoco.
    op.execute(
        """
        UPDATE invoices
        SET fiscal_identity_id = fi.id
        FROM fiscal_identities fi
        WHERE fi.entity_id = invoices.entity_id
          AND invoices.invoice_type = 'sale'
        """
    )

    # 5. Recién ahora, con los datos ya copiados, dropear las columnas de entities.
    op.drop_column("entities", "iibb")
    op.drop_column("entities", "iibb_rate")
    op.drop_column("entities", "tax_id")
    op.drop_column("entities", "address")
    op.drop_column("entities", "condicion_iva")
    op.drop_column("entities", "start_date")


def downgrade() -> None:
    """Downgrade schema."""
    # 1. Re-agregar las columnas en entities (todas nullable por ahora).
    #    condicion_iva vuelve como nullable (no NOT NULL): las entidades sin CUIT
    #    no tienen identidad de la cual restaurar, quedarían NULL. El enum se
    #    reutiliza con create_type=False (el tipo sigue existiendo).
    op.add_column(
        "entities", sa.Column("start_date", sa.DATE(), autoincrement=False, nullable=True)
    )
    op.add_column(
        "entities",
        sa.Column(
            "condicion_iva",
            postgresql.ENUM(
                "INSCRIPTO",
                "EXENTO",
                "FINAL",
                "MONOTRIBUTO",
                name="condicioniva",
                create_type=False,
            ),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.add_column(
        "entities", sa.Column("address", sa.VARCHAR(length=200), autoincrement=False, nullable=True)
    )
    op.add_column(
        "entities", sa.Column("tax_id", sa.VARCHAR(length=13), autoincrement=False, nullable=True)
    )
    op.add_column(
        "entities",
        sa.Column(
            "iibb_rate",
            sa.NUMERIC(precision=5, scale=2),
            server_default=sa.text("'0'::numeric"),
            autoincrement=False,
            nullable=False,
        ),
    )
    op.add_column(
        "entities", sa.Column("iibb", sa.VARCHAR(length=50), autoincrement=False, nullable=True)
    )

    # 2. Backfill de entities desde fiscal_identities (antes de dropear la tabla).
    op.execute(
        """
        UPDATE entities
        SET tax_id = fi.tax_id,
            condicion_iva = fi.condicion_iva,
            iibb_rate = fi.iibb_rate,
            address = fi.address,
            iibb = fi.iibb,
            start_date = fi.start_date
        FROM fiscal_identities fi
        WHERE fi.entity_id = entities.id
        """
    )

    # 3. Sacar la FK y la columna de invoices.
    op.drop_constraint("fk_invoices_fiscal_identity_id", "invoices", type_="foreignkey")
    op.drop_column("invoices", "fiscal_identity_id")

    # 4. Dropear la tabla.
    op.drop_table("fiscal_identities")
