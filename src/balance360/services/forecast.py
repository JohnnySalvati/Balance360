"""Previsión: las ocurrencias futuras de las recurrencias, calculadas y nunca guardadas.

**Nada de esto se persiste, y esa es la decisión central de la feature.** `transactions`
alimenta `get_account_balances`, `get_monthly_evolution`, `get_iva_position`,
`get_expenses_by_category`, `get_monthly_profit`, `get_iibb_on_sales`, el dashboard y los
reportes. Una fila proyectada ahí adentro obligaría a agregarle `is_projected == False` a esas
diez y pico de consultas, y un filtro olvidado no daría error: daría un número mentiroso que
nadie mira hasta la declaración del mes siguiente.

Además materializar traería el problema de reconciliar: cuando la transacción real entra por
importación habría que encontrar y borrar el fantasma, que es matching difuso —fecha y monto
aproximados— o sea un subsistema entero.

Ver `docs/prevision-de-gastos.md`.
"""

import calendar
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from balance360.crud import recurrence as recurrence_crud
from balance360.enums import ClassificationStatus, IntervalUnit, TransactionType
from balance360.models.account import Account
from balance360.models.category import Category
from balance360.models.contact import Contact
from balance360.models.entity import Entity
from balance360.models.recurrence import Recurrence

# Tope de seguridad por recurrencia. No es la cantidad esperada —una ventana de un mes da una
# o dos ocurrencias— sino el corte para que un `date_to` en el año 2999 no cuelgue el request.
MAX_OCCURRENCES = 1000


@dataclass(frozen=True)
class ProjectedTransaction:
    """Una ocurrencia futura. No es un modelo: no tiene id, no se guarda, no se clasifica.

    Los nombres de los campos son los de `Transaction` a propósito: la fila fantasma del
    template lee `t.date`, `t.amount`, `t.account.name` igual que la fila real.
    """

    date: date
    description: str
    amount: Decimal
    type: TransactionType
    account: Account
    entity: Entity | None
    contact: Contact | None
    category: Category | None
    is_transfer: bool
    recurrence_id: uuid.UUID
    rhythm_label: str

    @property
    def is_projected(self) -> bool:
        return True


def _add_months(anchor: date, months: int) -> date:
    """Suma meses conservando el día del ancla y clampeando al último día del mes destino.

    El 31 de enero más un mes es el 28 (o 29) de febrero. Lo que hace que la serie no quede
    pegada ahí es que `occurrences` calcula **siempre desde el ancla**: el paso siguiente es
    ancla + 2 meses = 31 de marzo, y no "el 28 de febrero más un mes".
    """
    total = anchor.month - 1 + months
    year = anchor.year + total // 12
    month = total % 12 + 1
    return date(year, month, min(anchor.day, calendar.monthrange(year, month)[1]))


def advance(anchor: date, unit: IntervalUnit, steps: int) -> date:
    match unit:
        case IntervalUnit.day:
            return anchor + timedelta(days=steps)
        case IntervalUnit.week:
            return anchor + timedelta(weeks=steps)
        case IntervalUnit.month:
            return _add_months(anchor, steps)
        case IntervalUnit.year:
            # Vía meses y no reemplazando el año, para que el 29/02 de un bisiesto clampee al
            # 28 igual que lo hace una mensual.
            return _add_months(anchor, steps * 12)


