"""Convertir filas en revisión de una importación en transacciones.

Lo que vale es lo que el operador ve en la grilla: fecha, descripción, monto, tipo y cuenta
llegan del formulario de cada fila, no de las columnas `debit`/`credit` que dejó el parser.
Antes la importación masiva volvía a las columnas guardadas —`debit` para un egreso,
`credit` para un ingreso—, así que una fila parseada con el importe en `debit` e importada
como ingreso no encontraba monto, se salteaba en silencio y quedaba pendiente para siempre.

La importación es **todo o nada**: se validan todas las filas antes de crear la primera
transacción, y si alguna falla se lanza `ImportRowValidationError` con el detalle de cada
una. El rollback de `get_db` cubriría igual una falla a mitad de camino, pero es la segunda
red: validar primero es lo que permite juntar todos los errores en un solo mensaje en vez
de cortar en el primero.
"""

import datetime
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from balance360.crud import account as account_crud
from balance360.crud import import_row as import_row_crud
from balance360.crud import transaction as transaction_crud
from balance360.enums import ImportRowStatus, TransactionType
from balance360.exceptions import ImportRowValidationError
from balance360.models.import_row import ImportRow
from balance360.models.money import money
from balance360.models.transaction import Transaction
from balance360.schemas.import_row import ImportRowUpdate
from balance360.schemas.transaction import TransactionCreate

# Largo de `transactions.description`. Sin este chequeo el texto largo llega al INSERT y
# vuelve como error de servidor en vez de como un mensaje que nombre la fila.
DESCRIPTION_MAX_LENGTH = 200

# Cuántas filas con error se listan en el toast. Más que eso no se lee: alcanza para que el
# operador sepa por dónde empezar, y el resto se resume como "y N más".
MAX_ERRORS_SHOWN = 5


@dataclass(frozen=True)
class ImportRowInput:
    """Lo que el formulario manda para una fila, tal cual: strings sin interpretar.

    El parseo es parte de la validación —un monto vacío o una fecha mal escrita son errores
    de la fila, no del request—, por eso no se convierte en la ruta.
    """

    row_id: uuid.UUID
    date: str
    description: str
    amount: str
    type: str
    account_id: str


def import_rows(db: Session, inputs: list[ImportRowInput]) -> list[Transaction]:
    if not inputs:
        raise ImportRowValidationError("No hay filas seleccionadas para importar.")

    validated: list[tuple[ImportRow, TransactionCreate]] = []
    errors: list[str] = []
    seen: set[uuid.UUID] = set()

    for item in inputs:
        if item.row_id in seen:
            # Mismo id dos veces en un request: crearía dos transacciones de una fila.
            continue
        seen.add(item.row_id)

        row = import_row_crud.get_by_id(db, item.row_id)
        if row is None:
            errors.append("una de las filas ya no existe (recargá la página)")
            continue

        row_errors, data = _validate(db, row, item)
        if data is None:
            label = item.description.strip() or row.description or f"fila {row.source_row}"
            errors.append(f'"{label}": {", ".join(row_errors)}')
        else:
            validated.append((row, data))

    if errors:
        raise ImportRowValidationError(_format_errors(errors))

    transactions = []
    for row, data in validated:
        transactions.append(transaction_crud.create(db, data))
        import_row_crud.update(db, ImportRowUpdate(status=ImportRowStatus.imported), row)
    return transactions


def _validate(
    db: Session, row: ImportRow, item: ImportRowInput
) -> tuple[list[str], TransactionCreate | None]:
    errors: list[str] = []

    # Una pestaña vieja o un doble click mandan una fila que ya se importó o se descartó.
    # Sin esto se creaba una segunda transacción para el mismo renglón del Excel.
    if row.status != ImportRowStatus.needs_review:
        errors.append("ya no está pendiente de revisión (recargá la página)")

    date: datetime.date | None = None
    if not item.date.strip():
        errors.append("falta la fecha")
    else:
        try:
            date = datetime.date.fromisoformat(item.date.strip())
        except ValueError:
            errors.append("la fecha no es válida")

    description = item.description.strip()
    if not description:
        errors.append("falta la descripción")
    elif len(description) > DESCRIPTION_MAX_LENGTH:
        errors.append(f"la descripción supera los {DESCRIPTION_MAX_LENGTH} caracteres")

    amount: Decimal | None = None
    try:
        amount = Decimal(item.amount.strip())
    except InvalidOperation:
        errors.append("falta el monto" if not item.amount.strip() else "el monto no es válido")
    else:
        # `Decimal("NaN")` e `Infinity` parsean sin error y no son montos.
        if not amount.is_finite():
            errors.append("el monto no es válido")
            amount = None
        elif amount <= 0:
            # El signo lo da el tipo: un egreso de -100 sumaría al saldo.
            errors.append("el monto tiene que ser mayor a cero")
            amount = None

    transaction_type: TransactionType | None = None
    try:
        transaction_type = TransactionType(item.type)
    except ValueError:
        errors.append("el tipo no es válido")

    account_id: uuid.UUID | None = None
    try:
        account_id = uuid.UUID(item.account_id)
    except ValueError:
        errors.append("falta la cuenta")
    else:
        if account_crud.get_by_id(db, account_id) is None:
            errors.append("la cuenta no existe")

    # Las cuatro variables quedan en None solo si su chequeo agregó un error; el `or` es
    # para que mypy lo sepa sin un `assert`, que con `python -O` desaparece.
    if errors or date is None or amount is None or transaction_type is None or account_id is None:
        return errors, None

    return [], TransactionCreate(
        date=date,
        description=description,
        amount=money(amount),
        type=transaction_type,
        account_id=account_id,
        source_file=row.import_batch.filename,
        source_sheet=row.account.name,
        source_row=row.source_row,
        import_batch_id=row.batch_id,
        import_row_id=row.id,
    )


def _format_errors(errors: list[str]) -> str:
    shown = errors[:MAX_ERRORS_SHOWN]
    rest = len(errors) - len(shown)
    message = "No se importó nada. " + "; ".join(shown)
    if rest:
        message += f"; y {rest} más"
    return message + "."
