"""El plan: qué se repite, con qué ritmo y hasta cuándo.

Una recurrencia **no es una transacción**. La transacción es un hecho —pasó, tiene fecha y
monto— y la recurrencia es una intención sobre el futuro. Por eso vive en su propia tabla y no
como un par de columnas en `transactions`: si el ritmo colgara de una fila de `transactions`,
esa fila sería la dueña de la serie, borrarla se llevaría toda la previsión, y actualizar el
monto previsto significaría editar un hecho pasado.

Es el mismo reparto que ya hay entre `import_rules` y `transactions`: la regla es la entidad,
la transacción guarda a cuál se aplicó.

Los campos del plan son **copia**, no referencia a la transacción semilla. La semilla se puede
borrar; el monto previsto casi nunca es el último real (se sabe que el alquiler sube antes de
que suba); y reclasificar la semilla no tiene por qué cambiar la previsión por abajo. La
contracara aceptada: reclasificar la semilla tampoco actualiza el plan — eso se hace en la
pantalla de Previsiones.

Ver `docs/prevision-de-gastos.md`.
"""

from __future__ import annotations

import datetime
import decimal
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from balance360.enums import IntervalUnit, TransactionType
from balance360.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from balance360.models.account import Account
    from balance360.models.category import Category
    from balance360.models.contact import Contact
    from balance360.models.entity import Entity
    from balance360.models.transaction import Transaction


class Recurrence(Base, TimestampMixin):
    __tablename__ = "recurrences"
    __table_args__ = (
        # `interval_count = 0` haría que el generador de ocurrencias avance siempre a la misma
        # fecha: un bucle que solo corta contra el tope de seguridad. El validador del schema
        # da el mensaje legible; esto es la garantía, porque a `crud` se le puede escribir
        # desde un script sin pasar por el schema.
        CheckConstraint("interval_count > 0", name="ck_recurrences_interval_count_positive"),
        CheckConstraint(
            "ends_on IS NULL OR ends_on >= starts_on", name="ck_recurrences_ends_after_starts"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    # Lo que se va a ver en la fila fantasma. Mismo largo que `transactions.description`
    # porque de ahí sale cuando el plan se crea desde una transacción.
    description: Mapped[str] = mapped_column(String(200))
    amount: Mapped[decimal.Decimal] = mapped_column(Numeric(precision=18, scale=2))
    type: Mapped[TransactionType] = mapped_column(Enum(TransactionType))

    # La cuenta no es opcional: es la que define en qué moneda está `amount`.
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("entities.id"))
    contact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contacts.id"))
    category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("categories.id"))
    is_transfer: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    interval_unit: Mapped[IntervalUnit] = mapped_column(Enum(IntervalUnit))
    interval_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # `starts_on` es el **ancla**, no "desde cuándo mostrar": todas las ocurrencias se calculan
    # como ancla + N intervalos, así que moverla corre la serie entera.
    starts_on: Mapped[datetime.date] = mapped_column(Date)
    ends_on: Mapped[datetime.date | None] = mapped_column(Date)

    # Apagar en vez de borrar. Borrar dispara el `SET NULL` de `transactions.recurrence_id` y
    # se pierde qué transacciones reales pertenecían a la serie; apagar es reversible.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Unidireccionales a propósito: `Entity`, `Contact`, `Category` y `Account` no necesitan
    # saber que existen las recurrencias, y agregarles el `back_populates` sería tocar cuatro
    # modelos para nada.
    account: Mapped["Account"] = relationship()
    entity: Mapped["Entity | None"] = relationship()
    contact: Mapped["Contact | None"] = relationship()
    category: Mapped["Category | None"] = relationship()

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="recurrence")

    @property
    def rhythm_label(self) -> str:
        """ "Mensual", "Cada 2 semanas". Para la grilla y el badge de la fila fantasma."""
        if self.interval_count == 1:
            return {
                IntervalUnit.day: "Diaria",
                IntervalUnit.week: "Semanal",
                IntervalUnit.month: "Mensual",
                IntervalUnit.year: "Anual",
            }[self.interval_unit]
        plural = {
            IntervalUnit.day: "días",
            IntervalUnit.week: "semanas",
            IntervalUnit.month: "meses",
            IntervalUnit.year: "años",
        }[self.interval_unit]
        return f"Cada {self.interval_count} {plural}"
