import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from balance360.models.recurrence import Recurrence
from balance360.models.transaction import Transaction
from balance360.schemas.recurrence import RecurrenceCreate, RecurrenceUpdate


def get_all(db: Session, description: str = "", active_only: bool = False) -> list[Recurrence]:
    stmt = select(Recurrence)

    if description:
        stmt = stmt.where(Recurrence.description.ilike(f"%{description}%"))
    if active_only:
        stmt = stmt.where(Recurrence.is_active.is_(True))

    # La grilla mezclada arma una fila por ocurrencia y cada una lee cuenta, entidad,
    # contacto y categoría del plan: sin esto es un SELECT por relación y por recurrencia.
    stmt = stmt.options(
        selectinload(Recurrence.account),
        selectinload(Recurrence.entity),
        selectinload(Recurrence.contact),
        selectinload(Recurrence.category),
    )

    stmt = stmt.order_by(Recurrence.description)

    return list(db.execute(stmt).scalars().all())


def get_by_id(db: Session, recurrence_id: uuid.UUID) -> Recurrence | None:
    return db.execute(select(Recurrence).where(Recurrence.id == recurrence_id)).scalars().first()


def get_occupied_dates(db: Session, date_from: date, date_to: date) -> dict[uuid.UUID, set[date]]:
    """Fechas de la ventana en las que ya hay una transacción **real** de cada serie.

    Es lo que evita que una transacción de fecha futura marcada como recurrente aparezca dos
    veces el mismo día, real y fantasma: su propia fecha es la primera ocurrencia de su plan.

    Solo cubre la coincidencia exacta de fecha. El alquiler previsto el 5 y pagado el 3 sigue
    contando doble hasta que exista la supresión por bucket del intervalo (ver `PENDING.md`).
    """
    stmt = (
        select(Transaction.recurrence_id, Transaction.date)
        .where(Transaction.recurrence_id.is_not(None))
        .where(Transaction.date >= date_from)
        .where(Transaction.date <= date_to)
    )

    occupied: dict[uuid.UUID, set[date]] = {}
    for recurrence_id, occurrence_date in db.execute(stmt):
        occupied.setdefault(recurrence_id, set()).add(occurrence_date)
    return occupied


def create(db: Session, data: RecurrenceCreate) -> Recurrence:
    recurrence = Recurrence(**data.model_dump())
    db.add(recurrence)
    db.flush()
    db.refresh(recurrence)
    return recurrence


def update(db: Session, recurrence: Recurrence, data: RecurrenceUpdate) -> Recurrence:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(recurrence, field, value)
    db.flush()
    db.refresh(recurrence)
    return recurrence


def delete(db: Session, recurrence: Recurrence) -> None:
    db.delete(recurrence)
    db.flush()
