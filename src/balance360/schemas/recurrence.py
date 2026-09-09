import datetime
import decimal
import uuid

from pydantic import BaseModel, ConfigDict, model_validator

from balance360.enums import IntervalUnit, TransactionType
from balance360.schemas.account import AccountShort
from balance360.schemas.category import CategoryShort
from balance360.schemas.contact import ContactShort
from balance360.schemas.entity import EntityShort


class RecurrenceBase(BaseModel):
    description: str
    amount: decimal.Decimal
    type: TransactionType
    account_id: uuid.UUID
    entity_id: uuid.UUID | None = None
    contact_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    is_transfer: bool = False
    interval_unit: IntervalUnit
    interval_count: int = 1
    starts_on: datetime.date
    ends_on: datetime.date | None = None
    is_active: bool = True


class RecurrenceCreate(RecurrenceBase):
    @model_validator(mode="after")
    def check_interval_and_dates(self) -> "RecurrenceCreate":
        return _check(self)


class RecurrenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    description: str
    amount: decimal.Decimal
    type: TransactionType
    account: AccountShort
    entity: EntityShort | None = None
    contact: ContactShort | None = None
    category: CategoryShort | None = None
    is_transfer: bool
    interval_unit: IntervalUnit
    interval_count: int
    starts_on: datetime.date
    ends_on: datetime.date | None = None
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime


class RecurrenceUpdate(BaseModel):
    description: str | None = None
    amount: decimal.Decimal | None = None
    type: TransactionType | None = None
    account_id: uuid.UUID | None = None
    entity_id: uuid.UUID | None = None
    contact_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    is_transfer: bool | None = None
    interval_unit: IntervalUnit | None = None
    interval_count: int | None = None
    starts_on: datetime.date | None = None
    ends_on: datetime.date | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def check_interval_and_dates(self) -> "RecurrenceUpdate":
        return _check(self)


def _check(data):
    """Las dos validaciones que también son CHECK en la base.

    Doble capa a propósito, igual que el CUIT único de contactos: acá sale el mensaje que se
    puede leer, y el constraint es la garantía para lo que escriba por `crud` sin pasar por el
    schema. `interval_count = 0` es el peligroso: el generador de ocurrencias avanzaría siempre
    a la misma fecha y solo cortaría contra el tope de seguridad.
    """
    if data.interval_count is not None and data.interval_count < 1:
        raise ValueError("La frecuencia tiene que repetirse cada 1 período o más.")
    # En un PATCH parcial cualquiera de las dos puede venir sin setear; ahí no hay par que
    # comparar y la garantía queda del lado del CHECK, que ve la fila entera.
    if data.starts_on is not None and data.ends_on is not None and data.ends_on < data.starts_on:
        raise ValueError("La fecha de fin no puede ser anterior a la de inicio.")
    return data
