import datetime
import uuid
from decimal import Decimal

from pydantic import BaseModel

from balance360.enums import ImportRowStatus


class ImportRowCreate(BaseModel):
    batch_id: uuid.UUID
    account_id: uuid.UUID
    source_row: int
    date: datetime.date | None = None
    description: str
    debit: Decimal | None = None
    credit: Decimal | None = None
    status: ImportRowStatus
    reason: str


class ImportRowUpdate(BaseModel):
    batch_id: uuid.UUID | None = None
    account_id: uuid.UUID | None = None
    source_row: int | None = None
    date: datetime.date | None = None
    description: str | None = None
    debit: Decimal | None = None
    credit: Decimal | None = None
    status: ImportRowStatus | None = None
    reason: str | None = None
