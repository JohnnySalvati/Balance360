"""índice único parcial en contacts.tax_id

Revision ID: b1e6c4a70f52
Revises: c5d0a91b7e38
Create Date: 2026-09-04 10:00:00.000000

Un CUIT identifica a un sujeto: dos fichas con el mismo CUIT son dos mitades de la historia de
un mismo cliente, y ninguna de las dos muestra el total. Pasó con AOMA —"AOMA Bs. As." y
"Asociacion Obrera Minera Argentina", los dos con 30503218107— y los comprobantes se
repartieron entre las dos sin dar error, porque `get_by_tax_id` hace `.first()` sobre una
consulta sin orden: con duplicados devuelve cualquiera de las dos, y esa función es la que
resuelve el receptor de lo que llega de FactuMov y el proveedor de un PDF importado.

**Parcial**: sin CUIT puede haber muchos. El consumidor final, la persona a la que no se le
factura y el proveedor que se anota de apuro son contactos legítimos sin número, y en un
índice único sobre toda la columna Postgres los dejaría convivir igual (varios NULL no chocan)
— pero el `WHERE tax_id IS NOT NULL` deja escrito que eso es la intención y no un accidente
de cómo trata los NULL, y además achica el índice.

**El UPDATE va antes del índice**: `tax_id = ''` no es NULL, así que dos contactos con la
cadena vacía sí chocarían. Hoy los formularios mandan `tax_id or None`, pero la API JSON
acepta `""` tal cual y lo guardaba así. El schema ahora lo normaliza a NULL; esto limpia lo
que ya haya entrado.

**Los duplicados que existan hay que resolverlos ANTES de deployar esto**, con
`scripts/merge_duplicate_contacts.sql`. El chequeo previo está para que el mensaje diga cuáles
son: sin él, lo único que aparece en los logs es un `duplicate key value violates unique
constraint` con un uuid, y como el entrypoint corre `alembic upgrade head` con `set -e`, la
app no arranca hasta que alguien entienda de qué fila habla.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1e6c4a70f52"
down_revision: Union[str, Sequence[str], None] = "c5d0a91b7e38"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE contacts SET tax_id = NULL WHERE tax_id = ''")

    op.execute(
        """
        DO $$
        DECLARE
            dups text;
        BEGIN
            SELECT string_agg(format('%s (%s)', tax_id, nombres), '; ')
              INTO dups
              FROM (
                    SELECT tax_id,
                           string_agg(name, ' / ' ORDER BY created_at) AS nombres
                      FROM contacts
                     WHERE tax_id IS NOT NULL
                     GROUP BY tax_id
                    HAVING count(*) > 1
                   ) d;

            IF dups IS NOT NULL THEN
                RAISE EXCEPTION
                    'Hay contactos con el CUIT repetido: %. Unificalos con '
                    'scripts/merge_duplicate_contacts.sql y volvé a deployar.', dups;
            END IF;
        END $$;
        """
    )

    op.create_index(
        "uq_contacts_tax_id",
        "contacts",
        ["tax_id"],
        unique=True,
        postgresql_where=sa.text("tax_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_contacts_tax_id", table_name="contacts")