def _first_step(recurrence: Recurrence, window_start: date) -> int:
    """Cuántos saltos hay del ancla hasta el borde de la ventana. Se calcula, no se itera.

    Iterar desde el ancla parece más simple y es una trampa: una recurrencia diaria anclada en
    2020 con una ventana en 2026 son más de dos mil pasos, o sea que se comería el
    `MAX_OCCURRENCES` y **la previsión saldría vacía sin dar error** — el peor modo de fallar.

    Devuelve una cota inferior con división entera: nunca se pasa, porque el clampeo de fin de
    mes solo puede correr una fecha hacia atrás dentro de su propio mes. Las pocas ocurrencias
    que todavía caigan antes de la ventana las descarta el bucle.
    """
    if window_start <= recurrence.starts_on:
        return 0

    match recurrence.interval_unit:
        case IntervalUnit.day:
            gap = (window_start - recurrence.starts_on).days
            per_step = recurrence.interval_count
        case IntervalUnit.week:
            gap = (window_start - recurrence.starts_on).days
            per_step = recurrence.interval_count * 7
        case IntervalUnit.month:
            gap = _month_gap(recurrence.starts_on, window_start)
            per_step = recurrence.interval_count
        case IntervalUnit.year:
            gap = _month_gap(recurrence.starts_on, window_start)
            per_step = recurrence.interval_count * 12

    return max(0, gap // per_step)


def _month_gap(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month)


def occurrences(recurrence: Recurrence, window_start: date, window_end: date) -> Iterator[date]:
    """Las fechas en que cae la recurrencia dentro de [window_start, window_end], inclusive."""
    if window_start > window_end:
        return

    first = _first_step(recurrence, window_start)
    for step in range(first, first + MAX_OCCURRENCES):
        occurrence = advance(
            recurrence.starts_on, recurrence.interval_unit, recurrence.interval_count * step
        )
        if occurrence > window_end:
            return
        if recurrence.ends_on is not None and occurrence > recurrence.ends_on:
            return
        if occurrence >= window_start:
            yield occurrence


def ghost_window(period_start: date, period_end: date) -> tuple[date, date]:
    """La parte futura de un período. Vacía —inicio > fin— si el período termina en el pasado.

    Los fantasmas arrancan en `hoy + 1`: el día de hoy ya es un hecho, y prever lo que pasa hoy
    mientras se está cargando lo que pasó hoy es la forma más rápida de contar dos veces.

    De acá sale la propiedad que hace que esta feature se pueda soltar sin miedo: mirando el
    pasado no hay una sola ocurrencia que generar, y la pantalla se comporta como antes.
    """
    return max(period_start, date.today() + timedelta(days=1)), period_end


def project(
    db: Session,
    window_start: date,
    window_end: date,
    entity_id: uuid.UUID | None = None,
    account_id: uuid.UUID | None = None,
    transaction_type: TransactionType | None = None,
    category_id: uuid.UUID | None = None,
    classification_status: ClassificationStatus | None = None,
    description: str = "",
) -> list[ProjectedTransaction]:
    """Las ocurrencias de la ventana, ya filtradas con los mismos filtros que la grilla.

    La firma repite la de `transaction_crud.get_all` para que el web pueda pasarle el mismo
    `as_crud_kwargs()` a los dos y no haya dos lugares donde un filtro se puede olvidar.
    """
    # Un fantasma no tiene estado de clasificación: no es que esté pendiente, es que no
    # existe. El filtro es sobre trabajo de clasificación, y no hay nada que clasificar en algo
    # que no pasó.
    if classification_status is not None:
        return []

    if window_start > window_end:
        return []

    occupied = recurrence_crud.get_occupied_dates(db, window_start, window_end)

    projected: list[ProjectedTransaction] = []
    for recurrence in recurrence_crud.get_all(db, active_only=True):
        if entity_id and recurrence.entity_id != entity_id:
            continue
        if account_id and recurrence.account_id != account_id:
            continue
        if transaction_type and recurrence.type != transaction_type:
            continue
        if category_id and recurrence.category_id != category_id:
            continue
        if description and description.lower() not in recurrence.description.lower():
            continue

        taken = occupied.get(recurrence.id, set())
        for occurrence in occurrences(recurrence, window_start, window_end):
            if occurrence in taken:
                continue
            projected.append(
                ProjectedTransaction(
                    date=occurrence,
                    description=recurrence.description,
                    amount=recurrence.amount,
                    type=recurrence.type,
                    account=recurrence.account,
                    entity=recurrence.entity,
                    contact=recurrence.contact,
                    category=recurrence.category,
                    is_transfer=recurrence.is_transfer,
                    recurrence_id=recurrence.id,
                    rhythm_label=recurrence.rhythm_label,
                )
            )

    return projected
